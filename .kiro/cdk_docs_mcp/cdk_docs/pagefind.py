"""Query the CDK v2 reference's own Pagefind search index from Python.

The CDK reference site (``docs.aws.amazon.com/cdk/api/v2/docs``) builds a
Pagefind index of every page and searches it client-side. That index
ranks by page content and tags each page with two filters, ``module``
(``aws-connect``, ``aws-lex``, ...) and ``kind`` (``construct``,
``struct``, ``interface``, ...). The AWS docs search proxy the server used
before only matches page titles well: "agentcore gateway target" found no
AgentCore page there, but tops Pagefind's results.

Pagefind has no HTTP search API and no Python client; its npm and PyPI
packages only build indexes (upstream issue Pagefind/pagefind#519). Its
search core is a Rust crate compiled to WASM, served by the site as
``wasm.en-us.pagefind``. This module loads that same WASM with
``wasmtime`` and replays the calls ``pagefind.js`` makes, so ranking
matches the site's search box:

    init_pagefind(meta) -> request_indexes(term) -> load_index_chunk(...)
    -> request_filter_indexes(filters) -> load_filter_chunk(...)
    -> search(...) -> fetch fragment/<hash>.pf_fragment per result

An earlier version ran the site's ``pagefind.js`` in a sandboxed Node
process per query. That needed Node 22.13+ on the MCP client's PATH and
re-downloaded about 400 KB on every call. Here the engine stays loaded in
the server process and Pagefind only fetches index chunks it has not
seen; a new index build on the site (a new hash in
``pagefind-entry.json``) rebuilds it.

The WASM module can do no I/O: it has a single import,
``__wbindgen_init_externref_table``, which this module supplies. Python
does every fetch, always under ``PAGEFIND_BASE_PATH``, and every hash the
index hands back is checked against ``_HASH_RE`` before it goes into a
path.

The string glue follows wasm-bindgen: inputs are copied into WASM memory
through ``__wbindgen_malloc``; string results come back as a
``(pointer, length)`` pair that must be released with ``__wbindgen_free``;
every ``init``/``load`` call returns a new index pointer that replaces the
old one. That glue is tied to the Pagefind version, so an index built by
another minor version than ``SUPPORTED_VERSION_PREFIX`` raises
``PagefindUnavailable`` instead of risking wrong results.

Query preparation and excerpts are ports of ``pagefind.js`` 1.5.2:
``normalize_term`` mirrors its punctuation stripping and diacritic
folding, and ``excerpt_start`` / ``plain_excerpt`` mirror
``calculate_excerpt_region`` / ``build_excerpt``.

Every failure raises ``PagefindUnavailable`` with a reason, and
``search.cdk_search`` then falls back to the docs search proxy and says
so in its output.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests

logger = logging.getLogger(__name__)

PAGEFIND_BASE_PATH = "https://docs.aws.amazon.com/cdk/api/pagefind/"
# Fragment URLs are relative to the site root the bundle sits under.
SITE_BASE_URL = "https://docs.aws.amazon.com/cdk/api"

# Only the stable ``aws-cdk-lib`` library is in scope: this keeps the four
# Connect modules and drops ``@aws-cdk/*`` alpha packages, the
# ``@aws-cdk/cfn-property-mixins`` pages, and CDK v1.
RESULT_URL_PREFIX = "https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib."

# docs.aws.amazon.com intermittently serves its 404 page to a short or
# missing User-Agent.
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

LANGUAGE = "en-us"
SUPPORTED_VERSION_PREFIX = "1.5."
EXCERPT_LENGTH = 30  # words, the pagefind.js default
FRAGMENT_BUDGET_FACTOR = 5  # fragments loaded per requested hit, at most
FETCH_WORKERS = 8
REQUEST_TIMEOUT = 30
# Rebuild the engine once this many index chunks are loaded, so a
# long-lived server does not grow without bound.
MAX_LOADED_CHUNKS = 400
# Parsed result fragments kept per index build; cleared when exceeded.
MAX_CACHED_FRAGMENTS = 1000

_SIGNATURE = b"pagefind_dcd"
_HASH_RE = re.compile(r"[A-Za-z0-9_-]+")
_WEIGHT_MARKER = "___END_PAGEFIND_WEIGHT___"
_PUNCTUATION_CATEGORIES = frozenset({"Pd", "Pe", "Pf", "Pi", "Po", "Ps"})
_EXACT_RE = re.compile(r'\s*".+"\s*')
_IMPORT_MODULE = "./pagefind_web_bg.js"
_EXPECTED_IMPORTS = {(_IMPORT_MODULE, "__wbindgen_init_externref_table")}


class PagefindUnavailable(RuntimeError):
    """Raised when the Pagefind search cannot run; ``str()`` is the reason."""


# ----- input preparation --------------------------------------------------------


def normalize_module(module: str | None) -> str | None:
    """Map a CDK library name onto Pagefind's ``module`` filter value.

    Accepts the Pagefind value itself (``aws-connect``), the Python module
    (``aws_connect``), or the full library (``aws_cdk.aws_connect``).

    Args:
        module: The caller's module or library name, or ``None``.

    Returns:
        The Pagefind ``module`` value, or ``None`` when no filter applies.
    """
    if module is None or not module.strip():
        return None
    value = module.strip().lower().removeprefix("aws_cdk.")
    return value.replace("_", "-")


def normalize_term(term: str, include_characters: frozenset[str] = frozenset()) -> tuple[str, str, bool]:
    """Prepare a query the way ``pagefind.js`` does before calling the WASM.

    Punctuation (Unicode categories Pd, Pe, Pf, Pi, Po, Ps) is dropped
    unless the index lists it in ``include_characters``; everything else
    is lowercased and runs of whitespace collapse. The search term then
    has its diacritics folded, while the original keeps them for the
    diacritic-similarity ranking.

    Args:
        term: The raw query.
        include_characters: Characters the index keeps verbatim.

    Returns:
        ``(term, original_term, exact)``, where ``exact`` is true for a
        query wrapped in double quotes.
    """
    exact = bool(_EXACT_RE.fullmatch(term))
    kept = []
    for ch in term:
        if ch in include_characters:
            kept.append(ch)
        elif unicodedata.category(ch) not in _PUNCTUATION_CATEGORIES:
            kept.append(ch.lower())
    original = re.sub(r"\s{2,}", " ", "".join(kept)).strip()
    folded = "".join(
        c for c in unicodedata.normalize("NFD", original) if not unicodedata.category(c).startswith("M")
    )
    return folded, original, exact


# ----- excerpts (ports of pagefind.js calculate_excerpt_region / build_excerpt) --


def excerpt_start(locations: list[tuple[int, float]], length: int = EXCERPT_LENGTH) -> int:
    """Pick the word offset of the densest ``length``-word window of matches.

    Args:
        locations: ``(word_location, balanced_score)`` per matched word.
        length: Window size in words.

    Returns:
        The window's starting word index, 0 when there is nothing to pick.
    """
    if not locations:
        return 0
    size = max(loc for loc, _ in locations) + 1
    words = [0.0] * size
    for loc, score in locations:
        words[loc] += score
    if size <= length:
        return 0
    densest = sum(words[:length])
    working = densest
    densest_at = [0]
    for i in range(size):
        boundary = i + length
        working += (words[boundary] if boundary < size else 0.0) - words[i]
        if working > densest:
            densest = working
            densest_at = [i]
        elif working == densest and densest_at[-1] == i - 1:
            densest_at.append(i)
    return densest_at[len(densest_at) // 2]


def plain_excerpt(content: str, start: int, length: int = EXCERPT_LENGTH) -> str:
    """Return ``length`` words of ``content`` from ``start``, clamped to the text."""
    if "\u200b" in content:
        words, joiner = content.split("\u200b"), ""
    else:
        words, joiner = re.split(r"[\r\n\s]+", content), " "
    length = min(length, len(words))
    start = max(0, min(start, len(words) - length))
    return joiner.join(words[start : start + length]).strip()


# ----- fetching -----------------------------------------------------------------


def _fetch(path: str) -> bytes:
    """GET ``path`` under ``PAGEFIND_BASE_PATH``; raise ``PagefindUnavailable`` on failure."""
    url = PAGEFIND_BASE_PATH + path
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise PagefindUnavailable(f"GET {path} failed: {exc}") from exc
    return response.content


def _fetch_many(paths: list[str]) -> list[bytes]:
    """Fetch several index files in parallel, in order."""
    if not paths:
        return []
    with ThreadPoolExecutor(max_workers=min(FETCH_WORKERS, len(paths))) as pool:
        return list(pool.map(_fetch, paths))


def decompress(data: bytes, name: str) -> bytes:
    """Strip Pagefind's file envelope: optional gzip, then the 12-byte signature."""
    if data[: len(_SIGNATURE)] == _SIGNATURE:
        return data[len(_SIGNATURE) :]
    try:
        data = gzip.decompress(data)
    except (OSError, EOFError) as exc:
        raise PagefindUnavailable(f"{name} is neither gzip nor a Pagefind file") from exc
    if data[: len(_SIGNATURE)] != _SIGNATURE:
        raise PagefindUnavailable(f"{name} lacks the Pagefind signature")
    return data[len(_SIGNATURE) :]


