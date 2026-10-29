"""Property-based test for refresh write-discipline.

Feature: connect-iac-cdk, Property 7: Refresh write-discipline

Validates: Requirements 4.4, 4.5

The property under test (design "Property 7: Refresh write-discipline",
design section C3):

    *For any* refresh invocation, when run with ``--dry-run`` the steering
    files SHALL be left unchanged, and when a source page fetch fails the
    corresponding previously-generated steering file SHALL be left
    unchanged (and the failing source URL reported).

This splits cleanly into the two halves Requirement 4 names:

* **Req 4.4 (dry-run discipline):** ``refresh_all(..., dry_run=True)``
  reports what *would* change but writes nothing — every catalog file's
  bytes are byte-for-byte identical before and after, and every
  ``RefreshResult`` is ``would-write`` / ``would-skip`` (never
  ``written`` / ``unchanged`` / ``failed``).
* **Req 4.5 (fetch-failure isolation):** when a source page fetch raises,
  ``refresh_all(..., dry_run=False)`` leaves *that* catalog file unchanged
  and reports the failing source URL on its ``RefreshResult`` (status
  ``failed``), while the catalogs whose fetch succeeded may still be
  rewritten.
* **Unrecognized layout counts as a failed fetch:** a page that yields no
  ``Cfn*`` construct links leaves its catalog unchanged and is reported
  ``failed``, in dry-run and real runs alike. This guard exists because
  the October 2026 CDK reference move left the old parser finding 0
  constructs, and merging an empty set would have emptied all four
  catalogs while exiting 0. A companion test parses hrefs copied from the
  live VitePress overview pages, so the guard cannot trip on the real
  layout.

Both halves are driven by ``hypothesis`` (>=100 iterations) over a mocked
``fetcher`` — the injectable seam ``refresh_one`` / ``refresh_all`` expose —
so the test does **zero** network I/O. hypothesis varies the construct
sets the mock returns (part 1) and which catalogs fail (part 2). The real
``.kiro/steering/cdk-*.md`` catalogs are copied into a throwaway temp dir
per example so the production files are never touched.

Run with::

    uv run --project .kiro/connect_knowledge_mcp --with pytest --with hypothesis \
        pytest .kiro/scripts/refresh_cdk_docs_writediscipline_test.py
"""

from __future__ import annotations

import string
import sys
import tempfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# The script under test lives next to this test in scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest  # noqa: E402

from refresh_cdk_docs import (  # noqa: E402
    CATALOGS,
    STEERING_DIR,
    parse_construct_links,
    refresh_all,
)

# --- generators ------------------------------------------------------------

# A construct name the landing-page parser will accept: ``Cfn`` followed by
# >=1 alphanumeric chars, and not a ``*Props`` data-interface page (those
# are filtered out by ``parse_construct_links``).
_construct_names = st.builds(
    lambda suffix: "Cfn" + suffix,
    st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=12),
).filter(lambda name: not name.endswith("Props"))

# A per-catalog set of constructs the mock page links to. At least one:
# a page with none is an unrecognized layout, covered by its own test.
_construct_name_list = st.lists(_construct_names, min_size=1, max_size=8, unique=True)

# One construct-name list per catalog, in CATALOGS order.
_name_sets_per_catalog = st.tuples(*([_construct_name_list] * len(CATALOGS)))

# A True/False "this fetch fails" flag per catalog, in CATALOGS order.
_fail_flags = st.lists(st.booleans(), min_size=len(CATALOGS), max_size=len(CATALOGS))


def _landing_page_html(names: list[str], library: str) -> str:
    """Render a minimal CDK module overview page linking each construct.

    Uses the live VitePress href form,
    ``/cdk/api/v2/docs/aws-cdk-lib.<module>.CfnX.html``.
    """
    module = library.removeprefix("aws_cdk.")
    anchors = "".join(
        f'<a href="/cdk/api/v2/docs/aws-cdk-lib.{module}.{name}.html">{name}</a>\n'
        for name in names
    )
    return f"<html><body><h1>module</h1>{anchors}</body></html>"


def _seed_steering_dir(tmp: Path) -> dict[str, bytes]:
    """Copy the four real catalogs into ``tmp``; return their original bytes."""
    originals: dict[str, bytes] = {}
    for catalog in CATALOGS:
        text = (STEERING_DIR / catalog.filename).read_text(encoding="utf-8")
        dest = tmp / catalog.filename
        dest.write_text(text, encoding="utf-8")
        originals[catalog.filename] = dest.read_bytes()
    return originals


# --- Property 7, part 1: --dry-run leaves every file unchanged (Req 4.4) ---


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(name_sets=_name_sets_per_catalog)
def test_dry_run_writes_nothing(name_sets: tuple[list[str], ...]) -> None:
    """Feature: connect-iac-cdk, Property 7: Refresh write-discipline.

    A ``--dry-run`` refresh, with a fetcher that returns valid (varying)
    HTML for every catalog, reports would-write/would-skip and leaves
    every steering file byte-for-byte unchanged. Validates: Requirements 4.4.
    """
    html_by_url = {
        catalog.source_url: _landing_page_html(list(names), catalog.library)
        for catalog, names in zip(CATALOGS, name_sets)
    }

    def fetcher(url: str, query_hint: str) -> tuple[str, str]:
        # Valid HTML, no network; final_url == source_url (no page move).
        return url, html_by_url[url]

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        originals = _seed_steering_dir(tmp)

        results = refresh_all(
            steering_dir=tmp,
            fetcher=fetcher,
            dry_run=True,
            verbose=False,
        )

        # Nothing was written: every file is byte-identical to the seed.
        for catalog in CATALOGS:
            after = (tmp / catalog.filename).read_bytes()
            assert after == originals[catalog.filename], (
                f"dry-run modified {catalog.filename}"
            )

        # Every result is a dry-run verdict, never an actual write/failure.
        assert len(results) == len(CATALOGS)
        for result in results:
            assert result.status in {"would-write", "would-skip"}, (
                f"unexpected dry-run status {result.status!r} for {result.filename}"
            )


