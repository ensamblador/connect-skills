"""Search AWS blogs: the aws.amazon.com ranked search, with a keyword fallback.

Ported from the connect-mcp gateway target Lambda
(``agentcore-gateway-primitive``, ``connect_tools.aws_blog_search``). The
default blog list is tuned for Amazon Connect work: contact center,
partner network, and messaging.

Two backends, tried in order:

1. ``ranked_blog_search``: ``POST prod.search.marketing.aws.dev/api/v1/search``
   with provider ``blogs``, the search behind the aws.amazon.com search
   box. It ranks by relevance and returns publish dates.
2. ``directory_blog_search``: the aws.amazon.com directories API that backs
   the blog listing pages. It is a keyword filter, not a search engine:
   every item scores 0.0, order is by date only, and ``Cases`` does not
   match ``Case``, so "Amazon Connect Cases" never returned "Rethinking the
   Case" (2026-06-09). This module re-ranks its results by whole-word
   matches.

``aws_blog_search`` uses the second only when the first fails or keeps
nothing from the requested blogs, and then prefixes one ``Note:`` line
naming the reason, because keyword-filter results differ in kind and a
silent switch would read like a ranked answer.

The history: the CloudSearch endpoint ``aws.amazon.com/search/p/2013-01-01/search``
used before was retired in October 2026 and answers every query with a
static empty body. The directories API replaced it, then the ranked search
replaced that as primary.

Ranked-search behaviour measured on 2026-10-29, which shapes the code:

- Only the top 30 results are reachable. ``limit`` is capped at 30, and an
  ``offset`` of 30 or more returns the first page again, so one request
  with ``limit`` 30 is all there is. ``hasMore`` stays ``true`` regardless.
- Queries of one or two words score lexically, from about 1e3 to 1e28,
  and append a fuzzy tail of one-edit matches: "chile" also returns posts
  saying "while" or "Chime", "callback" returns "fallback" and "rollback".
  Those tail results never contain the query word in their title or
  excerpt, while every real hit measured did. So in this mode a result is
  kept only when every query word, or its singular or plural, appears in
  the visible text. A score-ratio cut does not work: real "Connect Cases"
  hits span 5e27 to 7e19.
- Longer queries score semantically, between about 1.8 and 2.3. These
  results need not repeat the query words, so nothing is dropped. The
  mode is told apart by the top score: above ``LEXICAL_SCORE_FLOOR`` is
  lexical.
- The request has no blog filter. Blogs are filtered on the URL slug, the
  segment after ``/blogs/``, after the fetch.

Callers written against CloudSearch pass display names such as
``AWS Machine Learning Blog``. ``BLOG_NAME_ALIASES`` maps the known ones
to slugs. An unrecognised display name returns an error naming the
accepted forms, rather than a silent empty result.
"""

from __future__ import annotations

import html
import logging
import re
import time
from collections.abc import Iterable
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

RANKED_SEARCH_URL = "https://prod.search.marketing.aws.dev/api/v1/search"
BLOGS_URL = "https://aws.amazon.com/api/dirs/items/search"

# Blog URL slugs: the segment after /blogs/ in a post URL.
DEFAULT_BLOGS: tuple[str, ...] = (
    "contact-center",  # AWS Contact Center
    "apn",  # AWS Partner Network (APN) Blog
    "messaging-and-targeting",  # AWS Messaging Blog
)

# Display names accepted for backward compatibility, matched
# case-insensitively. Anything else must be passed as a slug.
BLOG_NAME_ALIASES: dict[str, str] = {
    "AWS Contact Center": "contact-center",
    "AWS Partner Network (APN) Blog": "apn",
    "AWS Messaging Blog": "messaging-and-targeting",
    "AWS Machine Learning Blog": "machine-learning",
}
_ALIAS_LOOKUP = {name.lower(): slug for name, slug in BLOG_NAME_ALIASES.items()}

MAX_BLOG_RESULTS = 25

# Ranked search: the API rejects a larger limit, and nothing past the
# first 30 is reachable anyway.
RANKED_LIMIT = 30
# Top scores above this mean the lexical mode; semantic scores stay
# below about 2.3, and the lowest lexical score measured was about 1.7e3.
LEXICAL_SCORE_FLOOR = 100.0
# Few retries: a failure falls back to the directory API, so waiting a
# minute on backoff would only delay an answer that exists.
RANKED_MAX_RETRIES = 3

# Directory API: candidates fetched before client-side re-ranking. Filtering
# by blog needs the larger pool because the filter runs after the fetch.
BLOG_POOL_SIZE = 100
BLOG_POOL_SIZE_FILTERED = 500

MAX_RETRIES = 6
BACKOFF_BASE = 2
REQUEST_TIMEOUT = 30

_RETRYABLE = (429, 500, 502, 503)
_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_TERM_RE = re.compile(r"[a-z0-9]+")


class RankedSearchUnavailable(RuntimeError):
    """The ranked search could not answer; ``str()`` is the reason."""


