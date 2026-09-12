"""Search AWS re:Post (questions, articles, knowledge-center).

Reads the public re:Post search page across the three content sections and
returns parsed hits. The Amazon Connect tag id is the default tag filter so
results are scoped to Connect content.

Parsing strategy
----------------
re:Post is a Next.js app. Every server-rendered search page embeds the raw
search API response in the ``__NEXT_DATA__`` script tag at
``props.pageProps.response``, alongside a normalized ``content`` array that
has the same shape for all three sections. We read that JSON instead of
scraping the rendered DOM.

An earlier implementation matched result cards with
``find_all("div", class_=re.compile("PageDataView"))``. re:Post has since
renamed its CSS modules, so that selector matched zero elements and the
tool reported "no results" for every query. Hashed CSS-module class names
change on any frontend deploy, so they are not a usable contract;
``__NEXT_DATA__`` is far more stable. A DOM anchor scrape is kept as a
last-resort fallback, keyed on ``data-testid`` and href shape.

Other hardening:
    * A server-side ``ValidationException`` in the page payload surfaces as
      an error instead of an empty result set.
    * ``tag_ids`` entries are stripped of stray whitespace and ``;``/``,``
      separators. A trailing ``;`` on a tag id makes re:Post return
      ``ValidationException`` with zero results.

Ported from the connect-mcp gateway target Lambda.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterable
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SECTIONS: tuple[str, ...] = ("questions", "articles", "knowledge-center")
BASE_URL = "https://repost.aws"
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Amazon Connect tag id on re:Post. Used as the default filter so the skill
# is scoped to Connect content. Override via the ``tag_ids`` argument.
CONNECT_TAG_ID = "TAC0wz6wJtRbuJVD4X7tUmWA"

# Maps the ``type`` field of a normalized content item to its URL prefix.
_TYPE_PATHS = {
    "Question": "questions",
    "Article": "articles",
    "KCArticle": "knowledge-center",
}

_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S
)


def _clean_tag_id(tag_id: str) -> str:
    """Normalize a re:Post tag id.

    Strips whitespace and stray ``;``/``,`` separators. A malformed tag id
    such as ``TAxxx;`` makes the search backend return a
    ``ValidationException`` and zero results.
    """
    return str(tag_id).strip().strip(";,").strip()


def _item_link(item: dict) -> str:
    """Build the absolute re:Post URL for a normalized content item.

    Knowledge Center articles are addressed by their ``onlineGroupId`` slug,
    questions and community articles by their content id. Both forms resolve
    without the human-readable title slug.
    """
    path = _TYPE_PATHS.get(item.get("type", ""))
    if not path:
        return ""
    if path == "knowledge-center":
        slug = item.get("onlineGroupId") or item.get("id")
    else:
        slug = item.get("id")
    if not slug:
        return ""
    return f"{BASE_URL}/{path}/{slug}"


def _content_item_to_hit(item: dict) -> dict:
    """Turn one normalized ``content`` entry into ``{title, link, description}``."""
    link = _item_link(item)
    if not link:
        return {}
    title = (item.get("title") or "").strip()
    # Questions carry the text in ``body``; articles and KC articles in
    # ``description``.
    description = (item.get("description") or item.get("body") or "").strip()
    return {"title": title, "link": link, "description": description}


def _parse_next_data(html: str) -> dict | None:
    """Extract and decode the ``__NEXT_DATA__`` payload from a re:Post page."""
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        logger.warning("repost_search: __NEXT_DATA__ is not valid JSON")
        return None


def _hits_from_dom(html: str) -> list[dict]:
    """Fallback: scrape result anchors straight out of the rendered grid.

    Used only when ``__NEXT_DATA__`` is missing or its shape changed. Matches
    on ``data-testid`` and href shape rather than hashed CSS-module classes.
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(
        "div", attrs={"data-testid": "results-grid"}
    ) or soup.find("div", attrs={"data-testid": "results-list"})
    if container is None:
        return []

    href_re = re.compile(r"^/(questions|articles|knowledge-center)/[^/]+")
    hits: list[dict] = []
    seen: set[str] = set()
    for anchor in container.find_all("a", href=href_re):
        href = anchor.get("href")
        title = anchor.get_text(strip=True)
        if not title or href in seen:
            continue
        seen.add(href)
        hits.append({"title": title, "link": f"{BASE_URL}{href}", "description": ""})
    return hits


