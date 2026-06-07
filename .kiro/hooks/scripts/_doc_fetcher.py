"""Shared HTTP fetcher with 404 self-healing for the refresh scripts.

Every ``refresh_*.py`` script in this directory pulls source pages from
``docs.aws.amazon.com``. AWS occasionally restructures the Connect
docs (e.g. moving the Flow language reference out of ``/APIReference/``
and into ``/devguide/``), which silently 404s every URL we had hard-coded.

Rather than each script handling that risk on its own, this module:

1. Wraps :func:`requests.get` with a typed :class:`NotFoundError` so 404
   is distinguishable from transient network errors.
2. Exposes :func:`resolve_url_via_search` which calls the
   ``connect_knowledge`` package's :func:`aws_search` (the same docs
   index the connect-knowledge MCP exposes) to look up the live URL
   for a given page slug.
3. Exposes :func:`fetch_with_fallback` which tries the original URL,
   and on 404 asks the resolver, retries against the resolved URL,
   and returns ``(final_url, body)``.

Intended usage from a refresh script::

    from _doc_fetcher import fetch_with_fallback, NotFoundError

    final_url, body = fetch_with_fallback(
        url, query_hint="amazon connect flow blocks"
    )
    if final_url != url:
        # The page moved; thread final_url back into the rendered output
        # so generated links point at the live page.
        ...

The ``query_hint`` matters: it biases the docs search so generic slugs
(``loop``, ``compare``) still resolve correctly. Pass enough context to
disambiguate (product + topic).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import requests

# The connect_knowledge package lives under ``connect_knowledge_mcp/``
# (installed editable by the root pyproject) and exposes ``aws_search``.
# When invoked via ``uv run`` the package is already importable; the
# sys.path insert is a belt-and-suspenders fallback so the module also
# resolves when run with a bare interpreter. This file lives at
# ``.kiro/hooks/scripts/`` — three levels under the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "connect_knowledge_mcp"))
from connect_knowledge import aws_search  # noqa: E402

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 30

# Default URL prefix the resolver will accept hits from. Every refresh
# script in this repo currently targets the Connect docs; override per
# call if you ever point a refresh script at a different product.
DEFAULT_URL_PREFIX = "/connect/latest/"

# URL: <link>  rows in the aws_search response, one per hit.
_SEARCH_URL_RE = re.compile(r"^URL:\s*(?P<url>https?://\S+)\s*$", re.MULTILINE)


# ----- exceptions ---------------------------------------------------------


class NotFoundError(Exception):
    """Raised when a docs page 404s — the trigger for the search fallback."""

    def __init__(self, url: str):
        super().__init__(f"404 Not Found: {url}")
        self.url = url


# ----- low-level fetch ----------------------------------------------------


def fetch(url: str, *, headers: dict[str, str] | None = None) -> str:
    """GET ``url`` and return body text. 404s raise :class:`NotFoundError`.

    All other HTTP errors raise :class:`requests.HTTPError` as usual.
    """
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    r = requests.get(url, headers=request_headers, timeout=TIMEOUT)
    if r.status_code == 404:
        raise NotFoundError(url)
    r.raise_for_status()
    return r.text


# ----- search-backed URL resolver -----------------------------------------


def _slug_from_url(url: str) -> str:
    """``…/devguide/foo-bar.html`` → ``foo-bar``. Tail only, no host or path."""
    tail = url.rsplit("/", 1)[-1]
    if tail.endswith(".html"):
        tail = tail[:-5]
    elif tail.endswith(".md"):
        tail = tail[:-3]
    return tail


def resolve_url_via_search(
    slug: str,
    query_hint: str = "",
    *,
    url_prefix: str = DEFAULT_URL_PREFIX,
    limit: int = 10,
    allow_renamed: bool = False,
) -> str | None:
    """Ask the AWS docs search index for the live page matching ``slug``.

    Returns a full ``https://docs.aws.amazon.com/...`` URL on success,
    or ``None`` if the search couldn't find a matching page.

    Args:
        slug: The page slug to look up, e.g. ``flow-control-actions-loop``.
        query_hint: Free-text bias for the search ("amazon connect flow
            language", "amazon connect flow blocks", …). Required in
            practice — slugs alone are often too generic.
        url_prefix: Only accept hits whose URL contains this substring
            (defaults to the Connect docs subtree). Override to broaden
            or narrow the match.
        limit: How many search hits to consider before giving up.
        allow_renamed: When ``True``, fall back to the first prefix-matching
            hit if no exact slug match is found in the top ``limit``
            results. Useful when a page has genuinely been renamed; risky
            because the search engine's top hit for a stale slug isn't
            always the right page. Off by default — callers that prefer
            "fail loud over follow the wrong link" don't have to pay
            for that risk.
    """
    query = f"site:docs.aws.amazon.com {slug} {query_hint}".strip()
    try:
        text = aws_search(query, limit=limit)
    except Exception as exc:  # noqa: BLE001 — any failure means "no result"
        print(f"    search resolver failed: {exc}", file=sys.stderr)
        return None
    if (
        not text
        or text.startswith("No AWS documentation results")
        or text.startswith("Error")
    ):
        return None

    # Prefer an exact slug match under the desired URL prefix.
    candidates: list[str] = []
    for m in _SEARCH_URL_RE.finditer(text):
        url = m.group("url")
        if url_prefix not in url:
            continue
        if _slug_from_url(url) == slug:
            return url
        candidates.append(url)
    if not allow_renamed:
        return None
    # Loose fallback: first prefix-matching hit. Use sparingly — a stale
    # slug's top hit can be a tangentially related page rather than the
    # renamed target.
    return candidates[0] if candidates else None


# ----- self-healing fetch -------------------------------------------------


def fetch_with_fallback(
    url: str,
    query_hint: str = "",
    *,
    url_prefix: str = DEFAULT_URL_PREFIX,
    headers: dict[str, str] | None = None,
    verbose: bool = True,
    allow_renamed: bool = False,
) -> tuple[str, str]:
    """Fetch ``url``; on 404, resolve via the docs search and retry once.

    Returns ``(final_url, body)``. ``final_url`` may differ from the
    input if the resolver pointed us at a moved page. Raises if both
    the original fetch and the resolved fetch fail.

    Args:
        url: The URL to fetch.
        query_hint: Extra search bias passed to
            :func:`resolve_url_via_search` if the original URL 404s.
        url_prefix: URL prefix the resolver will accept hits from.
        headers: Extra request headers (passed through to :func:`fetch`).
        verbose: Print 404/recovery progress to stderr. Set ``False``
            for tight inner loops where the noise isn't useful.
        allow_renamed: When ``True``, the resolver may follow a hit
            whose slug doesn't match the original (i.e. the page was
            renamed). Off by default — see
            :func:`resolve_url_via_search` for the tradeoff.
    """
    try:
        return url, fetch(url, headers=headers)
    except NotFoundError:
        slug = _slug_from_url(url)
        if verbose:
            print(
                f"  404 from {url}; asking connect-knowledge docs search "
                f"for the live page for slug '{slug}'",
                file=sys.stderr,
            )
        resolved = resolve_url_via_search(
            slug,
            query_hint=query_hint,
            url_prefix=url_prefix,
            allow_renamed=allow_renamed,
        )
        if not resolved or resolved == url:
            raise
        if verbose:
            print(f"    resolver suggested {resolved}", file=sys.stderr)
        # Try the markdown source first if the resolver gave us .html;
        # the refresh scripts generally prefer the .md source for parsing.
        if resolved.endswith(".html"):
            md_url = resolved[:-5] + ".md"
            try:
                return resolved, fetch(md_url, headers=headers)
            except NotFoundError:
                pass
        return resolved, fetch(resolved, headers=headers)


__all__ = [
    "DEFAULT_URL_PREFIX",
    "NotFoundError",
    "TIMEOUT",
    "USER_AGENT",
    "fetch",
    "fetch_with_fallback",
    "resolve_url_via_search",
]
