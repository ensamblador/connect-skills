"""Unit tests for ``cdk_docs.pagefind``, the in-process Pagefind search.

Offline: the HTTP layer (``pagefind._fetch``) serves canned files and the
WASM backend is replaced by ``FakeBackend``, so these run without network
or ``wasmtime``. They pin what a regression would make silent or unsafe:
the ports of ``pagefind.js`` query preparation and excerpts, the file
envelope, hash checks before a hash goes into a fetch path, result
scoping, engine reuse and rebuild, and that every failure raises
``PagefindUnavailable`` instead of returning an empty result that reads
like a real one. The real WASM round trip is in ``test_live_fetch.py``.

Run with (from ``cdk_docs_mcp/``)::

    uv run --with pytest pytest cdk_docs/test_pagefind.py
"""

from __future__ import annotations

import gzip
import json

import pytest

from cdk_docs import pagefind

SIG = b"pagefind_dcd"
CONNECT_URL = "/v2/docs/aws-cdk-lib.aws_connect.CfnContactFlow.html"


def _packed(payload: bytes) -> bytes:
    """A Pagefind file as served: gzip of signature + payload."""
    return gzip.compress(SIG + payload)


def _entry(version="1.5.2", hash_="en-us_abc123", **extra) -> bytes:
    language = {"hash": hash_, "wasm": "en-us", "page_count": 10, **extra}
    return json.dumps({"version": version, "languages": {"en-us": language}, "include_characters": ["_"]}).encode()


def _fragment(url, title="CfnContactFlow ___END_PAGEFIND_WEIGHT___ L1 construct", content="", filters=None) -> bytes:
    body = {"url": url, "meta": {"title": title}, "content": content, "filters": filters or {}}
    return _packed(json.dumps(body).encode())


class FakeBackend:
    """Stands in for ``_WasmBackend``; records calls, returns canned replies."""

    instances: list["FakeBackend"] = []
    search_results: list[dict] = []
    known_filters: dict = {}

    def __init__(self, wasm_bytes: bytes) -> None:
        assert wasm_bytes == b"wasm"
        self.calls: list[tuple] = []
        FakeBackend.instances.append(self)

    def init(self, meta: bytes) -> int:
        self.calls.append(("init", meta))
        return 1

    def load_chunk(self, method: str, ptr: int, chunk: bytes) -> int:
        self.calls.append((method, chunk))
        return ptr + 1

    def request(self, method: str, ptr: int, text: str | None = None) -> list:
        self.calls.append((method, text))
        if method == "request_indexes":
            return ["idx1"]
        if method == "request_all_filter_indexes":
            return ["flt1"]
        return ["flt1"] if text and text != "{}" else []

    def search(self, ptr: int, term: str, original: str, filters: str, exact: bool) -> dict:
        self.calls.append(("search", term, original, filters, exact))
        return {"results": list(FakeBackend.search_results)}

    def filters(self, ptr: int) -> dict:
        self.calls.append(("filters",))
        return FakeBackend.known_filters


@pytest.fixture
def site(monkeypatch):
    """Serve canned Pagefind files and swap in ``FakeBackend``."""
    files: dict[str, bytes] = {
        "pagefind-entry.json": _entry(),
        "wasm.en-us.pagefind": _packed(b"wasm"),
        "pagefind.en-us_abc123.pf_meta": _packed(b"meta"),
        "index/idx1.pf_index": _packed(b"chunk-1"),
        "filter/flt1.pf_filter": _packed(b"filter-1"),
    }
    fetched: list[str] = []

    def fake_fetch(path: str) -> bytes:
        fetched.append(path)
        if path not in files:
            raise pagefind.PagefindUnavailable(f"GET {path} failed: 404")
        return files[path]

    FakeBackend.instances = []
    FakeBackend.search_results = []
    FakeBackend.known_filters = {}
    monkeypatch.setattr(pagefind, "_fetch", fake_fetch)
    monkeypatch.setattr(pagefind, "_WasmBackend", FakeBackend)
    monkeypatch.setattr(pagefind, "_index", None)
    return files, fetched


