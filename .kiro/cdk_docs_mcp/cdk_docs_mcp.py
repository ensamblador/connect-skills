"""MCP server exposing AWS CDK (Python) reference docs for Connect IaC.

Wraps the lookup functions in the ``cdk_docs`` Python package and exposes
them as MCP tools over stdio, scoped to the four in-scope construct
libraries (``aws_cdk.aws_connect``, ``aws_cdk.aws_lex``,
``aws_cdk.aws_wisdom``, ``aws_cdk.aws_bedrockagentcore``):

    Search:
    - search_cdk_docs        → CDK v2 reference via the site's Pagefind
                               index, docs-index fallback (Title/URL/Snippet)

    Per-construct deep-dive:
    - get_cdk_construct_doc  → parsed construct page (properties + source URL)

Each tool delegates to the SAME package functions the CLI twins
(``cdk-docs-search`` / ``cdk-construct-doc``) call, so terminal output and
tool output stay equivalent. The package functions return descriptive
error strings/dicts rather than raising, so these tools never raise.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from cdk_docs.construct_doc import get_cdk_construct_doc as _get_cdk_construct_doc
from cdk_docs.search import cdk_search as _cdk_search

mcp = FastMCP("cdk_docs")


@mcp.tool()
def search_cdk_docs(
    query: str,
    limit: int = 10,
    module: str | None = None,
    kind: str | None = None,
) -> str:
    """Search the AWS CDK v2 API reference.

    Best for finding the right construct or property when authoring CDK
    Python infrastructure for Connect work. Uses the CDK site's own
    search index, which matches descriptions as well as names, so
    "agentcore gateway target" or "contact flow" work without knowing the
    construct name. Scoped to stable ``aws-cdk-lib`` pages, which cover the
    four in-scope construct libraries: ``aws_cdk.aws_connect``,
    ``aws_cdk.aws_lex``, ``aws_cdk.aws_wisdom``, and
    ``aws_cdk.aws_bedrockagentcore``. Pair with ``get_cdk_construct_doc``
    when you need the full property list for a specific construct.

    Args:
        query: Free-text search query.
        limit: Maximum number of hits to return (default 10).
        module: Optional module filter, e.g. ``aws-connect``,
            ``aws_connect`` or ``aws_cdk.aws_connect``. An unknown value
            returns an error listing the closest valid ones.
        kind: Optional page-kind filter. ``construct`` returns L1/L2
            constructs only; others are ``struct``, ``interface``,
            ``enum`` and ``class``. Property-type (``struct``) pages
            otherwise tend to outrank the construct itself.

    Returns:
        Multi-hit formatted block (``Title / URL / Snippet`` separated by
        ``---``), or an error / no-results string. URLs are full https
        links that open the Python tab. If the site search cannot run,
        the server falls back to the AWS docs search index, and the
        reply starts with a ``Note:`` line saying so; that index matches
        construct names best and ignores ``kind``.
    """
    return _cdk_search(query, limit=limit, module=module, kind=kind)


@mcp.tool()
def get_cdk_construct_doc(
    construct: str,
    library: str | None = None,
) -> dict[str, Any] | str:
    """Fetch and parse a single CDK construct reference page.

    Use this when authoring or reviewing a CDK construct and you need the
    canonical property list (name, type, required, description) and the
    source doc URL — beyond what the ``search_cdk_docs`` one-liner
    snippets provide.

    Args:
        construct: The construct identifier, e.g. ``CfnInstance``.
        library: One of the in-scope CDK libraries
            (``aws_cdk.aws_connect``, ``aws_cdk.aws_lex``,
            ``aws_cdk.aws_wisdom``, ``aws_cdk.aws_bedrockagentcore``).
            When ``None``, each in-scope library is tried until one
            resolves.

    Returns:
        On success, a dict with ``construct``, ``library``, ``url``,
        ``properties`` (list of ``{name, type?, required?,
        description?}``), ``description``, and ``raw_sections`` (escape
        hatch). On failure, a descriptive error string naming the
        requested identifier and the reason.
    """
    return _get_cdk_construct_doc(construct, library=library)


if __name__ == "__main__":
    mcp.run(transport="stdio")
