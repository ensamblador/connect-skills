"""Per-page deep-dive helpers for Connect docs.

Two entry points:

    get_block_doc(slug, section=None)   → admin-guide flow-block page
        e.g. slug="invoke-lambda-function-block"

    get_action_doc(slug, section=None)  → Flow language action reference page
        e.g. slug="interactions-invokelambdafunction"

Both fetch the markdown source of the page (AWS publishes ``.md``
alongside ``.html``) and return **that markdown**, with relative
cross-links rewritten to absolute URLs, plus the list of ``## ``
headings the page contains.

Markdown-first, deliberately. An earlier version mapped headings onto
fixed keys (``channels``, ``properties``, ``configuration_tips``). AWS
is migrating these pages to new wording — ``Supported channels`` became
``Contact types``, ``Properties`` became ``How to configure this
block``, and the flow-type bullet list became a table — which silently
emptied those keys on 10 of 58 block pages while the content sat right
there in the page. Worse, the empty value was indistinguishable from a
legitimately empty one.

Splitting on ``## `` hardcodes no heading names, so it cannot drift.
The ``section`` argument covers the one thing the field mapping was
genuinely good for, returning a slice instead of the whole page, and it
reports a miss instead of returning empty.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import requests
from requests.utils import get_encoding_from_headers

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 30

ADMINGUIDE_ROOT = "https://docs.aws.amazon.com/connect/latest/adminguide"
# The Flow language action reference used to live under /APIReference/;
# AWS moved it into the Connect Administrator/Developer guide
# (/devguide/). The old /APIReference/ URLs now 302-redirect away and
# have no .md source, so fetch the action pages from /devguide/.
FLOW_LANGUAGE_ROOT = "https://docs.aws.amazon.com/connect/latest/devguide"


# ----- fetching -----------------------------------------------------------


def _decoded_text(response: requests.Response) -> str:
    """Return ``response.text`` decoded with the right charset.

    ``requests`` derives ``response.encoding`` solely from the ``charset``
    parameter of the ``Content-Type`` header, falling back to the RFC 2616
    default of ISO-8859-1 for ``text/*`` when none is present. Decoding
    UTF-8 bytes as Latin-1 mangles every multi-byte sequence: an en dash
    (U+2013, ``e2 80 93``) arrives as ``â\\x80\\x93``.

    AWS currently serves the ``.md`` sources this module fetches *with*
    ``charset=utf-8``, so that path is fine today. This guard removes the
    dependency on an upstream header we do not control, and keeps the
    module correct if it is ever pointed at an ``.html`` page — those are
    served as a bare ``text/html`` and do exhibit the corruption.

    A charset the server actually declares is honoured.
    """
    content_type = response.headers.get("content-type", "")
    if "charset=" in content_type.lower():
        response.encoding = get_encoding_from_headers(response.headers)
    else:
        # Bare ``text/*``: requests would default to ISO-8859-1 here.
        response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def _fetch(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    return _decoded_text(r)


# ----- markdown structure parsing ----------------------------------------


_TOP_HEADING_RE = re.compile(r"^#\s+(?P<title>.+?)\s*$", re.MULTILINE)
_SECTION_RE = re.compile(r"^##\s+(?P<heading>.+?)\s*$", re.MULTILINE)
_ANCHOR_RE = re.compile(r'<a name="[^"]+"></a>\s*')


def _strip_anchors(text: str) -> str:
    return _ANCHOR_RE.sub("", text).strip()


def _parse_top_title(markdown: str) -> str | None:
    m = _TOP_HEADING_RE.search(markdown)
    return m.group("title").strip() if m else None


def _parse_lead_paragraph(markdown: str) -> str | None:
    """Return the first paragraph after the top heading, before any ``## `` section.

    Not used by the public fetchers, which return markdown verbatim.
    ``.kiro/scripts/refresh_connect_views.py`` imports it (lazily) to derive
    one-line blurbs for the admin-guide entries in the views catalog, so keep
    it even though nothing in this module calls it.
    """
    # Drop everything from the first ``## `` section onward.
    cut = _SECTION_RE.split(markdown, maxsplit=1)[0]
    # Drop everything up to and including the top ``# `` heading line.
    lines = cut.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            start = i + 1
            break
    body = "\n".join(lines[start:])
    body = _strip_anchors(body).strip()
    if not body:
        return None
    paragraph = body.split("\n\n", 1)[0]
    return " ".join(p.strip() for p in paragraph.splitlines() if p.strip()) or None


def _split_sections(markdown: str) -> dict[str, str]:
    """Split ``## ``-delimited sections, preserving order via dict insertion order."""
    parts = _SECTION_RE.split(markdown)
    # parts looks like: [pre, heading1, body1, heading2, body2, ...]
    out: dict[str, str] = {}
    if len(parts) <= 1:
        return out
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        body = _strip_anchors(body).strip()
        # Stop body at the next ``## `` if one accidentally slipped through (shouldn't).
        if "\n## " in body:
            body = body.split("\n## ", 1)[0].rstrip()
        out[heading] = body
    return out


# ----- relative-link rewriting -------------------------------------------


# AWS's ``.md`` sources cross-link with bare relative targets like
# ``(set-contact-attributes.md)`` or ``(connect-lambda-functions.md#anchor)``.
# Those resolve to nothing for a caller reading the markdown out of band, so
# rewrite them to absolute ``.html`` URLs against the page's own doc root.
# Absolute targets (http/https/mailto) and in-page anchors are left alone.
_RELATIVE_MD_LINK_RE = re.compile(r"\]\((?!https?://|mailto:|#)([^)\s]+?)\.md(#[^)\s]*)?\)")


def _rewrite_relative_links(markdown: str, root: str) -> str:
    """Turn relative ``.md`` cross-links into absolute ``.html`` URLs."""

    def _sub(m: re.Match[str]) -> str:
        stem, anchor = m.group(1), m.group(2) or ""
        return f"]({root}/{stem}.html{anchor})"

    return _RELATIVE_MD_LINK_RE.sub(_sub, markdown)


# ----- section selection --------------------------------------------------


def _select_section(sections: dict[str, str], wanted: str) -> tuple[str, str] | None:
    """Resolve a caller-supplied section name against the real headings.

    Matching is deliberately forgiving, because heading wording is AWS's to
    change: exact, then case-insensitive, then case-insensitive substring.
    Returns ``(heading, body)`` or ``None`` when nothing matches. It never
    guesses silently — the caller reports the miss along with the real
    heading list.
    """
    if wanted in sections:
        return wanted, sections[wanted]
    low = wanted.strip().lower()
    for heading, body in sections.items():
        if heading.lower() == low:
            return heading, body
    for heading, body in sections.items():
        if low in heading.lower():
            return heading, body
    return None


def _page_doc(slug: str, root: str, section: str | None) -> dict[str, Any]:
    """Shared markdown-first fetch for the admin-guide and devguide pages.

    Returns the page's own markdown rather than a fixed set of parsed
    fields. AWS reworks these pages' headings (``Supported channels``
    became ``Contact types``; ``Properties`` became ``How to configure
    this block``), so any mapping of heading names onto named keys goes
    stale silently. Splitting on ``## `` does not: it reads whatever
    headings the page actually has.

    ``sections`` lists those headings so a caller can discover the page
    shape cheaply, then re-request one section by name to keep the
    payload small.
    """
    md = _fetch(f"{root}/{slug}.md")
    md = _rewrite_relative_links(md, root)

    title = _parse_top_title(md) or slug
    # Block pages title as "Flow block in <product>: <Block name>".
    name = title.split(":", 1)[1].strip() if ":" in title else title
    sections = _split_sections(md)

    doc: dict[str, Any] = {
        "slug": slug,
        "name": name,
        "title": title,
        "url": f"{root}/{slug}.html",
        "sections": list(sections),
        "section": None,
        "markdown": md,
    }

    if section is None:
        return doc

    hit = _select_section(sections, section)
    if hit is None:
        doc["markdown"] = ""
        doc["error"] = (
            f"No section matching {section!r} on this page. "
            f"Available sections: {', '.join(sections) or '(none)'}. "
            f"Omit 'section' to get the whole page."
        )
        return doc

    heading, body = hit
    doc["section"] = heading
    doc["markdown"] = f"## {heading}\n\n{body}".rstrip() + "\n"
    return doc


# ----- public API ---------------------------------------------------------


def get_block_doc(slug: str, section: str | None = None) -> dict[str, Any]:
    """Fetch an admin-guide flow-block page as markdown.

    Args:
        slug: The page slug (no extension), e.g.
            ``invoke-lambda-function-block`` or ``get-customer-input``.
        section: Optional ``## `` heading to return instead of the whole
            page, matched exactly, then case-insensitively, then by
            substring. Use it to keep the payload small once
            ``sections`` has told you what the page contains.

    Returns:
        Dict with ``slug``, ``name``, ``title``, ``url``, ``sections``
        (every ``## `` heading on the page), ``section`` (which one was
        returned, ``None`` for the whole page), and ``markdown``. On a
        section miss, ``markdown`` is empty and ``error`` explains,
        listing the real headings.
    """
    return _page_doc(slug, ADMINGUIDE_ROOT, section)


def get_action_doc(slug: str, section: str | None = None) -> dict[str, Any]:
    """Fetch a Flow language action reference page as markdown.

    Args:
        slug: The page slug (no extension), e.g.
            ``interactions-invokelambdafunction`` or
            ``contact-actions-tagcontact``.
        section: Optional ``## `` heading to return instead of the whole
            page. ``"Parameter object"`` is the usual one when writing
            flow JSON.

    Returns:
        Same shape as :func:`get_block_doc`.
    """
    return _page_doc(slug, FLOW_LANGUAGE_ROOT, section)