# ----- pure helpers -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("aws-connect", "aws-connect"),
        ("aws_connect", "aws-connect"),
        ("aws_cdk.aws_bedrockagentcore", "aws-bedrockagentcore"),
        (" AWS_CDK.aws_lex ", "aws-lex"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_module(given, expected) -> None:
    assert pagefind.normalize_module(given) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Contact  Flow", ("contact flow", "contact flow", False)),
        ("Café, Señor!", ("cafe senor", "café señor", False)),
        ('"bot alias"', ("bot alias", "bot alias", True)),
        ("contact-flow", ("contactflow", "contactflow", False)),
        ("aws_connect", ("aws_connect", "aws_connect", False)),
        ("¿?", ("", "", False)),
    ],
)
def test_normalize_term_mirrors_pagefind_js(raw, expected) -> None:
    assert pagefind.normalize_term(raw, frozenset({"_"})) == expected


def test_excerpt_start_finds_the_densest_window() -> None:
    assert pagefind.excerpt_start([]) == 0
    assert pagefind.excerpt_start([(3, 1.0)], length=30) == 0  # shorter than the window
    locations = [(2, 1.0), (40, 5.0), (41, 5.0), (42, 5.0)]
    start = pagefind.excerpt_start(locations, length=5)
    assert 37 <= start <= 42


def test_plain_excerpt_clamps_to_the_text() -> None:
    content = " ".join(f"w{i}" for i in range(10))
    assert pagefind.plain_excerpt(content, 0, 3) == "w0 w1 w2"
    assert pagefind.plain_excerpt(content, 9, 3) == "w7 w8 w9"
    assert pagefind.plain_excerpt("a b", 5, 30) == "a b"
    assert pagefind.plain_excerpt("一\u200b二\u200b三", 0, 2) == "一二"


def test_decompress_envelope() -> None:
    assert pagefind.decompress(SIG + b"x", "f") == b"x"
    assert pagefind.decompress(_packed(b"y"), "f") == b"y"
    with pytest.raises(pagefind.PagefindUnavailable, match="lacks the Pagefind signature"):
        pagefind.decompress(gzip.compress(b"no signature"), "f")
    with pytest.raises(pagefind.PagefindUnavailable, match="neither gzip"):
        pagefind.decompress(b"garbage", "f")


def test_missing_wasmtime_raises_unavailable(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def no_wasmtime(name, *args, **kwargs):
        if name == "wasmtime":
            raise ImportError("no module named wasmtime")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_wasmtime)
    with pytest.raises(pagefind.PagefindUnavailable, match="wasmtime package is not installed"):
        pagefind._load_wasmtime()


# ----- run_pagefind orchestration ---------------------------------------------------


def test_scopes_formats_and_limits_results(site) -> None:
    files, _ = site
    files["fragment/f1.pf_fragment"] = _fragment(
        CONNECT_URL, content="CfnContactFlow L1 construct Specifies a flow.", filters={"kind": ["construct"]}
    )
    files["fragment/f2.pf_fragment"] = _fragment("/v2/docs/@aws-cdk_aws-x-alpha.Thing.html", title="Thing")
    files["fragment/f3.pf_fragment"] = _fragment("/v2/docs/aws-cdk-lib.aws_lex.CfnBot.html", title="CfnBot")
    FakeBackend.search_results = [
        {"p": "f1", "s": 9.0, "l": [{"w": 24, "s": 1.0, "l": 0}]},
        {"p": "f2", "s": 8.0, "l": []},
        {"p": "f3", "s": 7.0, "l": []},
    ]

    reply = pagefind.run_pagefind("Contact Flow", limit=1)

    assert reply["total"] == 3
    assert reply["unknownFilters"] == {}
    assert reply["results"] == [
        {
            "title": "CfnContactFlow",
            "kind_label": "L1 construct",
            "url": "https://docs.aws.amazon.com/cdk/api" + CONNECT_URL,
            "excerpt": "CfnContactFlow L1 construct Specifies a flow.",
            "filters": {"kind": ["construct"]},
        }
    ]
    search_call = next(c for c in FakeBackend.instances[0].calls if c[0] == "search")
    assert search_call == ("search", "contact flow", "contact flow", "{}", False)


