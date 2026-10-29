"""Refresh the four CDK construct-catalog steering files from the CDK docs.

Regenerates these ``.kiro/steering/`` catalogs from the live AWS CDK v2
API reference module overview pages
(``https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.<module>-readme.html``):

    cdk-connect.md       <- aws_cdk.aws_connect
    cdk-lex.md           <- aws_cdk.aws_lex
    cdk-q-in-connect.md  <- aws_cdk.aws_wisdom
    cdk-agentcore.md     <- aws_cdk.aws_bedrockagentcore

(The fifth catalog, ``cdk-iac.md``, is hand-authored prose — not a
construct list — and is intentionally left untouched by this script.)

Why the source moved: in October 2026 AWS retired the Sphinx Python
reference at ``cdk/api/v2/python`` for one VitePress site covering every
language at ``cdk/api/v2/docs``, with a 301 from each old page. The old
landing pages still answered 200 after the redirect, but the VitePress
markup links constructs as ``aws-cdk-lib.<module>.CfnX.html`` rather
than ``CfnX.html``, so the parser found 0 constructs. Because a refresh
drops constructs that vanish upstream, the next real run would have
emptied all four catalogs, 79 rows, and still exited 0. Two changes
close that: the parser matches the new href form, and ``refresh_one``
now treats a page that yields no constructs as a failed fetch, leaving
the catalog untouched and exiting 1.

Construct links point at ``...aws-cdk-lib.<module>.CfnX.html?lang=python``,
the address the old Python pages redirect to, so a click opens the
Python variant.

How it works (design C3, Requirement 4):

* It fetches each landing page via ``_doc_fetcher.fetch_with_fallback``,
  which 404-self-heals through the AWS docs search if AWS moves a page.
* It parses the page into the authoritative set of ``Cfn*`` constructs and
  their reference URLs, then **merges** that set with the curated one-line
  descriptions and ordering already in the steering file. Constructs that
  vanished upstream are dropped; brand-new constructs are appended (with a
  placeholder description) so an author notices them. In steady state the
  regenerated table is byte-identical to the existing one, so a no-diff
  refresh only bumps ``last_refreshed`` — exactly the contract
  ``refresh_connect_blocks.py`` follows.
* It updates ``last_refreshed``, ``construct_count``, and
  ``content_checksum`` together on every write (Req 4.3). The checksum is
  ``"sha256:" + sha256(table).hexdigest()[:16]`` over the full markdown
  table — the same convention as the other refresh scripts.
* ``--dry-run`` reports what would change and writes nothing (Req 4.4).
* If a source page cannot be fetched, or yields no ``Cfn*`` construct
  links, the failing URL is reported and that catalog file is left
  unchanged while the others still refresh (Req 4.5).

Run:
    uv run python .kiro/scripts/refresh_cdk_docs.py            # write
    uv run python .kiro/scripts/refresh_cdk_docs.py --dry-run  # preview

The pure helpers (``content_checksum``, ``parse_catalog_entries``,
``parse_construct_links``, ``merge_entries``, ``build_catalog_table``,
``regenerate_catalog_text``) are side-effect free and importable so the
property tests can exercise checksum integrity and write-discipline with a
mocked fetch, without any network access.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

# The freshness rule is the shared pure helper (task 3.3) — reuse it rather
# than redefining the 7-day window here.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from steering_freshness import is_stale  # noqa: E402

# This script lives at ``.kiro/scripts/`` — two levels under the
# repo root (scripts -> .kiro -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
STEERING_DIR = REPO_ROOT / ".kiro" / "steering"

# Root of the AWS CDK v2 API reference, one VitePress site for every
# language. Module overview pages live at ``<root>aws-cdk-lib.<module>-readme.html``
# and construct pages at ``<root>aws-cdk-lib.<module>.<Construct>.html``.
# Mirrors ``cdk_docs_mcp/cdk_docs/fetch.py``, which this script cannot
# import because it runs under the ``connect_knowledge_mcp`` project.
CDK_REF_ROOT = "https://docs.aws.amazon.com/cdk/api/v2/docs/"

# URL prefix the 404-self-healing resolver is allowed to accept hits from.
# Overrides ``_doc_fetcher``'s Connect-docs default so a moved CDK page
# resolves to another stable-library CDK page rather than a Connect page.
CDK_URL_PREFIX = "/cdk/api/v2/docs/aws-cdk-lib."

# Appended to construct links so they open the Python variant of the page.
PYTHON_VARIANT_QUERY = "?lang=python"


def _module(library: str) -> str:
    """``aws_cdk.aws_connect`` -> ``aws_connect``, the URL module segment."""
    return library.removeprefix("aws_cdk.")


# The four catalog files this script regenerates, each bound to its source
# construct library and module overview URL. ``cdk-iac.md`` is deliberately
# absent — it is hand-authored prose, not a generated construct list.
LIBRARY_URLS: dict[str, str] = {
    library: f"{CDK_REF_ROOT}aws-cdk-lib.{_module(library)}-readme.html"
    for library in (
        "aws_cdk.aws_connect",
        "aws_cdk.aws_lex",
        "aws_cdk.aws_wisdom",
        "aws_cdk.aws_bedrockagentcore",
    )
}

# Description used when a construct is present upstream but absent from the
# existing catalog (i.e. AWS added a new construct since the last refresh).
# It is intentionally obvious so a maintainer curates a real one-liner.
NEW_CONSTRUCT_DESCRIPTION = (
    "_(new construct — run `get_cdk_construct_doc` and curate a description)_"
)

# The catalog table header every generated file shares.
TABLE_HEADER = "| Construct | Description |"
TABLE_SEPARATOR = "| --- | --- |"


@dataclass(frozen=True)
class CatalogEntry:
    """One row of a CDK construct catalog (design M1)."""

    name: str
    url: str
    description: str


@dataclass(frozen=True)
class Catalog:
    """A catalog file bound to its source construct library."""

    filename: str
    library: str

    @property
    def source_url(self) -> str:
        return LIBRARY_URLS[self.library]

    @property
    def query_hint(self) -> str:
        # Bias the 404 resolver toward the right CDK reference page.
        return f"aws cdk aws-cdk-lib {_module(self.library)} module overview"


# The closed set of catalogs, in a stable order.
CATALOGS: tuple[Catalog, ...] = (
    Catalog("cdk-connect.md", "aws_cdk.aws_connect"),
    Catalog("cdk-lex.md", "aws_cdk.aws_lex"),
    Catalog("cdk-q-in-connect.md", "aws_cdk.aws_wisdom"),
    Catalog("cdk-agentcore.md", "aws_cdk.aws_bedrockagentcore"),
)


# ----- checksum (same convention as refresh_connect_blocks.py) -------------


def content_checksum(table_body: str) -> str:
    """Return ``"sha256:" + sha256(table_body).hexdigest()[:16]``.

    Deterministic over the rendered markdown table: identical table text
    yields an identical checksum, and any change to the table changes it
    (Req 4.3). This is the same convention every other refresh script uses.
    """
    digest = hashlib.sha256(table_body.encode("utf-8")).hexdigest()[:16]
    return f"sha256:{digest}"


# ----- parsing the live landing page --------------------------------------

def _construct_href_re(library: str) -> re.Pattern[str]:
    """Match a link to one of ``library``'s own ``Cfn*`` construct pages.

    The overview page links constructs as
    ``/cdk/api/v2/docs/aws-cdk-lib.aws_lex.CfnBot.html``. The pattern
    requires the module segment to equal ``library``'s, which rejects
    other modules (``aws_connectcampaigns``) and the
    ``aws-cdk-lib.interfaces.<module>.*`` reference pages. Requiring
    ``.html`` straight after the name rejects nested property-type pages
    such as ``CfnBot.AdvancedRecognitionSettingProperty.html``. A
    trailing ``?query`` or ``#anchor`` is tolerated.
    """
    module = re.escape(_module(library))
    return re.compile(
        rf"(?:^|/)aws-cdk-lib\.{module}\.(Cfn[A-Za-z0-9]+)\.html(?:[?#].*)?$"
    )


def _construct_url(library: str, construct: str) -> str:
    """Canonical CDK reference URL for a construct, Python variant."""
    return (
        f"{CDK_REF_ROOT}aws-cdk-lib.{_module(library)}.{construct}.html"
        f"{PYTHON_VARIANT_QUERY}"
    )


def parse_construct_links(html: str, library: str) -> list[tuple[str, str]]:
    """Extract ``(construct_name, url)`` pairs from a module overview page.

    Returns every ``Cfn*`` construct the page links to (excluding the
    ``*Props`` data-interface pages, which are not provisionable
    constructs), de-duplicated and sorted case-insensitively by name.
    Links into a different module are filtered out so only the library's
    own constructs are kept.
    """
    href_re = _construct_href_re(library)
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        match = href_re.search(anchor["href"].strip())
        if not match:
            continue
        name = match.group(1)
        if name.endswith("Props") or name in seen:
            continue
        seen.add(name)
        out.append((name, _construct_url(library, name)))
    return sorted(out, key=lambda pair: pair[0].casefold())


# ----- parsing the existing catalog table ---------------------------------

_ROW_LINK_RE = re.compile(r"\[(?P<name>[^\]]+)\]\((?P<url>[^)]+)\)")


def _split_row(line: str) -> list[str]:
    """Split a markdown table row into trimmed cells (tolerant of pipes)."""
    parts = [c.strip() for c in line.strip().split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _is_separator_row(line: str) -> bool:
    """True for a ``| --- | --- |`` style separator row."""
    return set(line.replace("|", "").strip()) <= {"-", " "} and "-" in line


def parse_catalog_entries(markdown: str) -> list[CatalogEntry]:
    """Parse an existing catalog file's table into ordered ``CatalogEntry``s.

    Finds the ``| Construct | Description |`` table and returns one entry
    per data row, preserving the file's existing order. A cell with a
    ``[name](url)`` link contributes both the name and URL; a plain-text
    name cell yields an empty URL. Rows outside the table are ignored.
    """
    lines = markdown.split("\n")
    entries: list[CatalogEntry] = []
    in_table = False
    for line in lines:
        if line.strip() == TABLE_HEADER:
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            break
        if _is_separator_row(line):
            continue
        cells = _split_row(line)
        if not cells:
            continue
        name_cell = cells[0]
        description = cells[1] if len(cells) > 1 else ""
        link = _ROW_LINK_RE.search(name_cell)
        if link:
            name = link.group("name").strip()
            url = link.group("url").strip()
        else:
            name = name_cell
            url = ""
        entries.append(CatalogEntry(name=name, url=url, description=description))
    return entries


# ----- merge + render ------------------------------------------------------


def merge_entries(
    live_links: list[tuple[str, str]],
    existing_entries: list[CatalogEntry],
) -> list[CatalogEntry]:
    """Merge the authoritative upstream construct set with curated text.

    * Constructs still present upstream keep their curated description and
      their existing position in the file (URL refreshed from upstream).
    * Constructs that disappeared upstream are dropped.
    * Constructs new upstream are appended (sorted case-insensitively) with
      a placeholder description so a maintainer notices and curates them.

    The result is therefore byte-stable when nothing changed upstream, so a
    no-diff refresh only bumps ``last_refreshed``.
    """
    live_url_by_name = dict(live_links)
    existing_names = {e.name for e in existing_entries}

    merged: list[CatalogEntry] = []
    for entry in existing_entries:
        url = live_url_by_name.get(entry.name)
        if url is None:
            continue  # construct removed upstream
        merged.append(
            CatalogEntry(name=entry.name, url=url, description=entry.description)
        )

    new_names = sorted(
        (name for name in live_url_by_name if name not in existing_names),
        key=str.casefold,
    )
    for name in new_names:
        merged.append(
            CatalogEntry(
                name=name,
                url=live_url_by_name[name],
                description=NEW_CONSTRUCT_DESCRIPTION,
            )
        )
    return merged


def render_table(entries: list[CatalogEntry]) -> str:
    """Render entries as the catalog markdown table (header + rows).

    The returned string is exactly what ``content_checksum`` hashes: the
    header row, the separator, then one row per entry, ``\\n``-joined with
    no trailing newline.
    """
    lines = [TABLE_HEADER, TABLE_SEPARATOR]
    for entry in entries:
        link = f"[{entry.name}]({entry.url})" if entry.url else entry.name
        lines.append(f"| {link} | {entry.description} |")
    return "\n".join(lines)


def build_catalog_table(
    html: str,
    library: str,
    existing_entries: list[CatalogEntry] | None = None,
) -> tuple[str, list[CatalogEntry]]:
    """Pure: fetched HTML + existing entries -> (rendered table, entries).

    This is the seam the property tests drive with mocked HTML: no network,
    no file I/O.
    """
    live_links = parse_construct_links(html, library)
    entries = merge_entries(live_links, existing_entries or [])
    return render_table(entries), entries


# ----- front-matter rewriting ----------------------------------------------


def _set_front_matter_field(text: str, key: str, value: str) -> str:
    """Replace the first ``<key>: ...`` line (front-matter scalar) in place.

    These keys (``last_refreshed`` / ``construct_count`` /
    ``content_checksum``) only ever appear in the YAML front matter, so a
    single first-occurrence replacement is safe.
    """
    pattern = re.compile(rf"(?m)^{re.escape(key)}:.*$")
    if not pattern.search(text):
        raise RuntimeError(f"front-matter field '{key}' not found")
    return pattern.sub(lambda _m: f"{key}: {value}", text, count=1)


def _set_front_matter_source_urls(text: str, url: str) -> str:
    """Point the front-matter ``source_urls:`` list at ``url`` alone.

    Every catalog has one source page. Rewriting the list, rather than
    swapping one known old URL for a new one, also repairs a file whose
    recorded source predates a site move, as all four did after the
    October 2026 CDK reference migration.
    """
    pattern = re.compile(r"(?m)^source_urls:\n(?:  - .*\n)+")
    if not pattern.search(text):
        raise RuntimeError("front-matter field 'source_urls' not found")
    return pattern.sub(lambda _m: f"source_urls:\n  - {url}\n", text, count=1)


def _replace_table(text: str, new_table: str) -> str:
    """Splice ``new_table`` over the existing catalog table, keeping prose."""
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if line.strip() == TABLE_HEADER:
            start = i
            break
    if start is None:
        raise RuntimeError("catalog table header not found")
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    new_lines = lines[:start] + new_table.split("\n") + lines[end:]
    return "\n".join(new_lines)


def front_matter_last_refreshed(text: str) -> date | None:
    """Read the ``last_refreshed`` date from a catalog's front matter."""
    match = re.search(r"(?m)^last_refreshed:\s*(\S+)\s*$", text)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def regenerate_catalog_text(
    existing_text: str,
    html: str,
    library: str,
    *,
    today: date,
    source_url: str | None = None,
    final_url: str | None = None,
) -> tuple[str, list[CatalogEntry], str]:
    """Produce the regenerated file text from existing text + fetched HTML.

    Returns ``(new_text, entries, checksum)``. Pure and side-effect free:
    it neither fetches nor writes, so the property tests can call it with
    mocked HTML. ``last_refreshed``, ``construct_count`` and
    ``content_checksum`` are all updated together (Req 4.3). The
    front-matter ``source_urls`` is set to the page actually fetched:
    ``final_url`` when given (it differs from ``source_url`` after a 404
    self-heal), else ``source_url``.
    """
    existing_entries = parse_catalog_entries(existing_text)
    table, entries = build_catalog_table(html, library, existing_entries)
    checksum = content_checksum(table)

    new_text = _replace_table(existing_text, table)
    new_text = _set_front_matter_field(new_text, "last_refreshed", today.isoformat())
    new_text = _set_front_matter_field(new_text, "construct_count", str(len(entries)))
    new_text = _set_front_matter_field(new_text, "content_checksum", checksum)

    live_source = final_url or source_url
    if live_source:
        new_text = _set_front_matter_source_urls(new_text, live_source)

    return new_text, entries, checksum


