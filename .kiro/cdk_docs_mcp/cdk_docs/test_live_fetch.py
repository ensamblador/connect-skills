"""Live integration test for per-library CDK construct-doc fetch.

Feature: connect-iac-cdk, Task 1.9 — integration test (NOT a property
test). Validates: Requirements 1.4.

Requirement 1.4: the CDK_Docs_MCP serves documentation for each in-scope
``Construct_Library`` — ``aws_cdk.aws_connect``, ``aws_cdk.aws_lex``,
``aws_cdk.aws_wisdom``, and ``aws_cdk.aws_bedrockagentcore``.

Unlike the parse-fidelity *property* test (``test_parse_fidelity.py``,
which mocks ``fetch_page`` and runs >=100 generated iterations), this test
hits the **real** ``docs.aws.amazon.com`` CDK reference. Because it depends
on an external service it runs **one example per library** (four real
fetches total), not a property sweep — per the design's INTEGRATION
classification of Req 1.4.

For each in-scope library it fetches one known-good construct reference
page via ``get_cdk_construct_doc(construct, library)`` (NO mocking — real
network) and asserts the parsed result is a ``ConstructDoc`` dict (design
M2) with:

  * ``result["construct"] == construct`` (the requested name, verbatim),
  * ``result["url"]`` containing both the library and the construct (the
    source CDK doc page), and
  * a non-empty ``result["properties"]`` list.

Network discipline: this test **skips gracefully when offline** so it
never hard-fails CI when ``docs.aws.amazon.com`` is unreachable. A
connectivity probe skips the whole suite up front, and any per-call result
that looks like a transport failure (connection refused / DNS / timeout)
is also turned into a ``skip`` rather than a failure. When the network IS
available the test genuinely verifies the real fetch + parse for all four
libraries (Req 1.4).

Run with (from ``cdk_docs_mcp/``)::

    uv run --with pytest pytest cdk_docs/test_live_fetch.py -v
"""

from __future__ import annotations

import pytest

from cdk_docs import construct_doc, fetch


# A known-good construct per in-scope library (Req 1.4). Each construct is
# an L1 ``Cfn*`` resource that the design confirms exists in that library's
# CDK (v2, Python) reference, so its per-construct page must fetch + parse.
LIBRARY_CONSTRUCTS: dict[str, str] = {
    "aws_cdk.aws_connect": "CfnInstance",
    "aws_cdk.aws_lex": "CfnBot",
    "aws_cdk.aws_wisdom": "CfnAssistant",
    "aws_cdk.aws_bedrockagentcore": "CfnGateway",
}

# Substrings that mark a returned error string (or a raised FetchError
# reason) as a *transport* failure rather than a genuine "not found /
# unparseable" failure. Transport failures => skip (offline CI); genuine
# failures => the test fails.
_TRANSPORT_FAILURE_MARKERS = (
    "connection",
    "max retries",
    "failed to establish",
    "timed out",
    "timeout",
    "temporary failure",
    "name or service not known",
    "getaddrinfo",
    "name resolution",
    "network is unreachable",
    "no route to host",
    "connection refused",
    "connection reset",
    "ssl",
)


def _looks_like_transport_failure(message: str) -> bool:
    """Heuristic: does ``message`` describe a network/transport failure?"""
    lowered = message.lower()
    return any(marker in lowered for marker in _TRANSPORT_FAILURE_MARKERS)


@pytest.fixture(scope="module")
def network_available() -> None:
    """Skip the whole module up front when the CDK reference is unreachable.

    Probes one in-scope reference URL with a short timeout. A ``FetchError``
    whose reason looks like a transport failure means we're offline -> skip
    every test in this module (so CI never hard-fails on an unreachable
    external service). Any other failure is allowed to surface in the
    individual tests.
    """
    probe_url = fetch.LIBRARIES["aws_cdk.aws_connect"]
    try:
        fetch.fetch_page(probe_url, timeout=15)
    except fetch.FetchError as exc:
        if _looks_like_transport_failure(exc.reason):
            pytest.skip(
                f"CDK reference unreachable ({probe_url}: {exc.reason}); "
                "skipping live integration test (offline)."
            )
        # A non-transport FetchError (e.g. unexpected HTTP status on the
        # landing page) is surprising but not necessarily fatal for the
        # per-construct fetches below — let the individual tests decide.
    except Exception as exc:  # pragma: no cover - defensive, should not happen
        pytest.skip(f"Network probe raised unexpectedly: {exc!r}; skipping.")


@pytest.mark.parametrize(
    ("library", "construct"),
    sorted(LIBRARY_CONSTRUCTS.items()),
    ids=sorted(LIBRARY_CONSTRUCTS),
)
def test_live_fetch_per_library(
    network_available: None, library: str, construct: str
) -> None:
    """Fetch + parse one real construct page per in-scope library.

    Feature: connect-iac-cdk, Task 1.9 (integration)
    Validates: Requirements 1.4

    Real network call (no mocking). Skips gracefully on a transport failure;
    asserts a parsed ConstructDoc with construct name / source URL /
    non-empty properties otherwise.
    """
    result = construct_doc.get_cdk_construct_doc(construct, library)

    # get_cdk_construct_doc never raises; on failure it returns a descriptive
    # error string (Req 1.6). Distinguish "offline" (skip) from a genuine
    # fetch/parse failure (fail).
    if isinstance(result, str):
        if _looks_like_transport_failure(result):
            pytest.skip(
                f"Transport failure fetching {construct} in {library} "
                f"(offline): {result}"
            )
        pytest.fail(
            f"Live fetch/parse failed for {construct} in {library}: {result}"
        )

    # --- parsed ConstructDoc assertions (Req 1.4 / design M2) -------------
    assert isinstance(result, dict), f"expected ConstructDoc dict, got: {result!r}"

    # The requested construct identifier is preserved verbatim.
    assert result["construct"] == construct
    assert result["library"] == library

    # The source URL is preserved and names both the library and construct.
    url = result["url"]
    assert isinstance(url, str) and url
    assert library in url, f"library {library!r} not in source url {url!r}"
    assert construct in url, f"construct {construct!r} not in source url {url!r}"

    # The real page documents resource properties -> the parsed list is
    # non-empty (Req 1.4 / 1.5: the property list survives the fetch+parse).
    properties = result["properties"]
    assert isinstance(properties, list)
    assert properties, (
        f"expected a non-empty property list for {construct} in {library}, "
        f"got empty"
    )
    # Every parsed property carries at least a non-empty name.
    for prop in properties:
        assert prop.get("name"), f"property without a name in {construct}: {prop!r}"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
