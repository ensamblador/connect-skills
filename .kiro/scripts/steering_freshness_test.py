"""Property-based test for the steering freshness rule.

Feature: connect-iac-cdk, Property 8: Steering freshness rule

Validates: Requirements 3.6

The property under test (design "Property 8: Steering freshness rule"):

    *For any* steering file and *any* current date, the freshness check
    SHALL flag the file as stale (instruct a refresh) if and only if
    ``current_date - last_refreshed > 7 days``.

The freshness check is the pure :func:`steering_freshness.is_stale`
helper. This test drives it with ``hypothesis``-generated date pairs
(>=100 iterations) and asserts the staleness verdict matches the
day-gap definition exactly, then pins the 7-day boundary with explicit
example-based cases (exactly 7 days = fresh, 8 days = stale).

Run with::

    uv run --extra dev pytest .kiro/scripts/steering_freshness_test.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

# The helper lives next to this test in scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from steering_freshness import FRESHNESS_MAX_AGE_DAYS, is_stale  # noqa: E402


# --- Property 8: stale iff current_date - last_refreshed > 7 days ---------


@settings(max_examples=300)
@given(last_refreshed=st.dates(), current_date=st.dates())
def test_is_stale_iff_gap_exceeds_seven_days(
    last_refreshed: date, current_date: date
) -> None:
    """Feature: connect-iac-cdk, Property 8: Steering freshness rule.

    For any pair of dates, ``is_stale`` returns True iff the gap strictly
    exceeds the 7-day window. Validates: Requirements 3.6.
    """
    gap_days = (current_date - last_refreshed).days
    expected_stale = gap_days > FRESHNESS_MAX_AGE_DAYS
    assert is_stale(last_refreshed, current_date) is expected_stale


@settings(max_examples=300)
@given(
    last_refreshed=st.dates(),
    offset_days=st.integers(min_value=0, max_value=3650),
)
def test_within_window_is_fresh_beyond_window_is_stale(
    last_refreshed: date, offset_days: int
) -> None:
    """Feature: connect-iac-cdk, Property 8: Steering freshness rule.

    Walking forward from ``last_refreshed``: any offset <= 7 days is
    fresh, any offset > 7 days is stale. Validates: Requirements 3.6.
    """
    current_date = last_refreshed + timedelta(days=offset_days)
    if offset_days <= FRESHNESS_MAX_AGE_DAYS:
        assert is_stale(last_refreshed, current_date) is False
    else:
        assert is_stale(last_refreshed, current_date) is True


@settings(max_examples=200)
@given(last_refreshed=st.dates(), days_before=st.integers(min_value=0, max_value=3650))
def test_current_date_not_after_last_refreshed_is_fresh(
    last_refreshed: date, days_before: int
) -> None:
    """Feature: connect-iac-cdk, Property 8: Steering freshness rule.

    A current date on or before ``last_refreshed`` (non-positive gap) is
    never stale. Validates: Requirements 3.6.
    """
    current_date = last_refreshed - timedelta(days=days_before)
    assert is_stale(last_refreshed, current_date) is False


# --- Boundary pinning (example-based, complements the property) -----------


def test_exactly_seven_days_is_not_stale() -> None:
    """The 7-day boundary is inclusive: exactly 7 days old = fresh."""
    last_refreshed = date(2025, 1, 1)
    current_date = last_refreshed + timedelta(days=7)
    assert is_stale(last_refreshed, current_date) is False


def test_eight_days_is_stale() -> None:
    """One day past the window = stale."""
    last_refreshed = date(2025, 1, 1)
    current_date = last_refreshed + timedelta(days=8)
    assert is_stale(last_refreshed, current_date) is True


def test_same_day_is_not_stale() -> None:
    """A freshly refreshed file (same day) is never stale."""
    today = date(2025, 6, 4)
    assert is_stale(today, today) is False
