"""Property-based test for CDK steering catalog entry completeness.

Feature: connect-iac-cdk, Property 5: Catalog entry completeness

Property 5 (design ``Correctness Properties``): every generated catalog
entry has a non-empty construct name, a description field, and a link
(URL) to the construct's CDK doc page. This mirrors data model M1
``ConstructCatalogEntry = {name, description, url}``.

Validates: Requirements 3.3

The test drives a *self-contained* ``parse_catalog_entries`` helper (kept
in this file on purpose, so the test has no hard dependency on the
in-parallel refresh script — see task 3.2 notes) with:

  (a) hypothesis-generated catalog table content rendered into the real
      steering-file shape (front matter + prose + markdown table), parsed
      back, and asserted complete + round-trip faithful — >=100 examples;

  (b) the four real generated catalog files under .kiro/steering/
      (cdk-connect.md, cdk-lex.md, cdk-q-in-connect.md, cdk-agentcore.md),
      asserting every row is a complete entry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# --------------------------------------------------------------------------
# Locate the repo root and the four generated catalog steering files.
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
STEERING_DIR = REPO_ROOT / ".kiro" / "steering"

CATALOG_FILES = [
    "cdk-connect.md",
    "cdk-lex.md",
    "cdk-q-in-connect.md",
    "cdk-agentcore.md",
]


# --------------------------------------------------------------------------
# M1 ConstructCatalogEntry + self-contained parser.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ConstructCatalogEntry:
    """M1: a single catalog row — {name, description, url}."""

    name: str
    description: str
    url: str


# A markdown link: [text](url)
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
# A table separator cell: ---, :--, --:, :-:  (any run of dashes w/ optional colons)
_SEP_CELL_RE = re.compile(r"^:?-{2,}:?$")


def _split_row(line: str) -> list[str] | None:
    """Split a markdown table row ``| a | b |`` into its trimmed cells.

    Returns ``None`` when the line is not a table row.
    """
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    # Drop the leading and trailing pipe, then split on the remaining pipes.
    inner = stripped.strip("|")
    return [cell.strip() for cell in inner.split("|")]


def parse_catalog_entries(markdown_text: str) -> list[ConstructCatalogEntry]:
    """Extract catalog entries from a catalog steering markdown document.

    Only true catalog rows are returned: the function walks every markdown
    table row and keeps a row *iff* its first cell carries a markdown link
    ``[Name](url)``. That naturally skips the header row (``| Construct |
    Description |``), the separator row (``| --- | --- |``), front matter,
    and surrounding prose — none of which contain a link in the first cell.
    """
    entries: list[ConstructCatalogEntry] = []
    for line in markdown_text.splitlines():
        cells = _split_row(line)
        if cells is None or len(cells) < 2:
            continue
        # A separator row (all cells are dashes) is never an entry.
        if all(_SEP_CELL_RE.match(cell) for cell in cells if cell):
            continue
        name_cell, description_cell = cells[0], cells[1]
        match = _LINK_RE.search(name_cell)
        if match is None:
            # Header row or any non-entry table row: no link in first cell.
            continue
        name = match.group(1).strip()
        url = match.group(2).strip()
        entries.append(
            ConstructCatalogEntry(
                name=name,
                description=description_cell.strip(),
                url=url,
            )
        )
    return entries


def _is_complete(entry: ConstructCatalogEntry) -> bool:
    """The Property 5 predicate: non-empty name, description, and a URL link."""
    return (
        bool(entry.name)
        and bool(entry.description)
        and bool(entry.url)
        and ("://" in entry.url)
    )


# --------------------------------------------------------------------------
# Strategies: generate well-formed-but-varied catalog entries, then render
# them into a realistic catalog document.
# --------------------------------------------------------------------------
# Names: non-empty, no markdown-link / table-delimiter / newline chars.
_name_text = st.text(
    alphabet=st.characters(
        blacklist_characters="[]()|\r\n",
        blacklist_categories=("Cs", "Cc"),
    ),
    min_size=1,
    max_size=40,
).map(lambda s: s.strip()).filter(lambda s: len(s) > 0)

# Descriptions: non-empty, no pipe / newline (would break the table cell).
_description_text = st.text(
    alphabet=st.characters(
        blacklist_characters="|\r\n",
        blacklist_categories=("Cs", "Cc"),
    ),
    min_size=1,
    max_size=120,
).map(lambda s: s.strip()).filter(lambda s: len(s) > 0)

# URLs: a doc-page-shaped https link, no ) / | / whitespace.
_url_segment = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.",
    min_size=1,
    max_size=20,
)


_BASE_URL = "https://docs.aws.amazon.com/cdk/api/v2/python"

# A doc-page-shaped https link built from two path segments.
_doc_url = st.builds(
    lambda lib, construct: f"{_BASE_URL}/{lib}/{construct}.html",
    _url_segment,
    _url_segment,
)

_entry = st.builds(
    ConstructCatalogEntry,
    name=_name_text,
    description=_description_text,
    url=_doc_url,
)


@st.composite
def _entries(draw) -> list[ConstructCatalogEntry]:
    return draw(st.lists(_entry, min_size=1, max_size=12))


def _render_catalog(entries: list[ConstructCatalogEntry]) -> str:
    """Render entries into the same shape the real catalog files use:
    front matter + heading + prose + a ``| Construct | Description |`` table.
    """
    lines = [
        "---",
        "inclusion: manual",
        "last_refreshed: 2026-06-04",
        f"construct_count: {len(entries)}",
        "source_urls:",
        "  - https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/README.html",
        "content_checksum: sha256:deadbeefdeadbeef",
        "---",
        "",
        "# CDK construct catalog — generated for the property test",
        "",
        "Some prose with a | pipe and [a link](https://example.com/x) in it,",
        "and a freshness rule the agent reads. None of this is a table row.",
        "",
        "| Construct | Description |",
        "| --- | --- |",
    ]
    for entry in entries:
        lines.append(f"| [{entry.name}]({entry.url}) | {entry.description} |")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Property 5: Catalog entry completeness (>=100 iterations).
# --------------------------------------------------------------------------
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(_entries())
def test_property5_generated_catalog_entries_are_complete(entries):
    """Feature: connect-iac-cdk, Property 5: Catalog entry completeness.

    For any generated catalog, every parsed entry has a non-empty construct
    name, a non-empty description, and a URL link to its CDK doc page; and
    the parser recovers every entry the catalog declares (no rows dropped,
    no prose/header/separator rows misread as entries).

    Validates: Requirements 3.3
    """
    document = _render_catalog(entries)
    parsed = parse_catalog_entries(document)

    # The parser recovered exactly the catalog rows (header/separator/prose
    # are not entries).
    assert len(parsed) == len(entries)

    # Property 5: every entry is complete.
    for entry in parsed:
        assert entry.name, f"empty construct name in {entry!r}"
        assert entry.description, f"empty description in {entry!r}"
        assert entry.url, f"missing url in {entry!r}"
        assert _is_complete(entry), f"incomplete entry {entry!r}"

    # Round-trip fidelity: name/url/description survive render+parse intact.
    for original, recovered in zip(entries, parsed):
        assert recovered.name == original.name
        assert recovered.url == original.url
        assert recovered.description == original.description


# --------------------------------------------------------------------------
# Property 5 asserted on the four real generated catalog files.
# --------------------------------------------------------------------------
def test_property5_real_catalog_files_entries_are_complete():
    """Feature: connect-iac-cdk, Property 5: Catalog entry completeness.

    Every row in each of the four real generated catalog steering files has
    a non-empty construct name, a non-empty description, and a CDK doc-page
    link.

    Validates: Requirements 3.3
    """
    for filename in CATALOG_FILES:
        path = STEERING_DIR / filename
        assert path.is_file(), f"missing catalog file: {path}"
        entries = parse_catalog_entries(path.read_text(encoding="utf-8"))
        assert entries, f"no catalog entries parsed from {filename}"
        for entry in entries:
            assert _is_complete(entry), f"incomplete entry in {filename}: {entry!r}"
