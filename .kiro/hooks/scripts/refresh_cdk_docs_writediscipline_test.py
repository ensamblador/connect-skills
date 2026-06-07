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

Both halves are driven by ``hypothesis`` (>=100 iterations) over a mocked
``fetcher`` — the injectable seam ``refresh_one`` / ``refresh_all`` expose —
so the test does **zero** network I/O. hypothesis varies the construct
sets the mock returns (part 1) and which catalogs fail (part 2). The real
``.kiro/steering/cdk-*.md`` catalogs are copied into a throwaway temp dir
per example so the production files are never touched.

Run with::

    uv run --extra dev pytest .kiro/hooks/scripts/refresh_cdk_docs_writediscipline_test.py
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
from refresh_cdk_docs import (  # noqa: E402
    CATALOGS,
    STEERING_DIR,
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

# A per-catalog set of constructs the mock page links to (may be empty —
# an empty page is a valid, if drastic, upstream change).
_construct_name_list = st.lists(_construct_names, min_size=0, max_size=8, unique=True)

# One construct-name list per catalog, in CATALOGS order.
_name_sets_per_catalog = st.tuples(*([_construct_name_list] * len(CATALOGS)))

# A True/False "this fetch fails" flag per catalog, in CATALOGS order.
_fail_flags = st.lists(st.booleans(), min_size=len(CATALOGS), max_size=len(CATALOGS))


def _landing_page_html(names: list[str]) -> str:
    """Render a minimal CDK landing page that links to each construct.

    Uses bare ``CfnX.html`` hrefs (the form on the aws_connect README),
    which ``parse_construct_links`` accepts for any library.
    """
    anchors = "".join(f'<a href="{name}.html">{name}</a>\n' for name in names)
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
        catalog.source_url: _landing_page_html(list(names))
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
        catalog.source_url: _landing_page_html(list(names))
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
