"""Per-page deep-dive helpers for Connect docs.

Two entry points:

    get_block_doc(slug)   → admin-guide flow-block page
        e.g. slug="invoke-lambda-function-block"

    get_action_doc(slug)  → API-reference flow-language action page
        e.g. slug="interactions-invokelambdafunction"

Both fetch the markdown source of the page (AWS publishes ``.md``
alongside ``.html``), split it into named sections by ``## `` heading,
and surface the most useful fields as named keys plus the full
``raw_sections`` map as an escape hatch for callers that need
content the parser doesn't know to extract.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 30

ADMINGUIDE_ROOT = "https://docs.aws.amazon.com/connect/latest/adminguide"
API_REF_ROOT = "https://docs.aws.amazon.com/connect/latest/APIReference"


# ----- fetching -----------------------------------------------------------


def _fetch(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


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
    """Return the first paragraph after the top heading, before any ``## `` section."""
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


# ----- channel-table extraction (block pages only) -----------------------


_CHANNEL_TABLE_HEADER_RE = re.compile(
    r"^\|\s*Channel\s*\|\s*Supported\?\s*\|\s*$", re.MULTILINE
)


def _extract_channels(supported_channels_section: str) -> dict[str, str]:
    """Pull the Voice/Chat/Task/Email rows out of the Supported channels section."""
    channels: dict[str, str] = {}
    if not _CHANNEL_TABLE_HEADER_RE.search(supported_channels_section):
        return channels
    for line in supported_channels_section.splitlines():
        line = line.strip()
        if not line.startswith("|") or "|" not in line[1:]:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 2:
            continue
        ch, val = cells
        if ch in {"Voice", "Chat", "Task", "Email"}:
            channels[ch] = val
    return channels


# ----- flow-types extraction ----------------------------------------------


def _extract_bullet_list(section: str) -> list[str]:
    """Pull a leading bullet list out of a section body."""
    items: list[str] = []
    for line in section.splitlines():
        s = line.strip()
        if s.startswith("+ ") or s.startswith("- "):
            items.append(s[2:].strip())
        elif items and not s:
            # blank line after the list ends the list
            break
    return items


# ----- API-reference: corresponding-block link ---------------------------


_LINK_RE = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<href>[^)]+)\)")


def _extract_first_link(section: str) -> tuple[str, str] | None:
    m = _LINK_RE.search(section)
    if not m:
        return None
    return m.group("text").strip(), m.group("href").strip()


# ----- public API ---------------------------------------------------------


def get_block_doc(slug: str) -> dict[str, Any]:
    """Fetch and parse an admin-guide flow-block page.

    Args:
        slug: The page slug (no extension), e.g.
            ``invoke-lambda-function-block`` or ``get-customer-input``.

    Returns:
        Dict with ``name``, ``url``, ``description``, ``channels``,
        ``flow_types``, ``properties``, ``configuration_tips``, plus the
        full ``raw_sections`` map.
    """
    url_md = f"{ADMINGUIDE_ROOT}/{slug}.md"
    url_html = f"{ADMINGUIDE_ROOT}/{slug}.html"
    md = _fetch(url_md)

    title = _parse_top_title(md) or slug
    name = title.split(":", 1)[1].strip() if ":" in title else title

    sections = _split_sections(md)

    return {
        "name": name,
        "title": title,
        "url": url_html,
        "description": sections.get("Description") or _parse_lead_paragraph(md),
        "channels": _extract_channels(sections.get("Supported channels", "")),
        "flow_types": _extract_bullet_list(sections.get("Flow types", "")),
        "properties": sections.get("Properties"),
        "configuration_tips": sections.get("Configuration tips"),
        "raw_sections": sections,
    }


def get_action_doc(slug: str) -> dict[str, Any]:
    """Fetch and parse a Flow language action reference page.

    Args:
        slug: The page slug (no extension), e.g.
            ``interactions-invokelambdafunction`` or
            ``contact-actions-tagcontact``.

    Returns:
        Dict with ``name``, ``url``, ``description``, ``parameter_object``,
        ``results_and_conditions``, ``errors``, ``restrictions``,
        ``corresponding_block``, plus the full ``raw_sections`` map.
    """
    url_md = f"{API_REF_ROOT}/{slug}.md"
    url_html = f"{API_REF_ROOT}/{slug}.html"
    md = _fetch(url_md)

    name = _parse_top_title(md) or slug
    description = _parse_lead_paragraph(md)
    sections = _split_sections(md)

    corresponding = None
    corr_section = sections.get("Corresponding block in the UI")
    if corr_section:
        link = _extract_first_link(corr_section)
        if link:
            corresponding = {"text": link[0], "url": link[1]}

    errors_list = _extract_bullet_list(sections.get("Errors", ""))

    return {
        "name": name,
        "url": url_html,
        "description": description,
        "parameter_object": sections.get("Parameter object"),
        "results_and_conditions": sections.get("Results and conditions"),
        "errors": errors_list,
        "restrictions": sections.get("Restrictions"),
        "corresponding_block": corresponding,
        "raw_sections": sections,
    }