def _checked_hash(value: Any, what: str) -> str:
    """A hash from the index, verified before it goes into a fetch path."""
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise PagefindUnavailable(f"index returned an invalid {what} {value!r}")
    return value


def _absolute_url(raw: Any) -> str:
    """Turn a fragment URL into an absolute one, like pagefind.js ``fullUrl``."""
    url = str(raw or "")
    if url.startswith(("https://", "http://")):
        return url
    return f"{SITE_BASE_URL}/{url.lstrip('/')}"


# ----- the WASM search core -----------------------------------------------------


def _load_wasmtime():
    """Import ``wasmtime`` lazily, so a broken install degrades to the fallback."""
    try:
        import wasmtime
    except ImportError as exc:
        raise PagefindUnavailable("the wasmtime package is not installed") from exc
    return wasmtime


class _WasmBackend:
    """The Pagefind WASM module, with the wasm-bindgen string glue."""

    def __init__(self, wasm_bytes: bytes) -> None:
        wasmtime = _load_wasmtime()
        self._errors = (wasmtime.WasmtimeError, wasmtime.Trap)
        try:
            engine = wasmtime.Engine()
            self._store = wasmtime.Store(engine)
            module = wasmtime.Module(engine, wasm_bytes)
            imports = {(i.module, i.name) for i in module.imports}
            if imports != _EXPECTED_IMPORTS:
                raise PagefindUnavailable(f"unexpected WASM imports {sorted(imports)}")
            linker = wasmtime.Linker(engine)
            linker.define_func(
                _IMPORT_MODULE,
                "__wbindgen_init_externref_table",
                wasmtime.FuncType([], []),
                self._init_externref_table,
            )
            instance = linker.instantiate(self._store, module)
            self._exports = instance.exports(self._store)
            self._memory = self._exports["memory"]
            self._exports["__wbindgen_start"](self._store)
        except self._errors as exc:
            raise PagefindUnavailable(f"WASM failed to load: {exc}") from exc

    def _init_externref_table(self) -> None:
        # The JS glue grows the table by four slots for undefined, null,
        # true and false. No exported call this module makes passes a JS
        # value, so the slots only have to exist.
        self._exports["__wbindgen_externrefs"].grow(self._store, 4, None)

    def _call(self, name: str, *args: Any) -> Any:
        try:
            return self._exports[name](self._store, *args)
        except self._errors as exc:
            raise PagefindUnavailable(f"WASM {name} failed: {exc}") from exc

    def _pass(self, data: bytes) -> tuple[int, int]:
        ptr = self._call("__wbindgen_malloc", len(data), 1)
        self._memory.write(self._store, data, ptr)
        return ptr, len(data)

    def _take_string(self, ret: Any) -> str:
        ptr, length = ret
        raw = bytes(self._memory.read(self._store, ptr, ptr + length))
        self._call("__wbindgen_free", ptr, length, 1)
        return raw.decode("utf-8")

    def _take_json(self, ret: Any, name: str) -> Any:
        try:
            return json.loads(self._take_string(ret))
        except (ValueError, UnicodeDecodeError) as exc:
            raise PagefindUnavailable(f"WASM {name} returned malformed JSON") from exc

    def init(self, meta: bytes) -> int:
        return self._call("init_pagefind", *self._pass(meta))

    def load_chunk(self, method: str, ptr: int, chunk: bytes) -> int:
        return self._call(method, ptr, *self._pass(chunk))

    def request(self, method: str, ptr: int, text: str | None = None) -> list:
        args = (ptr, *self._pass(text.encode())) if text is not None else (ptr,)
        value = self._take_json(self._call(method, *args), method)
        if not isinstance(value, list):
            raise PagefindUnavailable(f"WASM {method} did not return a list")
        return value

    def search(self, ptr: int, term: str, original: str, filters: str, exact: bool) -> dict:
        args: list[Any] = [ptr]
        for text in (term, original, filters, ""):
            args.extend(self._pass(text.encode()))
        value = self._take_json(self._call("search", *args, int(exact), 0), "search")
        if not isinstance(value, dict) or not isinstance(value.get("results"), list):
            raise PagefindUnavailable("WASM search reply lacks a 'results' list")
        return value

    def filters(self, ptr: int) -> dict:
        value = self._take_json(self._call("filters", ptr), "filters")
        if not isinstance(value, dict):
            raise PagefindUnavailable("WASM filters did not return an object")
        return value


