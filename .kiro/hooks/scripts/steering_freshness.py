"""Steering catalog freshness rule (pure, dependency-free).

This helper backs the 7-day freshness rule embedded in every CDK steering
catalog's front matter (design C2/C3, Requirement 3.6). It is deliberately
a pure function over two :class:`datetime.date` values so it can be:

* imported by the ``CDK_Docs_Refresh`` script
  (``.kiro/hooks/scripts/refresh_cdk_docs.py``) to decide whether a
  catalog needs regenerating, and
* driven by the ``hypothesis`` property test (Property 8) with no I/O.

The rule is the same one stated in prose in each ``cdk-*.md`` steering
file: a catalog is *stale* (the agent should run ``CDK_Docs_Refresh``
before relying on it) when more than 7 days have elapsed since its
``last_refreshed`` date.
"""

from __future__ import annotations

from datetime import date, timedelta

# The maximum age, in days, a steering catalog may reach before it is
# considered stale. A file exactly this many days old is still fresh;
# strictly older than this is stale (Requirement 3.6).
FRESHNESS_MAX_AGE_DAYS = 7


def is_stale(
    last_refreshed: date,
    current_date: date,
    max_age_days: int = FRESHNESS_MAX_AGE_DAYS,
) -> bool:
    """Return whether a steering catalog is stale and should be refreshed.

    Per Requirement 3.6, a catalog is stale **if and only if** the gap
    between ``current_date`` and ``last_refreshed`` strictly exceeds
    ``max_age_days`` (default 7). The boundary is exact:

    * a gap of exactly ``max_age_days`` days is **not** stale,
    * a gap of ``max_age_days + 1`` days **is** stale.

    A ``current_date`` earlier than ``last_refreshed`` yields a negative
    gap, which is never stale.

    Args:
        last_refreshed: The catalog's ``last_refreshed`` front-matter date.
        current_date: The date to evaluate freshness against (today).
        max_age_days: The inclusive maximum age in days before staleness
            (defaults to the 7-day rule).

    Returns:
        ``True`` when ``current_date - last_refreshed`` is strictly
        greater than ``max_age_days`` days, ``False`` otherwise.
    """
    return (current_date - last_refreshed) > timedelta(days=max_age_days)
