"""Search AWS blogs (CloudSearch endpoint).

Ported from the connect-mcp gateway target Lambda. The default blog list
is tuned for Amazon Connect work: contact center, partner network, and
messaging.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable

import requests

logger = logging.getLogger(__name__)

BLOG_SEARCH_URL = "https://aws.amazon.com/search/p/2013-01-01/search"

DEFAULT_BLOGS: tuple[str, ...] = (
    "AWS Contact Center",
    "AWS Partner Network (APN) Blog",
    "AWS Messaging Blog",
)

MAX_RETRIES = 6
BACKOFF_BASE = 2
REQUEST_TIMEOUT = 30

# CloudSearch structured-query fragment shared by both query branches:
# drop developer-tools / solution-provider entries and keep English only.
_BLOG_FILTERS = (
    "(and (not type: 'developertools') (not type: 'solution_providers')) "
    "(or (term field=lang 'en')) "
)


def _clean_blog_result(result: dict) -> dict:
    fields = result.get("fields") or {}
    link = fields.get("url")
    if not link:
        return {}
    return {
        "title": fields.get("title", ""),
        "link": link,
        "description": fields.get("description", ""),
    }


def _format_hit(result: dict) -> str:
    """Render one cleaned hit as a Title / URL / Snippet block."""
    return (
        f"Title: {result.get('title', '')}\n"
        f"URL: {result.get('link', '')}\n"
        f"Snippet: {result.get('description', '')}"
    )


def aws_blog_search(
    query: str,
    blogs: Iterable[str] | None = None,
    page_size: int = 25,
) -> str:
    """Search AWS blogs and return formatted text results.

    Args:
        query: Free-text search query.
        blogs: Iterable of blog display names to restrict the search to.
            Defaults to ``DEFAULT_BLOGS`` (Connect-tuned). Pass an empty
            iterable to search all AWS blogs.
        page_size: How many hits to request from CloudSearch.

    Returns:
        Multi-hit formatted block, or an error / no-results string.
    """
    include_blogs = list(DEFAULT_BLOGS if blogs is None else blogs)

    return_fields = (
        "return=description,title,url,type_display,"
        "marketplace_architecture,marketplace_price,"
        "marketplace_operating_system,marketplace_vendor_name,"
        "marketplace_vendor_url"
    )
    options = (
        "&q.parser=structured"
        '&q.options={"defaultOperator":"and","fields":["url^5", "title^2", "description", "entry", "categories"]}'
        "&highlight.url={max_phrases:5}"
        "&highlight.description={max_phrases:5}"
        "&facet.type={}"
        "&facet.ami_os={}"
        "&facet.ami_provider={}"
        "&facet.ami_type={}"
        "&facet.blog_name={}"
    )
    paging = f"size={page_size}&start=0&sort=custom_20160114 desc"

    if include_blogs:
        clauses = [
            f"(and '{query}' blog_name:'{b}' type: 'blogs' {_BLOG_FILTERS})"
            for b in include_blogs
        ]
        q = "or " + " ".join(clauses)
    else:
        q = f"and (and '{query}' type: 'blogs' {_BLOG_FILTERS})"

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            final_url = f"{BLOG_SEARCH_URL}?q=({q})&{paging}&{options}&{return_fields}"
            response = requests.get(final_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            hits = data.get("hits", {}).get("hit", [])
            results: list[dict] = []
            for hit in hits:
                link = (hit.get("fields") or {}).get("url", "")
                if "/author/" in link or "/tag/" in link:
                    continue
                cleaned = _clean_blog_result(hit)
                if cleaned:
                    results.append(cleaned)

            if not results:
                return f"No AWS blog results found for: {query}"

            return "\n---\n".join(_format_hit(r) for r in results)

        except requests.exceptions.HTTPError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else None
            if status in (400, 429, 500, 502, 503):
                wait = BACKOFF_BASE**attempt
                logger.warning(
                    "aws_blog_search attempt %d/%d got status %s, retrying in %ds",
                    attempt + 1,
                    MAX_RETRIES,
                    status,
                    wait,
                )
                time.sleep(wait)
            else:
                return f"Error searching AWS blogs: {exc}"
        except requests.exceptions.RequestException as exc:
            return f"Error searching AWS blogs: {exc}"

    return f"Error after {MAX_RETRIES} retries: {last_error}"
