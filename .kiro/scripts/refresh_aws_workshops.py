"""Refresh ``.kiro/steering/aws-workshops.md`` from the AWS workshop catalog.

The Workshop Studio landing pages are JavaScript-rendered, so a plain
``requests.get`` returns an empty shell. We drive a headless Chromium
session via Playwright (the same machinery that powers
``.kiro/scripts/refresh_connect_views.py``) to render each page, then
extract:

- the workshop title (``<h1>``)
- the module list (every link inside the left-hand sidebar, falling
  back to the ``Additional Links`` block at the bottom of the page)

Per-workshop curated content (one-liner, audience, time, cost, regions,
builds) lives in this file under ``CURATED`` and is hand-authored.
The script combines curated copy with freshly fetched titles + module
links, writes the steering file, and refreshes ``last_refreshed`` plus
the content checksum.

Source pages (rendered with Playwright):
    - https://catalog.workshops.aws/self-service-ai-agents/en-US
    - https://catalog.workshops.aws/amazon-connect-fundamentals/en-US
    - https://catalog.workshops.aws/amazon-connect-ai-agents/en-US
    - https://catalog.us-east-1.prod.workshops.aws/workshops/b60d8bf5-1afe-460f-ba05-6e7ad35d37f9/en-US
    - https://catalog.workshops.aws/amazon-connect-3p-applications/en-US
    - https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US
    - https://catalog.us-east-1.prod.workshops.aws/workshops/705f4a6b-6c3f-42ed-bb60-a76e27e78028/en-US
    - https://catalog.workshops.aws/amazon-connect-rules-engine/en-US
    - https://catalog.workshops.aws/amazon-connect-profiles/en-US
    - https://catalog.workshops.aws/amazon-connect-email/en-US
    - https://catalog.workshops.aws/amazon-connect-optimization/en-US
    - https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US
    - https://catalog.us-east-1.prod.workshops.aws/workshops/dd046ddd-9305-417e-b620-ac4ffc378690/en-US
    - Salesforce Contact Center with Amazon Connect bootcamp (4 modules
      with their own sub-modules, curated bundle — landing page is
      module 1):
        - https://catalog.us-east-1.prod.workshops.aws/workshops/f91b5bee-9028-47c0-b1c5-11acfec7c9f3/en-US
        - https://catalog.us-east-1.prod.workshops.aws/workshops/401c630f-2901-4f2d-8468-bd9a9066a78f/en-US
        - https://catalog.us-east-1.prod.workshops.aws/workshops/a0299a82-da56-4bd0-b8cb-d7f76dd42d09/en-US
        - https://catalog.us-east-1.prod.workshops.aws/workshops/f33ac20c-57f6-45ee-89fc-f80c5522e2bf/en-US

Run:
    uv run python .kiro/scripts/refresh_aws_workshops.py            # write
    uv run python .kiro/scripts/refresh_aws_workshops.py --dry-run  # preview
    uv run python .kiro/scripts/refresh_aws_workshops.py --only fundamentals
        # refresh a single workshop by slug

Setup (first time only):
    uv sync                                          # installs playwright (transitive core dep)
    uv run python -m playwright install chromium
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

# This script lives at ``.kiro/scripts/`` — two levels under the
# repo root (scripts → .kiro → repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / ".kiro" / "steering" / "aws-workshops.md"

NAV_TIMEOUT_MS = 45_000


# ----- curated copy -------------------------------------------------------


@dataclass
class WorkshopModuleGroup:
    """A top-level module inside a curated bundle, with an abstract.

    Used by multi-workshop bootcamps where each "module" is itself a
    separate Workshop Studio workshop (e.g. the Salesforce Contact
    Center with Amazon Connect series). Instead of enumerating every
    nested lesson, we keep the catalog at the module level and let
    ``abstract`` carry a paragraph-style summary so the agent can
    pick the right module without opening the page.

    The renderer emits the group as a single bullet with the abstract
    on the next line (indented), like:

    - **[Module 1: ...](url)**
      Abstract sentence describing what the module covers.
    """

    label: str
    url: str
    abstract: str


@dataclass
class WorkshopCurated:
    slug: str  # used by --only
    landing_url: str
    one_liner: str
    # When set, the renderer uses these (label, url) pairs verbatim
    # instead of asking Playwright to render the landing page and scrape
    # the sidebar. Use this when a single catalog "entry" is actually a
    # curated bundle of separate workshop landing pages (e.g. a
    # multi-module bootcamp series where each module has its own
    # workshop UUID).
    modules: tuple[tuple[str, str], ...] | None = None
    # When set, takes precedence over both ``modules`` and any
    # live-scraped sidebar. Use for curated bundles where each top-level
    # module also exposes its own internal sub-modules and you want the
    # steering file to render the full nested tree.
    module_groups: tuple[WorkshopModuleGroup, ...] | None = None
    # Optional H2 override. When set, takes precedence over the live H1
    # of ``landing_url``. Required for curated bundles where the
    # landing_url is one module in the series and we want the bundle
    # heading to describe the series as a whole.
    title: str | None = None


# Immutable module-level catalog: this is read-only reference data and
# nothing in the script mutates it.
CURATED: tuple[WorkshopCurated, ...] = (
    WorkshopCurated(
        slug="self-service-ai-agents",
        landing_url="https://catalog.workshops.aws/self-service-ai-agents/en-US",
        one_liner=(
            "Build an AI-powered self-service assistant for a fictional "
            "hotel chain using Amazon Connect AI Agents, MCP servers, "
            "and Bedrock AgentCore Gateway. Covers reservation handling, "
            "routine Q&A, and human escalation."
        ),
    ),
    WorkshopCurated(
        slug="amazon-connect-fundamentals",
        landing_url="https://catalog.workshops.aws/amazon-connect-fundamentals/en-US",
        one_liner=(
            "Introductory hands-on workshop covering Connect basics: "
            "queues, routing profiles, security profiles, users, a "
            "simple inbound flow, real-time and historical reporting, "
            "and Contact Lens conversational analytics."
        ),
    ),
    WorkshopCurated(
        slug="amazon-connect-ai-agents",
        landing_url="https://catalog.workshops.aws/amazon-connect-ai-agents/en-US",
        one_liner=(
            "Build action-oriented AI agents with Connect AI Agents + "
            "MCP integration. Covers orchestration agents, tool calling, "
            "1P MCP tools (Cases, Customer Profiles, Tasks), Nova Sonic "
            "generative voice, AgentCore Gateway, guardrails, and "
            "observability."
        ),
    ),
    WorkshopCurated(
        slug="connect-reporting-dashboards",
        landing_url=(
            "https://catalog.us-east-1.prod.workshops.aws/workshops/"
            "b60d8bf5-1afe-460f-ba05-6e7ad35d37f9/en-US"
        ),
        one_liner=(
            "Build real-time and historical metric reports plus custom "
            "dashboards in Amazon Connect."
        ),
    ),
    WorkshopCurated(
        slug="amazon-connect-3p-applications",
        landing_url="https://catalog.workshops.aws/amazon-connect-3p-applications/en-US",
        one_liner=(
            "Build custom third-party apps and services for the Connect "
            "Agent Workspace using the Amazon Connect SDK, and "
            "integrate them into Step-by-step Guides."
        ),
    ),
    WorkshopCurated(
        slug="amazon-connect-outbound-campaigns",
        landing_url="https://catalog.workshops.aws/amazon-connect-outbound-campaigns/en-US",
        one_liner=(
            "End-to-end Outbound Campaigns workshop covering voice, SMS "
            "/ email digital channels, event-based triggers, preview "
            "dialing, customer journeys, segmentation, and agent "
            "dispositions via step-by-step guides."
        ),
    ),
    WorkshopCurated(
        slug="connect-workspaces",
        landing_url=(
            "https://catalog.us-east-1.prod.workshops.aws/workshops/"
            "705f4a6b-6c3f-42ed-bb60-a76e27e78028/en-US"
        ),
        one_liner=(
            "Customise Agent Workspace and Admin Workspace using the "
            "no-code UI builder. Covers Views, Step-by-step Guides, "
            "Data Tables, Theming, persona-based workspaces, and "
            "supervisor business UIs (e.g. emergency closure)."
        ),
    ),
    WorkshopCurated(
        slug="amazon-connect-rules-engine",
        landing_url="https://catalog.workshops.aws/amazon-connect-rules-engine/en-US",
        one_liner=(
            "Use the Connect Rules Engine to automate contact center "
            "actions: real-time metric alerts, conversation analytics "
            "triggers, evaluation form follow-ups, case events, and "
            "schedule adherence notifications."
        ),
    ),
    WorkshopCurated(
        slug="amazon-connect-profiles",
        landing_url="https://catalog.workshops.aws/amazon-connect-profiles/en-US",
        one_liner=(
            "Build a unified customer profile inside Amazon Connect by "
            "ingesting data from external systems (Salesforce, "
            "ServiceNow, Zendesk, Marketo, S3) and surfacing it to "
            "agents. Covers Profile Object Types, personalized routing, "
            "and ML-powered identity resolution to dedupe customer "
            "records."
        ),
    ),
    WorkshopCurated(
        slug="amazon-connect-email",
        landing_url="https://catalog.workshops.aws/amazon-connect-email/en-US",
        one_liner=(
            "Enable the Email channel in Amazon Connect end to end: "
            "addresses, security profiles, routing profiles, send/"
            "receive flows, templates and quick responses, plus "
            "integrations with Customer Profiles and Cases for "
            "agent continuity and case creation from emails."
        ),
    ),
    WorkshopCurated(
        slug="amazon-connect-optimization",
        landing_url="https://catalog.workshops.aws/amazon-connect-optimization/en-US",
        one_liner=(
            "Hands-on with Amazon Connect Forecasting, Capacity "
            "Planning, and Scheduling: predict contact volume, convert "
            "forecasts into staffing needs, build daily shifts, and "
            "monitor schedule adherence."
        ),
    ),
    WorkshopCurated(
        slug="amazon-connect-operational-workshop",
        landing_url="https://catalog.workshops.aws/amazon-connect-operational-workshop/en-US",
        one_liner=(
            "Operate Amazon Connect in production: monitor and "
            "diagnose technical issues across voice, chat, flows, "
            "APIs, and the agent application. Covers the operational "
            "solution architecture, observability tooling, and "
            "hands-on flow / API / agent-app error simulations."
        ),
    ),
    WorkshopCurated(
        slug="agentic-cx-designer",
        landing_url=(
            "https://catalog.us-east-1.prod.workshops.aws/workshops/"
            "dd046ddd-9305-417e-b620-ac4ffc378690/en-US"
        ),
        one_liner=(
            "Nine-part hands-on build of an agentic self-service "
            "experience in the Amazon Connect Customer agentic CX "
            "designer (ACXD). Deploy a backend, expose it to the agent "
            "as tools via Data Requests, shape behaviour with the agent "
            "prompt and escalation, blend the agentic path with a "
            "deterministic entry flow, then instrument it with "
            "Conversation Analytics, ACXD in-canvas analytics, and "
            "analytics tags. Closes with Agentic Voices, Touchpoint "
            "modalities, and Live Sync. Pick one of ten industry "
            "scenarios (insurance, retail banking, healthcare, "
            "airlines, retail, telecom, utilities, automotive, "
            "manufacturing, public sector)."
        ),
    ),
    WorkshopCurated(
        slug="salesforce-contact-center-amazon-connect",
        # Bundle workshop — Module 1 is the canonical entry point
        # (overview / concepts / architecture). The four modules below
        # are linked verbatim instead of being scraped from a single
        # landing page. Each module is itself a Workshop Studio
        # workshop with its own internal lessons; rather than enumerate
        # the lessons we keep the catalog at the module level and
        # carry an ``abstract`` per module so the agent can route to
        # the right module without opening the page.
        landing_url=(
            "https://catalog.us-east-1.prod.workshops.aws/workshops/"
            "f91b5bee-9028-47c0-b1c5-11acfec7c9f3/en-US"
        ),
        title="Salesforce Contact Center with Amazon Connect",
        one_liner=(
            "Four-module bootcamp on Salesforce Contact Center with "
            "Amazon Connect (SCC-AC): generative-AI concepts and "
            "architecture, deploying SCC-AC in the Partner Telephony "
            "model on a Salesforce developer org, generative-AI "
            "self-service inside Salesforce, and generative-AI agent "
            "experience. Each module is a separate Workshop Studio "
            "workshop linked below."
        ),
        module_groups=(
            WorkshopModuleGroup(
                label="Module 1: Generative AI concepts, features, architecture",
                url="https://catalog.us-east-1.prod.workshops.aws/workshops/f91b5bee-9028-47c0-b1c5-11acfec7c9f3/en-US",
                abstract=(
                    "Conceptual primer. Introduces Amazon Connect and "
                    "Salesforce, walks through the integration options "
                    "(Service Cloud Voice with Partner Telephony, "
                    "Service Cloud Voice with Amazon Connect, and the "
                    "CTI Adapter), then zooms in on Salesforce Contact "
                    "Center with Amazon Connect (SCC-AC) — its "
                    "architectural choices, generative-AI overview, "
                    "common contact-center use cases, and the specific "
                    "generative-AI features Connect ships (Q in "
                    "Connect, post-contact summarization, AI Agents, "
                    "Contact Lens, etc.). No deployment yet; this is "
                    "the slide deck before the labs."
                ),
            ),
            WorkshopModuleGroup(
                label="Module 2: Setup (Service Cloud Voice with Partner Telephony from Amazon Connect)",
                url="https://catalog.us-east-1.prod.workshops.aws/workshops/401c630f-2901-4f2d-8468-bd9a9066a78f/en-US",
                abstract=(
                    "Hands-on deployment. End-to-end install of "
                    "SCC-AC on a Salesforce developer org in the "
                    "Partner Telephony model: create the Salesforce "
                    "Contact Center, validate the Service Cloud Voice "
                    "deployment, install and configure the SCC-AC "
                    "managed package, run the guided setup, enable it "
                    "for the Contact Center, and configure Voice, "
                    "Messaging, and Omni-Channel routing. Closes with "
                    "an omni-channel validation and an optional "
                    "Salesforce REST API access lab. After this "
                    "module you have a working SCC-AC environment to "
                    "build Modules 3 and 4 on top of."
                ),
            ),
            WorkshopModuleGroup(
                label="Module 3: Generative AI powered self service",
                url="https://catalog.us-east-1.prod.workshops.aws/workshops/a0299a82-da56-4bd0-b8cb-d7f76dd42d09/en-US",
                abstract=(
                    "Self-service labs. Builds a generative-AI "
                    "self-service experience inside SCC-AC using "
                    "Q in Connect (QiC) on Salesforce knowledge as "
                    "the LLM-grounded knowledge base. Covers the "
                    "self-service architecture and prompt engineering, "
                    "then walks through five labs: (1) wire QiC to "
                    "Salesforce KB, (2) enable QiC inside an Amazon "
                    "Lex bot, (3) build the Connect contact flow that "
                    "calls the QiC-enabled bot, (4) author a Prompt "
                    "for self-service answers, and (5) stand up a "
                    "customer-facing chat website. Ends with a live "
                    "test of the QiC self-service path."
                ),
            ),
            WorkshopModuleGroup(
                label="Module 4: Generative AI powered agent experience",
                url="https://catalog.us-east-1.prod.workshops.aws/workshops/f33ac20c-57f6-45ee-89fc-f80c5522e2bf/en-US",
                abstract=(
                    "Agent-assist labs. Layers Connect's generative-"
                    "AI agent-experience features on top of the "
                    "SCC-AC environment from Module 2: post-contact "
                    "summarization (auto-fill the Salesforce wrap-up "
                    "screen), Amazon Connect AI Agents for live "
                    "in-call assistance, and Contact Lens performance "
                    "evaluations to grade interactions and surface "
                    "coaching cues. Each feature is enabled, "
                    "configured in SCC-AC, and exercised on a sample "
                    "contact so the agent sees the gen-AI output "
                    "inside the Salesforce omni-channel widget."
                ),
            ),
        ),
    ),
)


# ----- runtime data shape -------------------------------------------------


@dataclass
class WorkshopRendered:
    curated: WorkshopCurated
    title: str
    modules: list[tuple[str, str]]  # (label, url)


# ----- playwright extraction ----------------------------------------------


def _ensure_playwright() -> Any:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed. It ships as a core dependency; "
            "sync it and install the Chromium browser:\n"
            "    uv sync\n"
            "    uv run python -m playwright install chromium"
        ) from exc
    return sync_playwright


def _normalize_url(url: str) -> str:
    """Strip query strings and fragments for stable comparison."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _is_module_link(href: str, landing_url: str) -> bool:
    """Module links live under the same workshop path as the landing page.

    Only returns True for *top-level* modules, i.e. links exactly one
    path segment deeper than the landing page. This keeps the steering
    file readable — every workshop has dozens or hundreds of nested
    task pages we don't want to enumerate.

    Skip the landing page itself, the Workshop Studio root, the AWS
    Builder Center catalog link, and any external docs links.
    """
    if not href:
        return False
    href_norm = _normalize_url(href)
    landing_norm = _normalize_url(landing_url)
    if href_norm == landing_norm:
        return False
    landing_prefix = landing_norm.rstrip("/") + "/"
    if not href_norm.startswith(landing_prefix):
        return False
    # require exactly one extra path segment beyond the landing path
    suffix = href_norm[len(landing_prefix):].strip("/")
    if not suffix:
        return False
    return "/" not in suffix


