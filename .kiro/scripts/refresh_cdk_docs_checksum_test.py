"""Property-based test for refresh checksum integrity.

Feature: connect-iac-cdk, Property 6: Refresh checksum integrity

Validates: Requirements 4.3

The property under test (design "Property 6: Refresh checksum integrity",
design C3):

    *For any* catalog content, the ``content_checksum`` SHALL be a
    deterministic function of that content (identical content → identical
    checksum; any content change → a different checksum), and a
    regeneration SHALL update both ``last_refreshed`` and
    ``content_checksum`` together.

This test exercises the side-effect-free helpers exposed by
``refresh_cdk_docs`` — ``content_checksum`` and ``regenerate_catalog_text``
(driven through ``build_catalog_table`` / ``parse_catalog_entries``) — with
``hypothesis``-generated catalog content (>=100 iterations each), with no
network and no file I/O:

* Determinism — ``content_checksum(c) == content_checksum(c)`` for any
  content, and distinct content yields distinct checksums (the 16-hex
  sha256 prefix is effectively collision-free for test inputs).
* Together — every ``regenerate_catalog_text`` call rewrites BOTH the
  ``last_refreshed`` date (to the passed ``today``) AND the
  ``content_checksum`` (to the checksum of the freshly rendered table),
  regardless of the file's previous front-matter values.
* Move-together-under-change — changing the content changes the checksum,
  while ``last_refreshed`` tracks ``today``; the two fields are written as
  one unit on every regeneration.

Run with::

    uv run --project .kiro/connect_knowledge_mcp --with pytest --with hypothesis \
        pytest .kiro/scripts/refresh_cdk_docs_checksum_test.py
"""

from __future__ import annotations

import re
import string
import sys
from datetime import date
from pathlib import Path

from hypothesis import assume, given, settings
from hypothesis import strategies as st

# The helpers live next to this test in scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from refresh_cdk_docs import (  # noqa: E402
    LIBRARY_URLS,
    TABLE_HEADER,
    TABLE_SEPARATOR,
    CatalogEntry,
    build_catalog_table,
    content_checksum,
    front_matter_last_refreshed,
    parse_catalog_entries,
    regenerate_catalog_text,
    render_table,
)

# --- smart generators -----------------------------------------------------

_NAME_CHARS = string.ascii_letters + string.digits
# Description text that round-trips through a markdown table row: no pipe
# (cell separator) and no newline/carriage-return (row separator).
_DESC_CHARS = string.ascii_letters + string.digits + " .,:;-_()[]#/"

_libraries = st.sampled_from(sorted(LIBRARY_URLS))


def _construct_names(min_size: int = 0, max_size: int = 8) -> st.SearchStrategy:
    """Distinct ``Cfn*`` construct names (excluding the ``*Props`` pages)."""
    name = (
        st.text(alphabet=_NAME_CHARS, min_size=1, max_size=12)
        .map(lambda s: "Cfn" + s)
        .filter(lambda n: not n.endswith("Props"))
    )
    return st.lists(name, min_size=min_size, max_size=max_size, unique=True)


_descriptions = st.text(alphabet=_DESC_CHARS, min_size=0, max_size=60)


def _construct_url(library: str, name: str) -> str:
    return f"https://docs.aws.amazon.com/cdk/api/v2/python/{library}/{name}.html"


def _make_landing_html(names: list[str], library: str) -> str:
    """Synthesize a CDK landing page that links to each construct page.

    Mirrors how the live pages link constructs (path-qualified hrefs) so
    ``parse_construct_links`` accepts them as the library's own constructs.
    """
    links = "".join(
        f'<li><a href="{library}/{name}.html">{name}</a></li>' for name in names
    )
    return f"<html><body><ul>{links}</ul></body></html>"


def _make_catalog_text(
    entries: list[CatalogEntry],
    *,
    library: str,
    last_refreshed: date,
    checksum: str,
) -> str:
    """Synthesize an existing catalog steering file (front matter + table).

    The shape mirrors the real ``cdk-*.md`` files: YAML front matter with
    ``last_refreshed`` / ``construct_count`` / ``content_checksum`` scalars
    (all three must exist for the in-place rewrite to succeed) and a
    ``| Construct | Description |`` table embedded in prose.
    """
    rows = "\n".join(
        f"| [{e.name}]({e.url}) | {e.description} |" for e in entries
    )
    table = "\n".join([TABLE_HEADER, TABLE_SEPARATOR, rows]) if rows else "\n".join(
        [TABLE_HEADER, TABLE_SEPARATOR]
    )
    front_matter = "\n".join(
        [
            "---",
            "inclusion: manual",
            f"last_refreshed: {last_refreshed.isoformat()}",
            f"construct_count: {len(entries)}",
            "source_urls:",
            f"  - {LIBRARY_URLS[library]}",
            f"content_checksum: {checksum}",
            "---",
        ]
    )
    return (
        f"{front_matter}\n\n"
        f"# CDK construct catalog\n\n"
        f"Intro prose that must survive the rewrite.\n\n"
        f"{table}\n\n"
        f"Trailing prose after the table.\n"
    )


_CHECKSUM_RE = re.compile(r"(?m)^content_checksum:\s*(\S+)\s*$")


def _front_matter_checksum(text: str) -> str | None:
    match = _CHECKSUM_RE.search(text)
    return match.group(1) if match else None