# --- Property 7, part 2: a failed fetch leaves THAT file unchanged (Req 4.5) -


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(name_sets=_name_sets_per_catalog, fail_flags=_fail_flags)
def test_failed_fetch_leaves_its_file_unchanged_and_reports_url(
    name_sets: tuple[list[str], ...], fail_flags: list[bool]
) -> None:
    """Feature: connect-iac-cdk, Property 7: Refresh write-discipline.

    With a fetcher that raises for a chosen subset of catalogs and returns
    valid HTML for the rest, a real (non-dry-run) refresh leaves each
    failed catalog's file unchanged and reports the failing source URL,
    while the others may be rewritten. Validates: Requirements 4.5.
    """
    failing_urls = {
        catalog.source_url
        for catalog, fail in zip(CATALOGS, fail_flags)
        if fail
    }
    html_by_url = {
        catalog.source_url: _landing_page_html(list(names), catalog.library)
        for catalog, names in zip(CATALOGS, name_sets)
    }

    def fetcher(url: str, query_hint: str) -> tuple[str, str]:
        if url in failing_urls:
            raise RuntimeError(f"simulated fetch failure for {url}")
        return url, html_by_url[url]

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        originals = _seed_steering_dir(tmp)

        results = refresh_all(
            steering_dir=tmp,
            fetcher=fetcher,
            dry_run=False,
            verbose=False,
        )

        results_by_file = {r.filename: r for r in results}
        assert len(results) == len(CATALOGS)

        for catalog, fail in zip(CATALOGS, fail_flags):
            result = results_by_file[catalog.filename]
            after = (tmp / catalog.filename).read_bytes()
            if fail:
                # Req 4.5: failed fetch -> file untouched, failure reported.
                assert result.status == "failed", (
                    f"expected failed status for {catalog.filename}, "
                    f"got {result.status!r}"
                )
                assert after == originals[catalog.filename], (
                    f"failed fetch modified {catalog.filename}"
                )
                # The failing source URL is reported on the result.
                assert result.source_url == catalog.source_url
                assert result.error and catalog.source_url in result.error
            else:
                # A successful fetch is a normal write/no-diff, never failed.
                assert result.status in {"written", "unchanged"}, (
                    f"unexpected status {result.status!r} for {catalog.filename}"
                )
                assert result.source_url == catalog.source_url


# --- Unrecognized layout: no Cfn* links leaves every file unchanged --------


# The pre-October-2026 Sphinx href forms. The current parser must not
# accept them, so a page still shaped like this reads as "no constructs".
_RETIRED_SPHINX_PAGE = (
    "<html><body>"
    '<a href="CfnInstance.html">CfnInstance</a>'
    '<a href="aws_cdk.aws_lex/CfnBot.html">CfnBot</a>'
    '<a href="#">Appearance</a>'
    "</body></html>"
)


@pytest.mark.parametrize("dry_run", [True, False])
def test_page_without_constructs_fails_and_leaves_file_unchanged(dry_run: bool) -> None:
    """A fetched page with no recognizable construct links is a failure.

    Without this guard, merging the empty live set drops every existing
    row and the run exits 0. Every catalog must stay byte-identical, and
    every result must be ``failed`` with the page URL in the error.
    """

    def fetcher(url: str, query_hint: str) -> tuple[str, str]:
        return url, _RETIRED_SPHINX_PAGE

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        originals = _seed_steering_dir(tmp)

        results = refresh_all(
            steering_dir=tmp,
            fetcher=fetcher,
            dry_run=dry_run,
            verbose=False,
        )

        for catalog, result in zip(CATALOGS, results):
            assert (tmp / catalog.filename).read_bytes() == originals[catalog.filename]
            assert result.status == "failed"
            assert result.error and catalog.source_url in result.error
            assert "not recognized" in result.error


def test_live_vitepress_href_shapes_parse_to_own_constructs_only() -> None:
    """Hrefs copied from the live ``aws-cdk-lib.aws_lex-readme.html`` page.

    Only the module's own top-level constructs survive: not ``*Props``
    pages, nested property types, ``interfaces`` reference pages, or
    another module's constructs.
    """
    hrefs = (
        "/cdk/api/v2/docs/aws-cdk-lib.aws_lex.CfnBot.html",
        "/cdk/api/v2/docs/aws-cdk-lib.aws_lex.CfnBotAlias.html",
        "/cdk/api/v2/docs/aws-cdk-lib.aws_lex.CfnBot.AdvancedRecognitionSettingProperty.html",
        "/cdk/api/v2/docs/aws-cdk-lib.aws_lex.CfnBotProps.html",
        "/cdk/api/v2/docs/aws-cdk-lib.interfaces.aws_lex.BotReference.html",
        "/cdk/api/v2/docs/aws-cdk-lib.aws_lexmodelsv2.CfnShadow.html",
        "/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnInstance.html",
        "/cdk/api/v2/docs/aws-cdk-lib.aws_lex.CfnBot.html#properties",
    )
    html = "".join(f'<a href="{h}">x</a>' for h in hrefs)

    links = parse_construct_links(html, "aws_cdk.aws_lex")

    assert [name for name, _ in links] == ["CfnBot", "CfnBotAlias"]
    assert links[0][1] == (
        "https://docs.aws.amazon.com/cdk/api/v2/docs/"
        "aws-cdk-lib.aws_lex.CfnBot.html?lang=python"
    )