class _Index:
    """One loaded index build: the WASM engine plus the chunks it has seen."""

    def __init__(self, entry: dict) -> None:
        self.version = entry["version"]
        language = entry["language"]
        self.hash = _checked_hash(language.get("hash"), "index hash")
        wasm_name = _checked_hash(language.get("wasm") or "unknown", "WASM name")
        self.include_characters = frozenset(entry.get("include_characters") or ())
        wasm, meta = _fetch_many([f"wasm.{wasm_name}.pagefind", f"pagefind.{self.hash}.pf_meta"])
        self.backend = _WasmBackend(decompress(wasm, "the WASM module"))
        self.ptr = self.backend.init(decompress(meta, "the index metadata"))
        self.loaded: dict[str, set[str]] = {"index": set(), "filter": set()}
        self.fragment_cache: dict[str, dict] = {}

    def _load(self, kind: str, hashes: list) -> None:
        """Fetch and load the index or filter chunks not loaded yet."""
        seen = self.loaded[kind]
        new = sorted({_checked_hash(h, f"{kind} chunk") for h in hashes if h} - seen)
        method = "load_index_chunk" if kind == "index" else "load_filter_chunk"
        for chunk_hash, data in zip(new, _fetch_many([f"{kind}/{h}.pf_{kind}" for h in new])):
            self.ptr = self.backend.load_chunk(method, self.ptr, decompress(data, f"{kind} chunk {chunk_hash}"))
            seen.add(chunk_hash)

    def _fragments(self, results: list[dict]) -> list[dict]:
        """Return the parsed fragment for each result, fetching only uncached ones."""
        hashes = [_checked_hash(r.get("p"), "fragment hash") for r in results]
        missing = sorted(set(hashes) - self.fragment_cache.keys())
        paths = [f"fragment/{h}.pf_fragment" for h in missing]
        if len(self.fragment_cache) + len(missing) > MAX_CACHED_FRAGMENTS:
            self.fragment_cache.clear()
        for fragment_hash, path, data in zip(missing, paths, _fetch_many(paths)):
            try:
                fragment = json.loads(decompress(data, path))
            except (ValueError, UnicodeDecodeError) as exc:
                raise PagefindUnavailable(f"{path} is not JSON") from exc
            if not isinstance(fragment, dict):
                raise PagefindUnavailable(f"{path} is not a JSON object")
            self.fragment_cache[fragment_hash] = fragment
        return [self.fragment_cache[h] for h in hashes]

    def _unknown_filters(self, filters: dict[str, str]) -> dict:
        """Name filter values the index does not have, with the known ones."""
        self._load("filter", self.backend.request("request_all_filter_indexes", self.ptr))
        known = self.backend.filters(self.ptr)
        unknown = {}
        for name, value in filters.items():
            values = known.get(name)
            if not isinstance(values, dict):
                unknown[name] = {"value": value, "known": sorted(known)}
            elif value not in values:
                unknown[name] = {"value": value, "known": sorted(values)}
        return unknown

    def query(self, query: str, limit: int, filters: dict[str, str]) -> dict:
        term, original, exact = normalize_term(query, self.include_characters)
        if not term:
            return {"total": 0, "results": [], "unknownFilters": {}}
        filters_json = json.dumps(filters)
        self._load("index", self.backend.request("request_indexes", self.ptr, term))
        self._load("filter", self.backend.request("request_filter_indexes", self.ptr, filters_json))
        results = [r for r in self.backend.search(self.ptr, term, original, filters_json, exact)["results"] if isinstance(r, dict)]

        # Results arrive ranked; fragments are fetched in batches of
        # ``limit`` until enough survive the aws-cdk-lib scope or the
        # fragment budget runs out.
        hits: list[dict] = []
        budget = min(len(results), limit * FRAGMENT_BUDGET_FACTOR)
        loaded = 0
        while len(hits) < limit and loaded < budget:
            batch = results[loaded : loaded + limit]
            loaded += len(batch)
            for result, fragment in zip(batch, self._fragments(batch)):
                url = _absolute_url(fragment.get("url"))
                if not url.startswith(RESULT_URL_PREFIX):
                    continue
                name, _, label = str((fragment.get("meta") or {}).get("title") or "").partition(_WEIGHT_MARKER)
                locations = [
                    (int(w["l"]), float(w.get("s", 0.0)))
                    for w in result.get("l") or []
                    if isinstance(w, dict) and isinstance(w.get("l"), int)
                ]
                content = str(fragment.get("content") or "")
                hits.append(
                    {
                        "title": name.strip(),
                        "kind_label": label.strip(),
                        "url": url,
                        "excerpt": plain_excerpt(content, excerpt_start(locations)),
                        "filters": fragment.get("filters") or {},
                    }
                )
                if len(hits) >= limit:
                    break

        unknown = self._unknown_filters(filters) if not results and filters else {}
        return {"total": len(results), "results": hits, "unknownFilters": unknown}