# ----- fetch injection -----------------------------------------------------


def _default_fetcher(url: str, query_hint: str) -> tuple[str, str]:
    """Fetch ``url`` via the shared 404-self-healing fetcher.

    Imported lazily so the pure helpers above stay importable (and the
    property tests stay network-free) even where ``_doc_fetcher`` or its
    ``requests``/``connect_knowledge`` dependencies are unavailable.
    """
    from _doc_fetcher import fetch_with_fallback  # lazy: keeps helpers pure

    return fetch_with_fallback(url, query_hint=query_hint, url_prefix=CDK_URL_PREFIX)


# ----- orchestration -------------------------------------------------------


@dataclass
class RefreshResult:
    """Outcome of refreshing a single catalog file."""

    filename: str
    library: str
    source_url: str
    status: str  # "written" | "unchanged" | "would-write" | "would-skip" | "failed"
    error: str | None = None
    construct_count: int | None = None
    checksum: str | None = None
    was_stale: bool | None = None
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status != "failed"


def refresh_one(
    catalog: Catalog,
    steering_dir: Path,
    *,
    fetcher=_default_fetcher,
    today: date | None = None,
    dry_run: bool = False,
    verbose: bool = True,
) -> RefreshResult:
    """Refresh a single catalog file. Never raises on a fetch failure.

    On a fetch failure the failing source URL is reported and the file is
    left untouched (Req 4.5). A fetched page with no ``Cfn*`` construct
    links counts as a failure too: every in-scope module has at least
    one, so zero means the layout changed, and merging an empty set
    would drop every row. In ``dry_run`` mode nothing is written
    (Req 4.4).
    """
    today = today or date.today()
    path = steering_dir / catalog.filename
    source_url = catalog.source_url

    existing_text = path.read_text(encoding="utf-8")
    last_refreshed = front_matter_last_refreshed(existing_text)
    was_stale = is_stale(last_refreshed, today) if last_refreshed else None

    if verbose:
        print(f"fetching {source_url}", file=sys.stderr)
    try:
        final_url, html = fetcher(source_url, catalog.query_hint)
    except Exception as exc:  # noqa: BLE001 — any fetch error is a Req 4.5 case
        print(
            f"  ERROR fetching {source_url}: {exc}\n"
            f"  leaving {catalog.filename} unchanged",
            file=sys.stderr,
        )
        return RefreshResult(
            filename=catalog.filename,
            library=catalog.library,
            source_url=source_url,
            status="failed",
            error=str(exc),
            was_stale=was_stale,
        )

    if not parse_construct_links(html, catalog.library):
        error = (
            f"no {_module(catalog.library)} Cfn* construct links found on "
            f"{final_url}; the page layout is not recognized"
        )
        print(
            f"  ERROR: {error}\n  leaving {catalog.filename} unchanged",
            file=sys.stderr,
        )
        return RefreshResult(
            filename=catalog.filename,
            library=catalog.library,
            source_url=final_url,
            status="failed",
            error=error,
            was_stale=was_stale,
        )

    new_text, entries, checksum = regenerate_catalog_text(
        existing_text,
        html,
        catalog.library,
        today=today,
        source_url=source_url,
        final_url=final_url,
    )

    existing_entries = parse_catalog_entries(existing_text)
    existing_names = {e.name for e in existing_entries}
    new_names = {e.name for e in entries}
    added = sorted(new_names - existing_names, key=str.casefold)
    removed = sorted(existing_names - new_names, key=str.casefold)

    table_changed = bool(added or removed) or any(
        e1.description != e2.description or e1.url != e2.url
        for e1, e2 in zip(existing_entries, entries)
    )

    if verbose:
        print(
            f"  parsed {len(entries)} constructs "
            f"(+{len(added)} / -{len(removed)})",
            file=sys.stderr,
        )

    if dry_run:
        return RefreshResult(
            filename=catalog.filename,
            library=catalog.library,
            source_url=final_url,
            status="would-write" if table_changed else "would-skip",
            construct_count=len(entries),
            checksum=checksum,
            was_stale=was_stale,
            added=added,
            removed=removed,
        )

    path.write_text(new_text, encoding="utf-8")
    if verbose:
        print(f"  wrote {path} ({len(entries)} constructs)", file=sys.stderr)
    return RefreshResult(
        filename=catalog.filename,
        library=catalog.library,
        source_url=final_url,
        status="written" if table_changed else "unchanged",
        construct_count=len(entries),
        checksum=checksum,
        was_stale=was_stale,
        added=added,
        removed=removed,
    )


