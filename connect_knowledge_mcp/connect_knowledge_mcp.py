"""MCP server exposing Amazon Connect research tools.

Wraps the search functions in the ``connect_knowledge`` Python package and
exposes them as MCP tools over stdio:

    Search:
    - search_docs    → docs.aws.amazon.com (canonical API/admin guide)
    - search_blogs   → AWS blogs (Contact Center, APN, Messaging)
    - search_repost  → repost.aws (Connect-tagged community Q&A)

    Per-page deep-dive:
    - get_block_doc   → admin-guide flow-block page (parsed)
    - get_action_doc  → API-reference flow-language action page (parsed)

    Authoring:
    - validate_flow_json → check Flow language JSON against the grammar

Future tools (not implemented yet, tracked in README):

    - search_cdk_docs  → AWS CDK reference (Connect constructs)
    - search_sdk_docs  → AWS SDK API references (boto3, JS, etc.)
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from connect_knowledge import aws_blog_search, aws_repost_search, aws_search
from connect_knowledge.page_doc import get_action_doc as _get_action_doc
from connect_knowledge.page_doc import get_block_doc as _get_block_doc
from connect_knowledge.validator import validate_flow_json as _validate_flow_json

mcp = FastMCP("connect_knowledge")


@mcp.tool()
def search_docs(query: str, limit: int = 10) -> str:
    """Search the official AWS documentation index (docs.aws.amazon.com).

    Best for canonical answers: API reference, admin guide chapters,
    contact flow block reference, service quotas, supported regions, IAM
    actions. Use this before answering questions about Connect APIs,
    contact flow blocks, configuration limits, or any documented
    behavior.

    Args:
        query: Free-text search query.
        limit: Maximum number of hits to return (default 10).

    Returns:
        Multi-hit formatted block (Title / URL / Snippet, separated by
        ``---``), or an error / no-results string. URLs are full https
        links suitable for inline citation.
    """
    return aws_search(query, limit=limit)


@mcp.tool()
def search_blogs(
    query: str,
    blogs: list[str] | None = None,
    all_blogs: bool = False,
) -> str:
    """Search AWS blogs via the public CloudSearch endpoint.

    Best for implementation patterns, walkthroughs, recent launches, and
    partner-led content. By default scoped to the three blogs that carry
    most Amazon Connect content: ``AWS Contact Center``,
    ``AWS Partner Network (APN) Blog``, and ``AWS Messaging Blog``.

    Args:
        query: Free-text search query.
        blogs: Optional list of blog display names to restrict the
            search to. When ``None`` and ``all_blogs`` is ``False``, the
            Connect-tuned default set is used. Pass an explicit list to
            override.
        all_blogs: When ``True``, search every AWS blog (overrides
            ``blogs``). Use as a fallback when the default Connect-tuned
            set returns nothing.

    Returns:
        Multi-hit formatted block (Title / URL / Snippet, separated by
        ``---``), or an error / no-results string.
    """
    if all_blogs:
        return aws_blog_search(query, blogs=[])
    return aws_blog_search(query, blogs=blogs)


@mcp.tool()
def search_repost(
    query: str,
    tag_ids: list[str] | None = None,
    no_tag: bool = False,
    include_unanswered: bool = False,
) -> str:
    """Search AWS re:Post (questions, articles, knowledge-center).

    Best for debugging specific errors, finding community-validated
    workarounds, and seeing real customer Q&A. By default scoped to the
    Amazon Connect tag and answered questions only.

    Args:
        query: Free-text search query.
        tag_ids: Optional list of re:Post tag IDs. When ``None`` and
            ``no_tag`` is ``False``, the Amazon Connect tag is used.
            Pass an explicit list to override.
        no_tag: When ``True``, disable tag filtering (search all of
            re:Post). Useful as a fallback when the Connect-tagged
            search returns nothing.
        include_unanswered: When ``True``, include unanswered questions.
            Defaults to ``False`` (answered questions only).

    Returns:
        Multi-section formatted block grouped by ``Questions``,
        ``Articles``, ``Knowledge Center``, or an error / no-results
        string.
    """
    if no_tag:
        tags: list[str] | None = []
    else:
        tags = tag_ids

    return aws_repost_search(
        query,
        tag_ids=tags,
        answered_only=not include_unanswered,
    )


@mcp.tool()
def get_block_doc(slug: str) -> dict[str, Any]:
    """Fetch and parse an admin-guide flow-block reference page.

    Use this when you need the full per-block detail (channel matrix,
    flow types, properties, configuration tips) beyond what the
    ``connect-blocks`` steering catalog one-liner provides. Pair with
    ``get_action_doc`` when also working with the Flow language JSON.

    Args:
        slug: The page slug (without extension) of the block's admin
            guide page, e.g. ``invoke-lambda-function-block``,
            ``get-customer-input``, ``customer-profiles-block``. The
            slug is the URL stem under ``/connect/latest/adminguide/``.
            You can find it from the link in the ``connect-blocks``
            steering catalog.

    Returns:
        Dict with ``name``, ``title``, ``url``, ``description``,
        ``channels`` (Voice/Chat/Task/Email matrix), ``flow_types``,
        ``properties`` (full markdown), ``configuration_tips``, plus
        the full ``raw_sections`` map for any section the parser does
        not surface as a named field.
    """
    return _get_block_doc(slug)


@mcp.tool()
def get_action_doc(slug: str) -> dict[str, Any]:
    """Fetch and parse a Connect Flow language action reference page.

    Use this when generating, validating, or debugging flow JSON and
    you need the exact ``Parameters`` shape, valid ``ErrorType``
    values, results / conditions semantics, and restrictions for a
    specific Action type. The ``connect-flow-language`` steering
    catalog one-liners are not enough on their own when writing JSON.

    Args:
        slug: The page slug (without extension) of the action's
            reference page, e.g. ``interactions-invokelambdafunction``,
            ``contact-actions-tagcontact``,
            ``flow-control-actions-loop``. The slug is the URL stem
            under ``/connect/latest/APIReference/``. You can find it
            from the link in the ``connect-flow-language`` steering
            catalog.

    Returns:
        Dict with ``name``, ``url``, ``description``,
        ``parameter_object`` (raw markdown of the Parameters schema),
        ``results_and_conditions``, ``errors`` (list of error
        descriptions), ``restrictions``, ``corresponding_block``
        (link to the matching admin-guide block), plus the full
        ``raw_sections`` map.
    """
    return _get_action_doc(slug)


@mcp.tool()
def validate_flow_json(json_str: str) -> dict[str, Any]:
    """Validate Amazon Connect Flow language JSON.

    Checks structural rules from the Flow language reference:
    top-level shape (``Version`` / ``StartAction`` / ``Actions``),
    per-Action required fields, ``Identifier`` constraints (length,
    forbidden characters, uniqueness), ``Type`` against the known
    catalog, ``Transitions`` shape, ``Operator`` against the closed
    set, ``Condition`` nesting limits, and ``NextAction`` reference
    resolution. Reports unreachable Actions as warnings.

    Per-Action ``Parameters`` schemas are NOT validated here; use
    ``get_action_doc`` for the canonical Parameters shape per Action.

    Args:
        json_str: The flow JSON as a string. The runtime requires
            real JSON — the docs example uses ``//`` comments for
            narration; remove them before validating.

    Returns:
        Dict with ``valid`` (bool), ``error_count``, ``warning_count``,
        ``issues`` (list of ``{severity, path, message}``),
        ``summary`` (str), and ``action_categories`` (Identifier →
        category name lookup).
    """
    return _validate_flow_json(json_str)


if __name__ == "__main__":
    mcp.run(transport="stdio")