# A composite strategy for an existing catalog: its entries, the construct
# names the (synthetic) live page advertises, the library, and the file's
# previous front-matter date + checksum (which regeneration must overwrite).
@st.composite
def _catalog_scenarios(draw: st.DrawFn) -> dict:
    library = draw(_libraries)
    existing_names = draw(_construct_names(min_size=0, max_size=6))
    existing_entries = [
        CatalogEntry(
            name=name,
            url=_construct_url(library, name),
            description=draw(_descriptions),
        )
        for name in existing_names
    ]
    live_names = draw(_construct_names(min_size=0, max_size=6))
    prev_date = draw(st.dates())
    prev_checksum = "sha256:" + draw(
        st.text(alphabet=string.hexdigits.lower()[:16], min_size=16, max_size=16)
    )
    return {
        "library": library,
        "existing_entries": existing_entries,
        "live_names": live_names,
        "prev_date": prev_date,
        "prev_checksum": prev_checksum,
    }


# --- Part 1: content_checksum determinism ---------------------------------


@settings(max_examples=200)
@given(content=st.text(max_size=400))
def test_checksum_is_deterministic(content: str) -> None:
    """Feature: connect-iac-cdk, Property 6: Refresh checksum integrity.

    Same content → same checksum: ``content_checksum`` is a pure function
    of its input. Validates: Requirements 4.3.
    """
    first = content_checksum(content)
    second = content_checksum(content)
    assert first == second, f"non-deterministic: {first!r} != {second!r}"
    # Shape contract: "sha256:" + 16 lowercase hex digits.
    digest = first
    assert digest.startswith("sha256:")
    hexpart = digest[len("sha256:") :]
    assert len(hexpart) == 16
    assert all(c in "0123456789abcdef" for c in hexpart)


@settings(max_examples=200)
@given(a=st.text(max_size=400), b=st.text(max_size=400))
def test_distinct_content_yields_distinct_checksum(a: str, b: str) -> None:
    """Feature: connect-iac-cdk, Property 6: Refresh checksum integrity.

    Any content change → a different checksum. The 16-hex sha256 prefix is
    effectively collision-free for generated test inputs.
    Validates: Requirements 4.3.
    """
    assume(a != b)
    assert content_checksum(a) != content_checksum(b)


# --- Part 2: regeneration updates last_refreshed AND checksum together ----


@settings(max_examples=200)
@given(scenario=_catalog_scenarios(), today=st.dates())
def test_regeneration_updates_date_and_checksum_together(
    scenario: dict, today: date
) -> None:
    """Feature: connect-iac-cdk, Property 6: Refresh checksum integrity.

    A regeneration rewrites BOTH ``last_refreshed`` (to ``today``) and
    ``content_checksum`` (to the checksum of the freshly rendered table)
    as one unit, regardless of the file's previous values.
    Validates: Requirements 4.3.
    """
    library = scenario["library"]
    existing_entries = scenario["existing_entries"]
    html = _make_landing_html(scenario["live_names"], library)
    existing_text = _make_catalog_text(
        existing_entries,
        library=library,
        last_refreshed=scenario["prev_date"],
        checksum=scenario["prev_checksum"],
    )

    # Independently derive what the regenerated table — and therefore the
    # checksum — must be, straight from the public helpers.
    expected_table, expected_entries = build_catalog_table(
        html, library, parse_catalog_entries(existing_text)
    )
    expected_checksum = content_checksum(expected_table)

    new_text, entries, checksum = regenerate_catalog_text(
        existing_text,
        html,
        library,
        today=today,
        source_url=LIBRARY_URLS[library],
        final_url=LIBRARY_URLS[library],
    )

    # The returned checksum is the checksum of the rendered table.
    assert entries == expected_entries
    assert checksum == expected_checksum
    assert checksum == content_checksum(render_table(entries))

    # BOTH front-matter fields were rewritten, together, in the new text.
    assert front_matter_last_refreshed(new_text) == today
    assert _front_matter_checksum(new_text) == checksum
    # construct_count moves with them too (part of the same write).
    assert f"construct_count: {len(entries)}" in new_text


@settings(max_examples=200)
@given(
    names_a=_construct_names(min_size=1, max_size=6),
    names_b=_construct_names(min_size=1, max_size=6),
    library=_libraries,
    day_a=st.dates(),
    day_b=st.dates(),
)
def test_content_change_moves_checksum_while_date_tracks_today(
    names_a: list[str],
    names_b: list[str],
    library: str,
    day_a: date,
    day_b: date,
) -> None:
    """Feature: connect-iac-cdk, Property 6: Refresh checksum integrity.

    Regenerating the *same* file from two different live construct sets:
    different content → different checksum, while ``last_refreshed`` tracks
    the ``today`` passed to each regeneration. The two fields move together
    on every write. Validates: Requirements 4.3.
    """
    # Two genuinely different construct sets → two different rendered tables.
    assume(frozenset(names_a) != frozenset(names_b))
    assume(day_a != day_b)

    existing_text = _make_catalog_text(
        [],
        library=library,
        last_refreshed=date(2000, 1, 1),
        checksum="sha256:0000000000000000",
    )

    new_a, entries_a, checksum_a = regenerate_catalog_text(
        existing_text,
        _make_landing_html(names_a, library),
        library,
        today=day_a,
        source_url=LIBRARY_URLS[library],
        final_url=LIBRARY_URLS[library],
    )
    new_b, entries_b, checksum_b = regenerate_catalog_text(
        existing_text,
        _make_landing_html(names_b, library),
        library,
        today=day_b,
        source_url=LIBRARY_URLS[library],
        final_url=LIBRARY_URLS[library],
    )

    # Different content (distinct construct sets) → different checksum.
    assert {e.name for e in entries_a} != {e.name for e in entries_b}
    assert checksum_a != checksum_b

    # last_refreshed tracked the today passed to each regeneration ...
    assert front_matter_last_refreshed(new_a) == day_a
    assert front_matter_last_refreshed(new_b) == day_b
    # ... and the checksum field in each file matches that file's checksum.
    assert _front_matter_checksum(new_a) == checksum_a
    assert _front_matter_checksum(new_b) == checksum_b