def refresh_all(
    catalogs=CATALOGS,
    steering_dir: Path = STEERING_DIR,
    *,
    fetcher=_default_fetcher,
    today: date | None = None,
    dry_run: bool = False,
    verbose: bool = True,
) -> list[RefreshResult]:
    """Refresh every catalog, isolating per-file fetch failures (Req 4.5)."""
    today = today or date.today()
    results: list[RefreshResult] = []
    for catalog in catalogs:
        results.append(
            refresh_one(
                catalog,
                steering_dir,
                fetcher=fetcher,
                today=today,
                dry_run=dry_run,
                verbose=verbose,
            )
        )
    return results


def _print_summary(results: list[RefreshResult], *, dry_run: bool) -> None:
    """Print a human-readable per-file summary to stdout."""
    heading = "Dry run — no files written:" if dry_run else "Refresh summary:"
    print(heading)
    for r in results:
        if r.status == "failed":
            print(f"  [FAILED]  {r.filename}: {r.error}  ({r.source_url})")
            continue
        stale = "" if r.was_stale is None else (" was-stale" if r.was_stale else "")
        churn = ""
        if r.added:
            churn += f" +{len(r.added)} ({', '.join(r.added)})"
        if r.removed:
            churn += f" -{len(r.removed)} ({', '.join(r.removed)})"
        print(
            f"  [{r.status:>11}]  {r.filename}: {r.construct_count} constructs, "
            f"{r.checksum}{stale}{churn}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the changes that would be made without writing any file.",
    )
    parser.add_argument(
        "--steering-dir",
        type=Path,
        default=STEERING_DIR,
        help=f"Steering directory (default: {STEERING_DIR}).",
    )
    args = parser.parse_args(argv)

    results = refresh_all(
        steering_dir=args.steering_dir,
        dry_run=args.dry_run,
    )

    print("", file=sys.stderr)
    _print_summary(results, dry_run=args.dry_run)

    failures = [r for r in results if not r.ok]
    if failures:
        print(
            f"\n{len(failures)} of {len(results)} source page(s) failed; "
            "those catalogs were left unchanged.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
