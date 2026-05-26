"""Command-line entry points for the three search tools.

Each entry point is exposed as a console script in ``pyproject.toml``:

    connect-docs-search   "search query"
    connect-blog-search   "search query"
    connect-repost-search "search query"

Output goes to stdout as plain text, ready for direct LLM consumption.
Logs go to stderr.
"""

from __future__ import annotations

import argparse
import logging
import sys

from connect_knowledge.blogs import DEFAULT_BLOGS, aws_blog_search
from connect_knowledge.docs import aws_search
from connect_knowledge.repost import CONNECT_TAG_ID, aws_repost_search


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def docs_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="connect-docs-search",
        description="Search AWS documentation (docs.aws.amazon.com).",
    )
    parser.add_argument("query", help="Free-text search query")
    parser.add_argument(
        "--limit", type=int, default=10, help="Max hits to return (default 10)"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    print(aws_search(args.query, limit=args.limit))
    return 0


def blogs_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="connect-blog-search",
        description="Search AWS blogs (Connect-tuned by default).",
    )
    parser.add_argument("query", help="Free-text search query")
    parser.add_argument(
        "--blog",
        action="append",
        dest="blogs",
        help=(
            "Restrict to a specific blog name. Repeat for multiple. "
            f"Default set: {', '.join(DEFAULT_BLOGS)}"
        ),
    )
    parser.add_argument(
        "--all-blogs",
        action="store_true",
        help="Search all AWS blogs (overrides --blog).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    if args.all_blogs:
        blogs: list[str] | None = []
    else:
        blogs = args.blogs  # None → DEFAULT_BLOGS, list → use as-is

    print(aws_blog_search(args.query, blogs=blogs))
    return 0


def repost_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="connect-repost-search",
        description="Search AWS re:Post questions / articles / knowledge-center.",
    )
    parser.add_argument("query", help="Free-text search query")
    parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        help=(
            "re:Post tag id to filter by. Repeat for multiple. "
            f"Default: {CONNECT_TAG_ID} (Amazon Connect)."
        ),
    )
    parser.add_argument(
        "--no-tag",
        action="store_true",
        help="Disable tag filtering (search all of re:Post).",
    )
    parser.add_argument(
        "--include-unanswered",
        action="store_true",
        help="Include unanswered questions (default: answered only).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    if args.no_tag:
        tag_ids: list[str] | None = []
    else:
        tag_ids = args.tags  # None → default Connect tag, list → use as-is

    print(
        aws_repost_search(
            args.query,
            tag_ids=tag_ids,
            answered_only=not args.include_unanswered,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(docs_main())
