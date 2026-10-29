"""Search the AWS CDK v2 reference documentation.

``cdk_search`` queries the CDK site's own Pagefind index first
(``cdk_docs.pagefind``, the site's search WASM run in ``wasmtime``), and
falls back to the AWS docs search proxy (``docs_index_search``) when
Pagefind cannot run, for example on a network error or a Pagefind
version the module does not support.

Why Pagefind is primary: the docs search proxy, the endpoint behind
``docs.aws.amazon.com`` autocomplete, matches page titles well and
descriptions badly. "CfnGatewayTarget" found the page there, but
"agentcore gateway target" returned no AgentCore page at all, and its
snippet for every CDK hit is the same site blurb. Pagefind ranks on page
content, returns a real excerpt, and filters on ``module`` and ``kind``,
so "contact flow" limited to ``aws-connect`` constructs returns exactly
the ``CfnContactFlow*`` constructs.

Both paths keep only the stable ``aws-cdk-lib`` reference, dropping
``@aws-cdk/*`` alpha packages, mixin pages and CDK v1. Both return the
same ``Title / URL / Snippet`` blocks joined by ``\\n---\\n``, with the
``Error searching CDK docs: …`` and ``No CDK documentation results found
for: <query>`` conventions shared with ``connect_knowledge.docs.aws_search``.

The fallback says so on its first line, because its results differ in
kind: title matches only, a placeholder snippet, ``module`` applied to the
URL, and ``kind`` ignored. A silent fallback would read like a Pagefind
answer.
"""

from __future__ import annotations

import difflib
import logging
import re
import time

import requests

from cdk_docs import pagefind

logger = logging.getLogger(__name__)

DOCS_URL = "https://proxy.search.docs.aws.com/search"
DOCS_DOMAIN = "docs.aws.amazon.com"

# The CDK v2 reference for every language lives under ``cdk/api/v2/docs/``
# since AWS retired the Sphinx Python site at ``cdk/api/v2/python``. The
# docs index returns only the new addresses, so the old prefix matched
# nothing and every query reported no results. The ``aws-cdk-lib.``
# segment keeps the stable library, which holds all four in-scope
# modules, and drops the ``@aws-cdk_*`` alpha, mixin and preview packages
# that share the directory. CDK v1 pages sit under ``cdk/api/v1`` and stay
# excluded.
CDK_REFERENCE_PREFIX = "docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib."

# Appended to the user's query to bias the docs index toward CDK pages
# before URL-prefix filtering. Does not affect the returned text — the
# no-results message echoes the caller's original query verbatim.
CDK_QUERY_SCOPE = "AWS CDK Python"

# Appended to result URLs so a browser opens the Python tab; the site
# defaults to TypeScript.
PYTHON_VARIANT_QUERY = "lang=python"

MAX_RETRIES = 6
BACKOFF_BASE = 2
REQUEST_TIMEOUT = 30


def _python_variant(url: str) -> str:
    """Add ``?lang=python`` to a reference URL, keeping any ``#anchor``."""
    base, sep, anchor = url.partition("#")
    if "lang=" in base:
        return url
    joiner = "&" if "?" in base else "?"
    return f"{base}{joiner}{PYTHON_VARIANT_QUERY}{sep}{anchor}"


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
    """True when ``link`` points at the stable CDK v2 reference."""
    return CDK_REFERENCE_PREFIX in link


def _in_module(link: str, module: str | None) -> bool:
    """True when ``link`` is a page of Pagefind ``module`` (or no filter).

    The URL segment uses underscores, ``aws-cdk-lib.aws_connect.CfnX``,
    where the Pagefind value uses dashes, ``aws-connect``.
    """
    if not module:
        return True
    return f"aws-cdk-lib.{module.replace('-', '_')}." in link


def _format_hit(result: dict) -> str:
    """Render one cleaned hit as a Title / URL / Snippet block."""
    return (
        f"Title: {result.get('title', '')}\n"
        f"URL: {_python_variant(result.get('link', ''))}\n"
        f"Snippet: {result.get('summary', result.get('suggestionBody', ''))}"
    )


