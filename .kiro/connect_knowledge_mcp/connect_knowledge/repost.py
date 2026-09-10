"""Search AWS re:Post (questions, articles, knowledge-center).

Scrapes the public re:Post search page across the three content sections
and returns parsed hits. The Amazon Connect tag id is the default tag
filter so results are scoped to Connect content.

Ported from the connect-mcp gateway target Lambda.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SECTIONS: tuple[str, ...] = ("questions", "articles", "knowledge-center")
BASE_URL = "https://www.repost.aws"
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Amazon Connect tag id on re:Post. Used as the default filter so the skill
# is scoped to Connect content. Override via the ``tag_ids`` argument.
CONNECT_TAG_ID = "TAC0wz6wJtRbuJVD4X7tUmWA"


def _link_is_valid(link: str | None) -> bool:
    if not link:
        return False
    return any(section in link for section in SECTIONS)


def _clean_result(result) -> dict:
    links = result.find_all("a")
    valid = [link for link in links if _link_is_valid(link.get("href"))]
    if not valid:
        return {}
    link_tag = valid[0]
    title = link_tag.get_text()
    description = result.get_text().replace(title, "").strip()
    return {
        "title": title,
        "link": f"{BASE_URL}{link_tag.get('href')}",
        "description": description,
    }


def repost_search(
    query: str,
    section: str = "questions",
    tag_ids: Iterable[str] | None = None,
    answered_only: bool = True,
) -> dict:
    """Search a single re:Post section.

    Args:
        query: Free-text search query.
        section: One of ``questions``, ``articles``, ``knowledge-center``.
        tag_ids: Iterable of re:Post tag IDs. Defaults to the Amazon
            Connect tag. Pass an empty iterable to disable tag filtering.
        answered_only: When True (default), restrict ``questions`` to
            answered ones. Has no effect on the other sections.

    Returns:
        ``{"results": [...]}`` on success, or
        ``{"error": "...", "results": []}`` on failure.
    """
    tags = list((CONNECT_TAG_ID,) if tag_ids is None else tag_ids)

    search_url = f"{BASE_URL.replace('www.', '')}/search/{section}?globalSearch="
    query_encoded = f"{quote_plus(query)}&sort=relevant"
    if answered_only:
        query_encoded += "&contentStatusFilter=answered"
    for tag_id in tags:
        query_encoded += f"&tagIds={tag_id}"
    final_url = f"{search_url}{query_encoded}"

    logger.info("repost_search GET %s", final_url)

    try:
        response = requests.get(
            final_url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        container = soup.find(
            "div", attrs={"data-testid": "results-grid"}
        ) or soup.find("div", attrs={"data-testid": "results-list"})

        if container is None:
            logger.warning(
                "repost_search: no results container for section=%s query=%r",
                section,
                query,
            )
            return {"results": []}

        hits = container.find_all("div", class_=re.compile("PageDataView"))
        results = [cleaned for hit in hits if (cleaned := _clean_result(hit))]
        return {"results": results}

    except Exception as exc:  # noqa: BLE001 — surface error to caller
        logger.error(
            "repost_search failed for section=%s query=%r: %s",
            section,
            query,
            exc,
            exc_info=True,
        )
        return {"error": f"Error in search: {exc}", "results": []}


def repost_full_search(
    query: str,
    tag_ids: Iterable[str] | None = None,
    answered_only: bool = True,
) -> dict:
    """Search all three re:Post content sections."""
    tags = list((CONNECT_TAG_ID,) if tag_ids is None else tag_ids)
    out: dict = {}
    for section in SECTIONS:
        out[section] = repost_search(query, section, tags, answered_only).get(
            "results", []
        )
        # nosemgrep: arbitrary-sleep (deliberate re:Post rate limit)
        time.sleep(1)  # be polite between requests
    return out


def aws_repost_search(
    query: str,
    tag_ids: list[str] | None = None,
    answered_only: bool = True,
) -> str:
    """Search re:Post across all sections and return formatted text.

    Args:
        query: Free-text search query.
        tag_ids: Optional list of re:Post tag IDs. Defaults to the Amazon
            Connect tag. Pass an empty list to disable tag filtering.
        answered_only: When True (default), restrict ``questions`` to
            answered ones.

    Returns:
        Human-readable multi-section summary, or a no-results / error
        message string.
    """
    data = repost_full_search(query, tag_ids, answered_only)

    lines: list[str] = []
    for section in SECTIONS:
        hits = data.get(section, [])
        if not hits:
            continue
        lines.append(f"## {section.replace('-', ' ').title()}")
        for hit in hits:
            lines.append(f"Title: {hit.get('title', '')}")
            lines.append(f"URL: {hit.get('link', '')}")
            if snippet := hit.get("description", ""):
                lines.append(f"Snippet: {snippet}")
            lines.append("---")

    if not lines:
        return f"No AWS re:Post results found for: {query}"

    return "\n".join(lines)