def _resolve_blog_slugs(blogs: Iterable[str]) -> tuple[set[str], list[str]]:
    """Map caller-supplied blog names or slugs to URL slugs.

    Args:
        blogs: Blog URL slugs or known display names.

    Returns:
        ``(slugs, unknown)``: the resolved slugs, and the entries that
        are neither a known display name nor slug-shaped.
    """
    slugs: set[str] = set()
    unknown: list[str] = []
    for raw in blogs:
        name = raw.strip()
        alias = _ALIAS_LOOKUP.get(name.lower())
        if alias:
            slugs.add(alias)
        elif _SLUG_RE.fullmatch(name):
            slugs.add(name)
        else:
            unknown.append(raw)
    return slugs, unknown


def _blog_slug(link: str) -> str:
    """Return the blog slug from a post URL (``/blogs/<slug>/<post>/``)."""
    parts = [p for p in urlparse(link).path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "blogs":
        return parts[1]
    return ""


def _is_listing_page(link: str) -> bool:
    """Author and tag pages are listings, not posts."""
    return "/author/" in link or "/tag/" in link


def _format_hit(result: dict) -> str:
    """Render one cleaned hit as a Title / URL / Published / Snippet block."""
    return (
        f"Title: {result.get('title', '')}\n"
        f"URL: {result.get('link', '')}\n"
        f"Published: {result.get('date', '')}\n"
        f"Snippet: {result.get('description', '')}"
    )


# ----- ranked search ----------------------------------------------------------


def _term_forms(term: str) -> tuple[str, ...]:
    """A query word and its simple singular or plural."""
    if term.endswith("s") and len(term) > 3:
        return (term, term[:-1])
    return (term, term + "s")


def _contains_every_term(text: str, terms: list[str]) -> bool:
    """True when each term, or its singular/plural, is a whole word in ``text``."""
    lowered = text.lower()
    return all(
        any(re.search(rf"\b{re.escape(form)}\b", lowered) for form in _term_forms(t))
        for t in terms
    )


def _clean_ranked_result(result: dict) -> dict:
    """Extract the fields the tool prints from one ranked-search result."""
    link = result.get("url")
    if not isinstance(link, str) or not link:
        return {}
    metadata = result.get("metadata") or {}
    date = (metadata.get("isoTimestamp") or "")[:10] or metadata.get("date", "")
    chunks = [c for c in result.get("relevantChunks") or [] if isinstance(c, str)]
    return {
        "title": html.unescape(str(result.get("title") or "")),
        "link": link,
        "description": html.unescape(str(result.get("description") or "")),
        "date": date,
        "chunks": chunks,
        "score": result.get("score"),
    }


def _fetch_ranked(query: str) -> list[dict]:
    """POST one ranked-search request; return its raw ``results`` list."""
    body = {
        "query": {
            "text": query,
            "locale": "en-US",
            "pagination": {"offset": 0, "limit": RANKED_LIMIT},
        },
        "providers": [{"name": "blogs"}],
    }
    last_reason = ""
    for attempt in range(RANKED_MAX_RETRIES):
        try:
            response = requests.post(RANKED_SEARCH_URL, json=body, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise RankedSearchUnavailable(f"request failed: {exc}") from exc
        if response.status_code in _RETRYABLE:
            last_reason = f"HTTP {response.status_code}"
            if attempt + 1 < RANKED_MAX_RETRIES:
                wait = BACKOFF_BASE**attempt
                logger.warning(
                    "ranked blog search attempt %d/%d got %s, retrying in %ds",
                    attempt + 1,
                    RANKED_MAX_RETRIES,
                    last_reason,
                    wait,
                )
                time.sleep(wait)
            continue
        if response.status_code != 200:
            raise RankedSearchUnavailable(f"HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise RankedSearchUnavailable("response was not JSON") from exc
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            raise RankedSearchUnavailable("response has no 'results' list")
        return results
    raise RankedSearchUnavailable(f"{last_reason} after {RANKED_MAX_RETRIES} attempts")


def ranked_blog_search(
    query: str,
    include_blogs: set[str],
    page_size: int = MAX_BLOG_RESULTS,
) -> list[dict]:
    """Search AWS blogs with the aws.amazon.com ranked search.

    Args:
        query: Free-text search query.
        include_blogs: Blog URL slugs to keep; empty keeps every blog.
        page_size: Maximum number of hits returned.

    Returns:
        Cleaned hits in the API's rank order, each a dict with ``title``,
        ``link``, ``description`` and ``date``. May be empty.

    Raises:
        RankedSearchUnavailable: On a transport error, a non-200 reply
            after retries, or a reply without a ``results`` list.
    """
    raw = _fetch_ranked(query)
    cleaned = [c for c in (_clean_ranked_result(r) for r in raw if isinstance(r, dict)) if c]
    scores = [c["score"] for c in cleaned if isinstance(c["score"], (int, float))]
    lexical = bool(scores) and max(scores) > LEXICAL_SCORE_FLOOR
    terms = _TERM_RE.findall(query.lower())

    hits: list[dict] = []
    seen: set[str] = set()
    for item in cleaned:
        link = item["link"]
        if link in seen or _is_listing_page(link):
            continue
        if include_blogs and _blog_slug(link) not in include_blogs:
            continue
        if lexical and terms:
            visible = " ".join([item["title"], item["description"], *item["chunks"]])
            if not _contains_every_term(visible, terms):
                continue  # one-edit fuzzy match, e.g. "chile" -> "while"
        seen.add(link)
        hits.append(item)
        if len(hits) >= page_size:
            break
    return hits


# ----- directory API fallback -------------------------------------------------


def _clean_blog_result(item: dict) -> dict:
    """Extract and clean fields from a directories API blog item."""
    fields = (item.get("item") or {}).get("additionalFields") or {}
    link = fields.get("link")
    if not link:
        return {}
    return {
        "title": html.unescape(fields.get("title", "")),
        "link": link,
        "description": html.unescape(fields.get("postExcerpt", "")),
        "date": (fields.get("createdDate") or "")[:10],
    }


def _relevance(result: dict, terms: list[str]) -> int:
    """Score a blog result by whole-word query term matches.

    A title match counts 2, an excerpt match counts 1.
    """
    title = result["title"].lower()
    description = result["description"].lower()
    score = 0
    for term in terms:
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, title):
            score += 2
        if re.search(pattern, description):
            score += 1
    return score


def directory_blog_search(
    query: str,
    include_blogs: set[str],
    page_size: int = MAX_BLOG_RESULTS,
) -> str:
    """Search AWS blogs through the aws.amazon.com directories API.

    Fetches English posts that contain every query term, keeps only
    ``include_blogs``, and re-ranks by whole-word term matches in the
    title and excerpt. ``sorted`` is stable, so equal scores keep the
    API's newest-first order.

    Args:
        query: Free-text search query.
        include_blogs: Blog URL slugs to keep; empty keeps every blog.
        page_size: Maximum number of hits returned after re-ranking.

    Returns:
        Multi-hit formatted block, or an error / no-results string.
    """
    params = {
        "item.directoryId": "blog-posts",
        "item.locale": "en_US",
        "sort_by": "item.additionalFields.createdDate",
        "sort_order": "desc",
        "size": BLOG_POOL_SIZE_FILTERED if include_blogs else BLOG_POOL_SIZE,
        "q": query,
        "q_operator": "AND",
    }
    terms = _TERM_RE.findall(query.lower())

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(BLOGS_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            results: list[dict] = []
            for item in data.get("items", []):
                cleaned = _clean_blog_result(item)
                if not cleaned:
                    continue
                link = cleaned["link"]
                if _is_listing_page(link):
                    continue
                if include_blogs and _blog_slug(link) not in include_blogs:
                    continue
                results.append(cleaned)

            if not results:
                return f"No AWS blog results found for: {query}"

            results = sorted(results, key=lambda r: _relevance(r, terms), reverse=True)
            return "\n---\n".join(_format_hit(r) for r in results[:page_size])

        except requests.exceptions.HTTPError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else None
            if status in _RETRYABLE:
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


# ----- public entry point -----------------------------------------------------


def aws_blog_search(
    query: str,
    blogs: Iterable[str] | None = None,
    page_size: int = MAX_BLOG_RESULTS,
) -> str:
    """Search AWS blogs and return formatted text results.

    Args:
        query: Free-text search query.
        blogs: Iterable of blog URL slugs (``contact-center``,
            ``machine-learning``) or known display names to restrict the
            search to. Defaults to ``DEFAULT_BLOGS`` (Connect-tuned). Pass
            an empty iterable to search all AWS blogs.
        page_size: Maximum number of hits returned.

    Returns:
        Multi-hit formatted block (``Title / URL / Published / Snippet``
        joined by ``\\n---\\n``), or an error / no-results string. When the
        directory fallback answered, the block is prefixed with one
        ``Note:`` line and a blank line.
    """
    include_blogs, unknown = _resolve_blog_slugs(
        DEFAULT_BLOGS if blogs is None else blogs
    )
    if unknown:
        known = ", ".join(BLOG_NAME_ALIASES)
        return (
            f"Error searching AWS blogs: unknown blog name(s) {unknown}. Pass "
            "a URL slug, the segment after /blogs/ in a post URL (for "
            f"example 'machine-learning'), or one of these names: {known}"
        )

    try:
        hits = ranked_blog_search(query, include_blogs, page_size=page_size)
    except RankedSearchUnavailable as exc:
        logger.warning("ranked blog search unavailable, using directory API: %s", exc)
        reason = f"the ranked AWS search is unavailable ({exc})"
    else:
        if hits:
            return "\n---\n".join(_format_hit(h) for h in hits)
        scope = "these blogs" if include_blogs else "any blog"
        reason = f"the ranked AWS search kept no posts from {scope} in its top {RANKED_LIMIT}"

    note = (
        f"Note: {reason}. These results come from the AWS blog directory, a "
        "keyword filter ranked locally by word matches, so expect more noise."
    )
    return f"{note}\n\n{directory_blog_search(query, include_blogs, page_size=page_size)}"