# Module labels we treat as boilerplate and drop from the rendered
# catalog. Workshops universally end with cleanup / summary / next-steps
# pages that don't carry learning content; they add noise to the steering
# file. Match is case-insensitive substring against the rendered label,
# stripped of leading numbering ("11. Cleaning Up" → "Cleaning Up").
_BOILERPLATE_LABEL_KEYWORDS = (
    "clean up",
    "cleanup",
    "cleaning up",
    "summary",
    "next steps",
    "next-steps",
    "conclusion",
    "wrap up",
    "wrap-up",
)


def _strip_label_numbering(label: str) -> str:
    """``"11. Cleaning Up"`` → ``"Cleaning Up"``; ``"5-cleanup"`` → ``"cleanup"``."""
    s = label.strip()
    # Drop a leading "<digits>." or "<digits>-" or "<digits> " prefix.
    i = 0
    while i < len(s) and s[i].isdigit():
        i += 1
    if i and i < len(s) and s[i] in ".-) ":
        s = s[i + 1 :].lstrip()
    return s


def _is_boilerplate_module(label: str) -> bool:
    """Return True for cleanup / summary / next-steps style labels."""
    stripped = _strip_label_numbering(label).lower()
    return any(kw in stripped for kw in _BOILERPLATE_LABEL_KEYWORDS)