def repost_search(
    query: str,
    section: str = "questions",
    tag_ids: Iterable[str] | None = None,
    answered_only: bool = True,
) -> dict:
    """Search a single re:Post section.

    Args:
        query: Free-text search query.
        section: One of ``questions``, ``articles``, ``knowledge-center``,
            or the aggregate ``content``.
        tag_ids: Iterable of re:Post tag IDs. Defaults to the Amazon
            Connect tag. Pass an empty iterable to disable tag filtering.
        answered_only: When True (default), restrict ``questions`` to
            answered ones. Has no effect on the other sections.

    Returns:
        ``{"results": [...]}`` on success, or
        ``{"error": "...", "results": []}`` on failure.
    """
    raw_tags = (CONNECT_TAG_ID,) if tag_ids is None else tag_ids
    tags = [t for t in (_clean_tag_id(t) for t in raw_tags) if t]

    query_encoded = f"{quote_plus(query)}&sort=relevant"
    if answered_only:
        query_encoded += "&contentStatusFilter=answered"
    for tag_id in tags:
        query_encoded += f"&tagIds={tag_id}"
    final_url = f"{BASE_URL}/search/{section}?globalSearch={query_encoded}"

    logger.info("repost_search GET %s", final_url)

    try:
        response = requests.get(
            final_url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        html = response.text

        next_data = _parse_next_data(html)
        page_props = (
            (next_data or {}).get("props", {}).get("pageProps", {})
            if next_data
            else {}
        )

        # re:Post reports a failed backend search here rather than via HTTP
        # status, so an empty result set would otherwise look like "no hits".
        error = page_props.get("error")
        if error:
            code = error.get("code") if isinstance(error, dict) else error
            logger.error(
                "repost_search: re:Post returned %s for section=%s query=%r",
                code,
                section,
                query,
            )
            return {
                "error": f"re:Post search rejected the request ({code})",
                "results": [],
            }

        search_response = page_props.get("response") or {}
        content = search_response.get("content")

        if isinstance(content, list):
            results = [
                hit for item in content if (hit := _content_item_to_hit(item))
            ]
            logger.info(
                "repost_search: section=%s totalCount=%s parsed=%d",
                section,
                search_response.get("totalCount"),
                len(results),
            )
            return {"results": results}

        # __NEXT_DATA__ shape changed. Fall back to the DOM.
        logger.warning(
            "repost_search: no 'content' array in page payload for section=%s; "
            "falling back to DOM scrape",
            section,
        )
        return {"results": _hits_from_dom(html)}

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
    """Search all three re:Post content sections.

    Returns one dict keyed by section name. Any per-section errors are
    collected under the ``_errors`` key.
    """
    tags = list((CONNECT_TAG_ID,) if tag_ids is None else tag_ids)
    out: dict = {}
    errors: list[str] = []
    for index, section in enumerate(SECTIONS):
        section_result = repost_search(query, section, tags, answered_only)
        out[section] = section_result.get("results", [])
        if section_result.get("error"):
            errors.append(f"{section}: {section_result['error']}")
        if index < len(SECTIONS) - 1:
            time.sleep(1)  # be polite between requests
    if errors:
        out["_errors"] = errors
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
    errors = data.get("_errors", [])

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
        if errors:
            return f"AWS re:Post search failed for: {query}\n" + "\n".join(errors)
        return f"No AWS re:Post results found for: {query}"

    return "\n".join(lines)
