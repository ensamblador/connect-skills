"""Command-line entry points for the CDK docs tools.

Each entry point is exposed as a console script in ``pyproject.toml``:

    cdk-docs-search    "search query"
    cdk-construct-doc  "CfnInstance" --library aws_cdk.aws_connect

Output goes to stdout as plain text / JSON, ready for direct LLM
consumption. Logs go to stderr.

Both entry points call the **same** package functions the MCP tools
(task 1.7) call — ``cdk_docs.search.cdk_search`` and
``cdk_docs.construct_doc.get_cdk_construct_doc`` — so the terminal output
is equivalent to the tool output (Req 1.7 parity, design Property 4).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from cdk_docs.construct_doc import get_cdk_construct_doc
from cdk_docs.fetch import LIBRARIES
from cdk_docs.search import cdk_search


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _render_construct_doc(result: dict[str, Any] | str) -> str:
    """Render a ``get_cdk_construct_doc`` result for terminal display.

    The MCP tool (task 1.7) returns the structured dict directly and the
    FastMCP runtime serializes it to JSON for the caller. To keep the CLI
    output equivalent (Req 1.7 parity), a dict result is rendered as
    pretty JSON; an error result is already a descriptive string and is
    passed through verbatim.
    """
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, ensure_ascii=False)


def docs_main(argv: list[str] | None = None) -> int:
    """Console script for ``cdk-docs-search``.

    Free-text search over the AWS CDK (Python) reference. Delegates to
    ``cdk_docs.search.cdk_search`` — the same function the
    ``search_cdk_docs`` MCP tool calls.
    """
    parser = argparse.ArgumentParser(
        prog="cdk-docs-search",
        description="Search the AWS CDK (Python) reference documentation.",
    )
    parser.add_argument("query", help="Free-text search query")
    parser.add_argument(
        "--limit", type=int, default=10, help="Max hits to return (default 10)"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    print(cdk_search(args.query, limit=args.limit))
    return 0


def construct_main(argv: list[str] | None = None) -> int:
    """Console script for ``cdk-construct-doc``.

    Per-construct deep dive. Delegates to
    ``cdk_docs.construct_doc.get_cdk_construct_doc`` — the same function
    the ``get_cdk_construct_doc`` MCP tool calls.
    """
    parser = argparse.ArgumentParser(
        prog="cdk-construct-doc",
        description="Fetch and parse a CDK construct reference page.",
    )
    parser.add_argument(
        "construct", help="Construct identifier, e.g. CfnInstance"
    )
    parser.add_argument(
        "--library",
        default=None,
        help=(
            "In-scope CDK library to look in. When omitted, every in-scope "
            "library is tried until one resolves. "
            f"Choices: {', '.join(sorted(LIBRARIES))}"
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    result = get_cdk_construct_doc(args.construct, args.library)
    print(_render_construct_doc(result))
    # A string result is the descriptive error path (Req 1.6); signal it
    # with a non-zero exit while still printing the message for parity.
    return 1 if isinstance(result, str) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(docs_main())