def _dedupe(modules: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Preserve order, drop URL duplicates (favoring the first label)."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for label, href in modules:
        href_norm = _normalize_url(href)
        if href_norm in seen:
            continue
        seen.add(href_norm)
        out.append((label, href_norm))
    return out


def fetch_workshop(
    sync_playwright: Any,
    page: Any,
    curated: WorkshopCurated,
) -> WorkshopRendered:
    """Render the workshop landing page and extract title + modules.

    Strategy:
    1. Wait for ``<h1>`` to appear (Workshop Studio always renders one).
    2. Walk every ``<a>`` on the page and keep those whose href lives
       under the workshop's landing path. This catches both the
       sidebar and the bottom "Additional Links" block, and works for
       both the public ``catalog.workshops.aws`` host and the
       ``catalog.us-east-1.prod.workshops.aws`` regional host.

    For curated bundles (``curated.modules`` set), skip the network
    round-trip entirely and emit the curated label/url pairs as-is.
    """
    if curated.module_groups is not None:
        title = curated.title or curated.slug.replace("-", " ").title()
        print(
            f"  curated bundle (with abstracts) {curated.slug!r} "
            f"({len(curated.module_groups)} modules, no network)",
            file=sys.stderr,
        )
        return WorkshopRendered(curated=curated, title=title, modules=[])

    if curated.modules is not None:
        title = curated.title or curated.slug.replace("-", " ").title()
        print(
            f"  curated bundle {curated.slug!r} "
            f"({len(curated.modules)} modules, no network)",
            file=sys.stderr,
        )
        return WorkshopRendered(curated=curated, title=title, modules=list(curated.modules))

    print(f"  fetching {curated.landing_url}", file=sys.stderr)
    page.goto(curated.landing_url, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
    # Workshop Studio is a React SPA — wait for the H1 to actually
    # carry text. ``wait_until='networkidle'`` is usually enough but
    # some pages keep an open analytics socket; loop a few times.
    for _ in range(20):
        try:
            txt = (page.locator("h1").first.inner_text(timeout=1_000) or "").strip()
        except Exception:
            txt = ""
        if txt:
            break
        page.wait_for_timeout(250)

    title = (page.locator("h1").first.inner_text(timeout=5_000) or "").strip()

    modules: list[tuple[str, str]] = []
    # Anchors can detach mid-iteration as the SPA re-renders, and
    # ``inner_text`` times out on hidden ones. Both are expected; count
    # them so a page that yields no modules is diagnosable instead of
    # silently empty.
    unreadable = 0
    last_anchor_error: Exception | None = None
    for anchor in page.locator("a[href]").all():
        try:
            href = anchor.get_attribute("href") or ""
            label = (anchor.inner_text(timeout=1_000) or "").strip()
        except Exception as exc:  # noqa: BLE001 — playwright raises many types
            unreadable += 1
            last_anchor_error = exc
            continue
        if not label:
            continue
        # workshop links may be relative to the page root; resolve them
        if href.startswith("/"):
            parsed = urlparse(curated.landing_url)
            href = f"{parsed.scheme}://{parsed.netloc}{href}"
        if _is_module_link(href, curated.landing_url):
            if _is_boilerplate_module(label):
                continue
            modules.append((label, href))

    modules = _dedupe(modules)
    if unreadable:
        print(
            f"    skipped {unreadable} unreadable anchor(s) "
            f"(last: {last_anchor_error})",
            file=sys.stderr,
        )
    print(f"    {title!r} → {len(modules)} module link(s)", file=sys.stderr)
    return WorkshopRendered(curated=curated, title=title, modules=modules)


def fetch_all(curated: Sequence[WorkshopCurated]) -> list[WorkshopRendered]:
    sync_playwright = _ensure_playwright()
    out: list[WorkshopRendered] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 1600})
        page = context.new_page()
        try:
            for entry in curated:
                try:
                    out.append(fetch_workshop(sync_playwright, page, entry))
                except Exception as exc:
                    print(
                        f"  ! failed to render {entry.landing_url}: {exc}",
                        file=sys.stderr,
                    )
                    # write a stub so the file still mentions the workshop
                    out.append(
                        WorkshopRendered(
                            curated=entry,
                            title=entry.slug.replace("-", " ").title(),
                            modules=[],
                        )
                    )
        finally:
            browser.close()
    return out