def test_out_of_scope_hits_are_skipped(site) -> None:
    files, _ = site
    files["fragment/f1.pf_fragment"] = _fragment("/v2/docs/@aws-cdk_aws-x-alpha.Thing.html", title="Alpha")
    files["fragment/f2.pf_fragment"] = _fragment(CONNECT_URL)
    FakeBackend.search_results = [{"p": "f1", "s": 2.0}, {"p": "f2", "s": 1.0}]

    reply = pagefind.run_pagefind("thing", limit=1)

    assert [r["title"] for r in reply["results"]] == ["CfnContactFlow"]


def test_filters_are_passed_and_filter_chunks_loaded(site) -> None:
    files, _ = site
    files["fragment/f1.pf_fragment"] = _fragment(CONNECT_URL)
    FakeBackend.search_results = [{"p": "f1", "s": 1.0}]

    pagefind.run_pagefind("flow", limit=1, module="aws-connect", kind="construct")

    calls = FakeBackend.instances[0].calls
    assert ("load_filter_chunk", b"filter-1") in calls
    search_call = next(c for c in calls if c[0] == "search")
    assert json.loads(search_call[3]) == {"module": "aws-connect", "kind": "construct"}


def test_unknown_filter_reported_only_when_nothing_matches(site) -> None:
    FakeBackend.search_results = []
    FakeBackend.known_filters = {"module": {"aws-connect": 40, "aws-lex": 4}, "kind": {"construct": 9}}

    reply = pagefind.run_pagefind("flow", limit=3, module="aws-conect", kind="construct")

    assert reply["results"] == []
    assert reply["unknownFilters"] == {"module": {"value": "aws-conect", "known": ["aws-connect", "aws-lex"]}}


def test_empty_term_short_circuits(site) -> None:
    reply = pagefind.run_pagefind("¿?", limit=3)
    assert reply == {"total": 0, "results": [], "unknownFilters": {}}
    assert not any(c[0] == "search" for c in FakeBackend.instances[0].calls)


def test_engine_is_reused_then_rebuilt_on_a_new_index_build(site) -> None:
    files, fetched = site
    files["fragment/f1.pf_fragment"] = _fragment(CONNECT_URL)
    FakeBackend.search_results = [{"p": "f1", "s": 1.0}]

    pagefind.run_pagefind("flow", limit=1)
    pagefind.run_pagefind("flow", limit=1)
    assert len(FakeBackend.instances) == 1
    # Chunks and fragments are fetched once per build.
    assert fetched.count("index/idx1.pf_index") == 1
    assert fetched.count("fragment/f1.pf_fragment") == 1

    files["pagefind-entry.json"] = _entry(hash_="en-us_def456")
    files["pagefind.en-us_def456.pf_meta"] = _packed(b"meta-2")
    pagefind.run_pagefind("flow", limit=1)
    assert len(FakeBackend.instances) == 2
    assert FakeBackend.instances[1].calls[0] == ("init", b"meta-2")


def test_unsupported_version_raises_before_loading_wasm(site) -> None:
    files, fetched = site
    files["pagefind-entry.json"] = _entry(version="2.0.0")

    with pytest.raises(pagefind.PagefindUnavailable, match="version 2.0.0"):
        pagefind.run_pagefind("flow", limit=1)
    assert fetched == ["pagefind-entry.json"]


def test_invalid_hash_from_the_index_is_refused(site) -> None:
    FakeBackend.search_results = [{"p": "../../evil", "s": 1.0}]

    with pytest.raises(pagefind.PagefindUnavailable, match="invalid fragment hash"):
        pagefind.run_pagefind("flow", limit=1)


def test_fetch_failure_raises_and_discards_the_engine(site) -> None:
    FakeBackend.search_results = [{"p": "missing", "s": 1.0}]

    with pytest.raises(pagefind.PagefindUnavailable, match="fragment/missing.pf_fragment"):
        pagefind.run_pagefind("flow", limit=1)
    assert pagefind._index is None
