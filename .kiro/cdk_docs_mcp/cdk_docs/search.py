"""Search the AWS CDK (Python) reference documentation.

Hits the same public docs search endpoint that powers
``https://docs.aws.amazon.com/`` autocomplete (the one
``connect_knowledge/docs.py:aws_search`` uses) and returns parsed hits,
but **scoped** to the CDK for Python API reference
(``docs.aws.amazon.com/cdk/api/v2/python``) so results stay within the
four in-scope construct libraries (``aws_cdk.aws_connect``,
``aws_cdk.aws_lex``, ``aws_cdk.aws_wisdom``,
``aws_cdk.aws_bedrockagentcore``) and the rest of the CDK reference.

The output format is **identical** to ``aws_search``: ``Title / URL /
Snippet`` blocks joined by ``\\n---\\n``, the same ``Error searching … :
…`` error-string convention, and the same query/limit handling — so the
MCP tool and the CLI twin (task 1.6) produce equivalent output (Req 1.7
parity).
"""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)

DOCS_URL = "https://proxy.search.docs.aws.com/search"
DOCS_DOMAIN = "docs.aws.amazon.com"

# The CDK for Python API reference lives under this path. Results are
# filtered to this prefix so the search is scoped to the CDK reference
# (which contains every in-scope ``aws_cdk.aws_*`` construct library).
CDK_REFERENCE_PREFIX = "docs.aws.amazon.com/cdk/api/v2/python"

# Appended to the user's query to bias the docs index toward CDK pages
# before URL-prefix filtering. Does not affect the returned text — the
# no-results message echoes the caller's original query verbatim.
CDK_QUERY_SCOPE = "AWS CDK Python"

MAX_RETRIES = 6
BACKOFF_BASE = 2
REQUEST_TIMEOUT = 30


def _clean_doc_result(result: dict) -> dict:
    link = result.get("link")
    if not link:
        return {}
    cleaned = {"title": result.get("title", ""), "link": link}
    if summary := result.get("summary"):
        cleaned["summary"] = summary
    if body := result.get("suggestionBody"):
        cleaned["suggestionBody"] = body
    return cleaned


def _is_cdk_reference(link: str) -> bool:
    """True when ``link`` points at the CDK for Python API reference."""
    return CDK_REFERENCE_PREFIX in link


def _format_hit(result: dict) -> str:
    """Render one cleaned hit as a Title / URL / Snippet block."""
    return (
        f"Title: {result.get('title', '')}\n"
        f"URL: {result.get('link', '')}\n"
        f"Snippet: {result.get('summary', result.get('suggestionBody', ''))}"
    )


def cdk_search(query: str, limit: int = 10) -> str:
    """Search the AWS CDK (Python) reference and return formatted results.

    Args:
        query: Free-text search query.
        limit: Maximum number of hits to return (default 10).

    Returns:
        Multi-hit formatted block (``Title / URL / Snippet`` separated by
        ``\\n---\\n``), or an error / no-results string. Format is
        identical to ``connect_knowledge.docs.aws_search``.
    """
    payload = {
        "textQuery": {"input": f"{query} {CDK_QUERY_SCOPE}"},
        "contextAttributes": [{"key": "domain", "value": DOCS_DOMAIN}],
        "acceptSuggestionBody": "RawText",
        "locales": ["en_us"],
    }

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                DOCS_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            suggestions = data.get("suggestions", [])
            # Clean every suggestion first, then keep only CDK reference
            # pages, then truncate to ``limit`` — so the limit budget is
            # spent on in-scope hits rather than filtered-out ones.
            cleaned = [
                _clean_doc_result(s.get("textExcerptSuggestion", {}))
                for s in suggestions
            ]
            results = [
                r for r in cleaned if r and _is_cdk_reference(r["link"])
            ][:limit]

            if not results:
                return f"No CDK documentation results found for: {query}"

            return "\n---\n".join(_format_hit(r) for r in results)

        except requests.exceptions.HTTPError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else None
            if status in (400, 429, 500, 502, 503):
                wait = BACKOFF_BASE**attempt
                logger.warning(
                    "cdk_search attempt %d/%d got status %s, retrying in %ds",
                    attempt + 1,
                    MAX_RETRIES,
                    status,
                    wait,
                )
                time.sleep(wait)
            else:
                return f"Error searching CDK docs: {exc}"
        except requests.exceptions.RequestException as exc:
            return f"Error searching CDK docs: {exc}"

    return f"Error after {MAX_RETRIES} retries: {last_error}"