# ----- markdown rendering -------------------------------------------------


HEADER = """\
# Amazon Connect workshops & how-to catalog

Quick lookup table for AWS-published Amazon Connect workshops on
``catalog.workshops.aws``. Each entry has a one-liner describing the
scope and a deep-linked module list so you can jump straight to the
right step without re-crawling the catalog.

**Activation:** opt-in. Reference from chat with `#aws-workshops` when
you need to point the user at an end-to-end tutorial, scaffold a
proof-of-concept, or copy a configuration pattern that is documented
as a workshop step.

**Freshness rule (for the agent):** before relying on this catalog,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 30 days, run
``uv run python .kiro/scripts/refresh_aws_workshops.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.
The refresh script renders each landing page with Playwright (same
machinery the View component refresher uses) because these pages are
JavaScript-rendered and a plain HTTP fetch returns an empty shell.

**How to use this catalog:**
- Pick the workshop whose summary matches the user's intent.
- Use the module list to jump straight to the relevant step instead of
  the landing page.
- For multi-module bootcamps (e.g. Salesforce Contact Center with
  Amazon Connect), each module has its own one-paragraph abstract so
  you can route to the right module without opening the page.
- For module-level detail (commands, screenshots, JSON snippets), open
  the module URL in `web_fetch` with ``mode="rendered"``. Plain
  ``mode="full"`` returns an empty page on these catalogs.

"""


