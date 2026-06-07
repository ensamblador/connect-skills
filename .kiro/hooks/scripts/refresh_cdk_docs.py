"""Refresh the four CDK construct-catalog steering files from the CDK docs.

Regenerates these ``.kiro/steering/`` catalogs from the live AWS CDK
(v2, Python) API reference landing pages:

    cdk-connect.md       <- aws_cdk.aws_connect    (.../aws_cdk.aws_connect/README.html)
    cdk-lex.md           <- aws_cdk.aws_lex        (.../aws_cdk.aws_lex.html)
    cdk-q-in-connect.md  <- aws_cdk.aws_wisdom     (.../aws_cdk.aws_wisdom.html)
    cdk-agentcore.md     <- aws_cdk.aws_bedrockagentcore (.../aws_cdk.aws_bedrockagentcore.html)

(The fifth catalog, ``cdk-iac.md``, is hand-authored prose — not a
construct list — and is intentionally left untouched by this script.)

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
* If a source page cannot be fetched, the failing URL is reported and that
  catalog file is left unchanged while the others still refresh (Req 4.5).

Run:
    uv run python .kiro/hooks/scripts/refresh_cdk_docs.py            # write
    uv run python .kiro/hooks/scripts/refresh_cdk_docs.py --dry-run  # preview

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

# This script lives at ``.kiro/hooks/scripts/`` — three levels under the
# repo root (scripts -> hooks -> .kiro -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[3]
STEERING_DIR = REPO_ROOT / ".kiro" / "steering"

# Root of the AWS CDK v2 Python API reference. Per-construct pages live at
# ``<root>/<library>/<Construct>.html`` for every library, even though the
# library landing pages themselves are heterogeneous (``aws_connect`` lands
# on ``README.html`` while the rest are flat ``.html`` pages).
CDK_PYTHON_REF_ROOT = "https://docs.aws.amazon.com/cdk/api/v2/python/"

# URL prefix the 404-self-healing resolver is allowed to accept hits from.
# Overrides ``_doc_fetcher``'s Connect-docs default so a moved CDK page
# resolves to another CDK page rather than a Connect page.
CDK_URL_PREFIX = "/cdk/api/v2/python"

# The four catalog files this script regenerates, each bound to its source
# construct library and landing-page URL. ``cdk-iac.md`` is deliberately
# absent — it is hand-authored prose, not a generated construct list.
LIBRARY_URLS: dict[str, str] = {
    "aws_cdk.aws_connect": f"{CDK_PYTHON_REF_ROOT}aws_cdk.aws_connect/README.html",
    "aws_cdk.aws_lex": f"{CDK_PYTHON_REF_ROOT}aws_cdk.aws_lex.html",
    "aws_cdk.aws_wisdom": f"{CDK_PYTHON_REF_ROOT}aws_cdk.aws_wisdom.html",
    "aws_cdk.aws_bedrockagentcore": f"{CDK_PYTHON_REF_ROOT}aws_cdk.aws_bedrockagentcore.html",
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
        return f"aws cdk python {self.library} construct reference"


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

# Matches a link to a construct page, whether the href is bare
# (``CfnBot.html``, as on the aws_connect README) or path-qualified
# (``aws_cdk.aws_lex/CfnBot.html``). Trailing ``#anchor`` is tolerated.
_CFN_HREF_RE = re.compile(r"(?:^|/)(Cfn[A-Za-z0-9]+)\.html(?:#.*)?$")


def _construct_url(library: str, construct: str) -> str:
    """Canonical CDK reference URL for a construct in a library."""
    return f"{CDK_PYTHON_REF_ROOT}{library}/{construct}.html"


def parse_construct_links(html: str, library: str) -> list[tuple[str, str]]:
    """Extract ``(construct_name, url)`` pairs for a library landing page.

    Returns every ``Cfn*`` construct the page links to (excluding the
    ``*Props`` data-interface pages, which are not provisionable
    constructs), de-duplicated and sorted case-insensitively by name.
    Cross-library links (e.g. a "see also" pointing at a different
    ``aws_cdk.aws_*`` module) are filtered out so only the library's own
    constructs are kept.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        match = _CFN_HREF_RE.search(href)
        if not match:
            continue
        name = match.group(1)
        if name.endswith("Props"):
            continue
        # Reject links that belong to a *different* construct library.
        clean = href.split("#", 1)[0]
        prefix = clean[: -len(f"{name}.html")].rstrip("/")
        if prefix and not prefix.endswith(library):
            continue
        if name in seen:
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
    ``content_checksum`` are all updated together (Req 4.3). When the source
    page moved (``final_url`` differs from ``source_url``), the front-matter
    source URL is updated to the live location.
    """
    existing_entries = parse_catalog_entries(existing_text)
    table, entries = build_catalog_table(html, library, existing_entries)
    checksum = content_checksum(table)

    new_text = _replace_table(existing_text, table)
    new_text = _set_front_matter_field(new_text, "last_refreshed", today.isoformat())
    new_text = _set_front_matter_field(new_text, "construct_count", str(len(entries)))
    new_text = _set_front_matter_field(new_text, "content_checksum", checksum)

    if source_url and final_url and final_url != source_url:
        new_text = new_text.replace(source_url, final_url, 1)

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
    left untouched (Req 4.5). In ``dry_run`` mode nothing is written
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