def docs_index_search(query: str, limit: int = 10, module: str | None = None) -> str:
    """Search the AWS docs search proxy, scoped to the CDK v2 reference.

    The fallback for ``cdk_search``. Matches page titles best; the snippet
    is the same site blurb for every CDK page.

    Args:
        query: Free-text search query.
        limit: Maximum number of hits to return (default 10).
        module: Pagefind-style ``module`` value (``aws-connect``), applied
            here as a URL segment filter.

    Returns:
        Multi-hit formatted block (``Title / URL / Snippet`` separated by
        ``\\n---\\n``), or an error / no-results string.
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
                r
                for r in cleaned
                if r and _is_cdk_reference(r["link"]) and _in_module(r["link"], module)
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


# Page chrome that follows a construct's lead sentence in Pagefind's
# excerpt: the CloudFormation badge, the "SourceType last changed" line,
# and the start of the TypeScript example.
_CHROME_RE = re.compile(r"\s*(?:CloudFormationAWS::|SourceType last changed|Example ts\b)")


def _clean_excerpt(excerpt: str, title: str, label: str) -> str:
    """Drop the ``<title> <label>`` heading and trailing page chrome.

    Pagefind excerpts are 30 words of page text around the match, so a
    construct hit reads "CfnBot L1 construct Specifies an Amazon Lex bot.
    CloudFormationAWS::Lex::BotSourceType last changed Example ts...".
    Only the lead sentence carries information. The chrome is cut only
    when text remains before it.
    """
    for head in (f"{title} {label}".strip(), title):
        if head and excerpt.startswith(head + " "):
            excerpt = excerpt[len(head) + 1 :]
            break
    match = _CHROME_RE.search(excerpt)
    if match and match.start() > 0:
        excerpt = excerpt[: match.start()]
    return excerpt.strip()


def _format_pagefind_hit(result: dict) -> str:
    """Render one Pagefind result as a Title / URL / Snippet block."""
    title = str(result.get("title") or "").strip()
    label = str(result.get("kind_label") or "").strip()
    shown = f"{title} ({label})" if label else title
    excerpt = _clean_excerpt(str(result.get("excerpt") or "").strip(), title, label)
    return (
        f"Title: {shown}\n"
        f"URL: {_python_variant(result['url'])}\n"
        f"Snippet: {excerpt}"
    )


def _unknown_filter_error(unknown: dict) -> str:
    """Describe filter values the index does not have, with close matches."""
    parts = []
    for name, info in sorted(unknown.items()):
        value = str(info.get("value"))
        known = [str(k) for k in info.get("known", [])]
        close = difflib.get_close_matches(value, known, n=5, cutoff=0.6)
        hint = close or known[:10]
        label = "closest values" if close else "some valid values"
        parts.append(f"unknown {name} {value!r}; {label}: {', '.join(hint)}")
    return "Error searching CDK docs: " + "; ".join(parts)


def _filter_suffix(module: str | None, kind: str | None) -> str:
    applied = [f"{n}={v}" for n, v in (("module", module), ("kind", kind)) if v]
    return f" ({', '.join(applied)})" if applied else ""


def cdk_search(
    query: str,
    limit: int = 10,
    module: str | None = None,
    kind: str | None = None,
) -> str:
    """Search the AWS CDK v2 reference and return formatted results.

    Args:
        query: Free-text search query.
        limit: Maximum number of hits to return (default 10).
        module: Restrict to one CDK module: ``aws-connect``,
            ``aws_connect`` or ``aws_cdk.aws_connect`` all work.
        kind: Restrict to one page kind: ``construct``, ``struct``,
            ``interface``, ``enum``, ``class``. Pagefind only.

    Returns:
        Multi-hit formatted block (``Title / URL / Snippet`` separated by
        ``\\n---\\n``), or an error / no-results string. When Pagefind is
        unavailable, the docs-index fallback result is prefixed with one
        ``Note:`` line naming the reason.
    """
    module_value = pagefind.normalize_module(module)
    kind_value = kind.strip().lower() if kind and kind.strip() else None

    try:
        reply = pagefind.run_pagefind(
            query, limit=limit, module=module_value, kind=kind_value
        )
    except pagefind.PagefindUnavailable as exc:
        logger.warning("Pagefind search unavailable, using docs index: %s", exc)
        ignored = " It ignores the kind filter." if kind_value else ""
        note = (
            f"Note: CDK site search unavailable ({exc}). These results come from "
            f"the AWS docs search index, which matches construct names best.{ignored}"
        )
        return f"{note}\n\n{docs_index_search(query, limit=limit, module=module_value)}"

    if reply.get("unknownFilters"):
        return _unknown_filter_error(reply["unknownFilters"])
    results = reply["results"]
    if not results:
        return (
            f"No CDK documentation results found for: {query}"
            f"{_filter_suffix(module_value, kind_value)}"
        )
    return "\n---\n".join(_format_pagefind_hit(r) for r in results)