def render_workshop(item: WorkshopRendered) -> str:
    c = item.curated
    lines: list[str] = []
    lines.append("---")
    lines.append("")
    lines.append(f"## {item.title}")
    lines.append("")
    lines.append(f"- **URL:** {c.landing_url}")
    lines.append(f"- **One-liner:** {c.one_liner}")
    if c.module_groups:
        lines.append("- **Modules:**")
        for group in c.module_groups:
            lines.append(f"  - **[{group.label}]({group.url})**")
            lines.append(f"    {group.abstract}")
    elif item.modules:
        lines.append("- **Modules:**")
        for label, href in item.modules:
            lines.append(f"  - [{label}]({href})")
    else:
        lines.append("- **Modules:** _(refresh failed — see script logs)_")
    lines.append("")
    return "\n".join(lines)


def content_hash(body: str) -> str:
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def render_document(items: list[WorkshopRendered]) -> str:
    body_parts = [HEADER]
    for item in items:
        body_parts.append(render_workshop(item))
    body = "\n".join(body_parts).rstrip() + "\n"

    # For curated bundles list every module URL so the front matter
    # surfaces all source pages, not just the canonical landing URL.
    source_url_lines: list[str] = []
    for item in items:
        if item.curated.module_groups is not None:
            for group in item.curated.module_groups:
                source_url_lines.append(f"  - {group.url}")
        elif item.curated.modules is not None:
            for _label, href in item.curated.modules:
                source_url_lines.append(f"  - {href}")
        else:
            source_url_lines.append(f"  - {item.curated.landing_url}")
    source_urls = "\n".join(source_url_lines)

    frontmatter = (
        "---\n"
        "inclusion: manual\n"
        f"last_refreshed: {date.today().isoformat()}\n"
        f"workshop_count: {len(items)}\n"
        "source_urls:\n"
        f"{source_urls}\n"
        f"content_checksum: {content_hash(body)}\n"
        "---\n\n"
    )
    return frontmatter + body