# ----- public entry point -------------------------------------------------------

_lock = threading.Lock()
_index: _Index | None = None


def _read_entry() -> dict:
    """Fetch ``pagefind-entry.json`` and pick the language index."""
    try:
        entry = json.loads(_fetch("pagefind-entry.json"))
    except ValueError as exc:
        raise PagefindUnavailable("pagefind-entry.json is not JSON") from exc
    version = str(entry.get("version") or "")
    if not version.startswith(SUPPORTED_VERSION_PREFIX):
        raise PagefindUnavailable(
            f"the site's Pagefind is version {version or 'unknown'}; this module "
            f"supports {SUPPORTED_VERSION_PREFIX}x only"
        )
    languages = entry.get("languages") or {}
    language = languages.get(LANGUAGE) or max(
        languages.values(), key=lambda lang: lang.get("page_count", 0), default=None
    )
    if not isinstance(language, dict):
        raise PagefindUnavailable("pagefind-entry.json lists no language index")
    return {"version": version, "language": language, "include_characters": entry.get("include_characters")}


def run_pagefind(
    query: str,
    *,
    limit: int,
    module: str | None = None,
    kind: str | None = None,
) -> dict[str, Any]:
    """Run one Pagefind query against the live CDK reference index.

    Args:
        query: Free-text search query.
        limit: Maximum results to return after the ``aws-cdk-lib`` scope.
        module: Pagefind ``module`` filter value, already normalized.
        kind: Pagefind ``kind`` filter value, such as ``construct``.

    Returns:
        Dict with ``total`` (matches before scoping and ``limit``),
        ``results`` (list of ``{title, kind_label, url, excerpt,
        filters}``) and ``unknownFilters`` (filter name to ``{value,
        known}`` when a filtered query matched nothing because the value
        is not in the index).

    Raises:
        PagefindUnavailable: ``wasmtime`` is missing, a fetch failed, the
            site's Pagefind version is unsupported, or the WASM returned
            something unexpected. The loaded engine is discarded, so the
            next call starts clean.
    """
    global _index
    filters = {name: value for name, value in (("module", module), ("kind", kind)) if value}
    with _lock:
        try:
            entry = _read_entry()
            index = _index
            if (
                index is None
                or index.hash != entry["language"].get("hash")
                or index.version != entry["version"]
                or len(index.loaded["index"]) > MAX_LOADED_CHUNKS
            ):
                index = _index = _Index(entry)
            return index.query(query, limit=max(0, int(limit)), filters=filters)
        except PagefindUnavailable:
            _index = None
            raise


__all__ = [
    "PAGEFIND_BASE_PATH",
    "PagefindUnavailable",
    "RESULT_URL_PREFIX",
    "decompress",
    "excerpt_start",
    "normalize_module",
    "normalize_term",
    "plain_excerpt",
    "run_pagefind",
]
