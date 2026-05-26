"""Search the AWS documentation index.

Hits the public docs search endpoint that powers
``https://docs.aws.amazon.com/`` autocomplete and returns parsed hits.

Ported from the connect-mcp gateway target Lambda.
"""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)

DOCS_URL = "https://proxy.search.docs.aws.com/search"
DOCS_DOMAIN = "docs.aws.amazon.com"

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


def aws_search(query: str, limit: int = 10) -> str:
    """Search AWS documentation and return formatted text results.

    Args:
        query: Free-text search query.
        limit: Maximum number of hits to return (default 10).

    Returns:
        Multi-hit formatted block, or an error / no-results string.
    """
    payload = {
        "textQuery": {"input": query},
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
            results = [
                _clean_doc_result(s.get("textExcerptSuggestion", {}))
                for s in suggestions[:limit]
            ]
            results = [r for r in results if r]

            if not results:
                return f"No AWS documentation results found for: {query}"

            lines = [
                f"Title: {r.get('title', '')}\n"
                f"URL: {r.get('link', '')}\n"
                f"Snippet: {r.get('summary', r.get('suggestionBody', ''))}"
                for r in results
            ]
            return "\n---\n".join(lines)

        except requests.exceptions.HTTPError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else None
            if status in (400, 429, 500, 502, 503):
                wait = BACKOFF_BASE**attempt
                logger.warning(
                    "aws_search attempt %d/%d got status %s, retrying in %ds",
                    attempt + 1,
                    MAX_RETRIES,
                    status,
                    wait,
                )
                time.sleep(wait)
            else:
                return f"Error searching AWS docs: {exc}"
        except requests.exceptions.RequestException as exc:
            return f"Error searching AWS docs: {exc}"

    return f"Error after {MAX_RETRIES} retries: {last_error}"