# ----- CLI ----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rendered document to stdout without writing.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"Output path (default: {OUTPUT_PATH.relative_to(REPO_ROOT)}).",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help=(
            "Refresh only the named workshop (slug match). When set, "
            "merges the freshly-fetched workshop into the existing "
            "steering file's other entries instead of overwriting "
            "everything. Pass without value to list slugs."
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available workshop slugs and exit.",
    )
    args = parser.parse_args(argv)

    if args.list:
        for entry in CURATED:
            print(f"{entry.slug}\t{entry.landing_url}")
        return 0

    if args.only:
        targets = [c for c in CURATED if c.slug == args.only]
        if not targets:
            available = ", ".join(c.slug for c in CURATED)
            print(
                f"unknown workshop slug {args.only!r}. choose one of: {available}",
                file=sys.stderr,
            )
            return 2
        items = fetch_all(targets)
        # The --only flow only refreshes the requested workshop's
        # module list; we still render the full document using the
        # other workshops' previously-curated copy and previously-
        # rendered modules. Since module lists for the other entries
        # would otherwise be empty, fall back to rendering them with
        # only their curated copy (no module list) — operators using
        # --only should run a full refresh afterward to repopulate.
        existing_slugs = {c.slug for c in targets}
        rest = [
            WorkshopRendered(
                curated=c,
                title=c.slug.replace("-", " ").title(),
                modules=[],
            )
            for c in CURATED
            if c.slug not in existing_slugs
        ]
        # Keep CURATED order
        ordered: list[WorkshopRendered] = []
        for c in CURATED:
            match = next(
                (i for i in items + rest if i.curated.slug == c.slug),
                None,
            )
            if match is not None:
                ordered.append(match)
        items = ordered
        print(
            "  note: --only refreshed module list for "
            f"{args.only}; rerun without --only to refresh others.",
            file=sys.stderr,
        )
    else:
        items = fetch_all(CURATED)

    document = render_document(items)

    if args.dry_run:
        sys.stdout.write(document)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding="utf-8")
    print(f"wrote {args.output} ({len(items)} workshops)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
