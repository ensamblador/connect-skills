"""Refresh ``.kiro/steering/connect-views.md`` from the View Dictionary.

Two-source script:

1. **Storybook component catalog** (cloudfront) — pulls the public
   Amazon Connect View Dictionary Storybook bundle, parses each story
   module to extract (hierarchy, name, description, story id), and
   writes the four catalog tables (AWS-managed Views, Customer-managed
   Views, UI Components, FormView Components).

2. **Admin guide pages** (``docs.aws.amazon.com/connect``) — fetches the
   ``.md`` source for each curated topic page, extracts its top-level
   title and lead paragraph, and renders the three-subsection
   ``Admin guide pages`` group (Setup & permissions, Authoring,
   Integration patterns).

Sources:
    - https://d3irlmavjxd3d8.cloudfront.net/  (View Dictionary, JS-rendered)
    - https://docs.aws.amazon.com/connect/    (admin guide, plain markdown)

Why parse the JS bundle for the Storybook side? The site is a
client-rendered Storybook; there is no ``stories.json`` index served.
The bundle ships every story module side-by-side, each carrying its
title (``constant.U.<HIERARCHY> + "/<Name>"``), its component-level
description (``description:{component:"…"}``) and its default-story
slug (recoverable from inline ``href:"/?path=/docs/..."`` links).

Why simple HTTP for admin-guide pages? AWS publishes a ``.md`` source
alongside every ``.html`` page (swap the extension), so for pages
under ``docs.aws.amazon.com/connect/`` we don't need a browser — a
plain ``GET`` plus the lightweight markdown parsers in
``connect_knowledge.page_doc`` is enough.

Optional enrichment: when ``--with-props`` is passed, each component's
required props are captured by rendering its Storybook docs page with
Playwright and reading the ``ArgsTable``. This adds a ``Required props``
column to every catalog table, at the cost of one Chromium launch and
roughly one second per component (~40 components → ~45 seconds total).
The enrichment is off by default so a structural refresh stays fast.

Run:
    uv run python .kiro/scripts/refresh_connect_views.py            # write (no props)
    uv run python .kiro/scripts/refresh_connect_views.py --dry-run  # preview
    uv run python .kiro/scripts/refresh_connect_views.py --with-props
        # enrich every row with required props (needs the Chromium binary:
        #   uv run python -m playwright install chromium)
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests

# Shared HTTP fetcher with 404 self-healing via the connect-knowledge
# docs search. Used for the AWS-docs admin-guide pages; the local
# fetch() below stays for the Storybook bundle (CloudFront returns the
# wrong charset, so we need custom decoding).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _doc_fetcher import fetch_with_fallback  # noqa: E402

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 30

VIEW_DICT_ROOT = "https://d3irlmavjxd3d8.cloudfront.net"
INDEX_URL = f"{VIEW_DICT_ROOT}/iframe.html"
ADMINGUIDE_ROOT = "https://docs.aws.amazon.com/connect/latest/adminguide"

# This script lives at ``.kiro/scripts/`` — two levels under the
# repo root (scripts → .kiro → repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / ".kiro" / "steering" / "connect-views.md"

# Hierarchy constants from the bundle's ``src/common/constant.ts``:
#   AWS_MANAGED_VIEWS = "AWS-managed Views"
#   UI_COMP           = "UI Component"
#   FORM              = "FormView Component"
#   CUSTOMER_MANAGED_VIEWS = "Customer-managed Views"
HIERARCHY = {
    "AWS_MANAGED_VIEWS": "AWS-managed Views",
    "UI_COMP": "UI Component",
    "FORM": "FormView Component",
    "CUSTOMER_MANAGED_VIEWS": "Customer-managed Views",
}

# Section order and headings used in the output document.
SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("AWS-managed Views", "AWS-managed Views",
     "Pre-built end-to-end view templates fully managed by Amazon Connect. "
     "Use these as a `Show view` block target when you want a ready-made screen "
     "instead of composing one from UI components. _Common Configuration_ is a "
     "reference page describing fields shared by every AWS-managed template."),
    ("Customer-managed Views", "Customer-managed Views",
     "Custom view resources that you author and version yourself with the Connect "
     "view APIs. Useful when AWS-managed templates do not fit and you need full "
     "control over the JSON template."),
    ("UI Component", "UI Components",
     "Connect-managed UI elements that you compose inside a customer-managed view "
     "template's `Body` field. Default styles match the Connect look and feel; most "
     "props can be overridden when the view is configured in a flow. _UI Components_ "
     "is the umbrella reference page covering shared structure and props."),
    ("FormView Component", "FormView Components",
     "Subset of UI components that are valid inside a `Form` UI component. They "
     "render input fields whose values are submitted via the `SubmitButton` and "
     "surfaced on the `Show view` block's branches."),
)


# ----- fetch & module slicing ---------------------------------------------


def fetch(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    # CloudFront returns ``Content-Type: text/javascript`` (no charset) for the
    # bundle, which makes ``requests`` fall back to ISO-8859-1. The bytes are
    # actually UTF-8 — force the right codec so smart quotes survive.
    return r.content.decode("utf-8")


def discover_main_bundle_url(iframe_html: str) -> str:
    """Find the ``main.<hash>.iframe.bundle.js`` URL referenced by the iframe shell.

    Webpack also emits a ``runtime~main.<hash>.iframe.bundle.js`` shim,
    which contains the same ``main.<hash>`` token as a substring. We
    require the match to be preceded by a non-``~`` character (or
    start-of-string) so the runtime shim doesn't shadow the real
    bundle.
    """
    pattern = re.compile(r"(?:^|[^~])(main\.[0-9a-f]+\.iframe\.bundle\.js)")
    for m in pattern.finditer(iframe_html):
        return f"{VIEW_DICT_ROOT}/{m.group(1)}"
    raise RuntimeError("could not locate main iframe bundle in iframe.html")


# ----- per-module extraction ----------------------------------------------


@dataclass
class Entry:
    hierarchy: str  # human-readable, e.g. "UI Component"
    name: str       # component name as shown in the sidebar, e.g. "Button"
    description: str | None
    story_slug: str  # full story slug, e.g. "ui-component-button--default-case"
    source_path: str  # original ``components/...`` path, for debugging
    required_props: list[str] | None = None  # populated when --with-props is set


# Webpack module map keys for story modules under src/stories/...
MODULE_KEY_RE = re.compile(r'"\./src/stories/([^"]+\.(?:stories(?:\.tsx)?|stories\.mdx))":')

# constant.U.<HIERARCHY_KEY> + "/<Name>" — robust to the minified import alias
TITLE_CONST_RE = re.compile(r'\.U\.([A-Z_]+)\s*\+\s*"/([^"]+)"')

# Some modules use a dynamic title: ``constant.U.UI_COMP + "/" + componentName``
# where componentName is a local var assigned literally further down.
TITLE_DYNAMIC_RE = re.compile(r'\.U\.([A-Z_]+)\s*\+\s*"/"\s*\+\s*componentName')
COMPONENT_NAME_RE = re.compile(r'componentName\s*[:=]\s*"([^"]+)"')

# Plain literal title:"..." (used by overview.stories.mdx)
LITERAL_TITLE_RE = re.compile(r'title:\s*"([^"]+)"')

# description:{component:"<...escaped...>"}
DESC_RE = re.compile(r'description:\{component:"((?:[^"\\]|\\.)*?)"\}', re.DOTALL)

# Inline href links — used to recover the default story suffix per slug
HREF_RE = re.compile(r'href:"/\?path=/(?:docs|story)/([a-z0-9-]+)--([a-z0-9-]+)"')

# Storybook 6 ID slugifier: lowercase, runs of non-alnum collapse to "-".
def storybook_slug(title: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")


def slice_modules(bundle: str) -> list[tuple[str, str]]:
    """Return ``(source_path, body_until_next_module)`` for each story module."""
    matches = list(MODULE_KEY_RE.finditer(bundle))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(bundle)
        out.append((m.group(1), bundle[start:end]))
    return out


def infer_title_from_path(source_path: str) -> tuple[str, str] | None:
    """Fallback for modules where the constant alias defeats the title regex.

    Path shapes:
        components/ui_components/<Comp>/<Comp>.stories.tsx
        components/form/<Comp>/<Comp>.stories.tsx
        components/view_components/<comp>/<comp>.stories.tsx
        customer-managed-views/overview.stories.mdx
    """
    parts = source_path.split("/")
    if len(parts) < 2:
        return None
    if parts[0] == "components":
        section = parts[1]
        # use the directory name as the canonical component name (preserves casing)
        comp = parts[2] if len(parts) > 2 else None
        if not comp:
            return None
        if section == "ui_components":
            return ("UI_COMP", comp)
        if section == "form":
            return ("FORM", comp)
        if section == "view_components":
            return ("AWS_MANAGED_VIEWS", comp.capitalize())
    return None


def extract_default_suffixes(bundle: str) -> tuple[dict[str, str], dict[str, str]]:
    """Map ``base-slug`` → first ``suffix`` we see linked anywhere in the bundle.

    Also returns a per-hierarchy-prefix fallback (``ui-component`` →
    ``with-all``) so components that are not cross-linked from any other
    page still get a sensible suffix.

    The View Dictionary cross-links each component's default story (e.g.
    ``ui-component-button--default-case``). One suffix per slug holds in
    practice; we collapse to first-seen.
    """
    per_slug: dict[str, str] = {}
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for m in HREF_RE.finditer(bundle):
        base, suffix = m.group(1), m.group(2)
        per_slug.setdefault(base, suffix)
        # bucket by leading prefix (e.g. ``ui-component``, ``aws-managed-views``)
        for prefix in ("aws-managed-views", "customer-managed-views",
                       "formview-component", "ui-component"):
            if base.startswith(f"{prefix}-"):
                counts[prefix][suffix] += 1
                break
    per_prefix = {
        prefix: max(suffixes.items(), key=lambda kv: kv[1])[0]
        for prefix, suffixes in counts.items()
    }
    return per_slug, per_prefix


def parse_entries(bundle: str) -> list[Entry]:
    suffix_by_slug, suffix_by_prefix = extract_default_suffixes(bundle)
    entries: list[Entry] = []
    seen: set[tuple[str, str]] = set()  # dedupe on (hierarchy_key, name)

    for source_path, body in slice_modules(bundle):
        # Title via constant ref, then via dynamic+componentName, then via path
        # inference, then via literal "Hierarchy/Name" string.
        title_m = TITLE_CONST_RE.search(body)
        if title_m:
            hierarchy_key = title_m.group(1)
            name = title_m.group(2)
        else:
            dyn = TITLE_DYNAMIC_RE.search(body)
            cname = COMPONENT_NAME_RE.search(body)
            if dyn and cname:
                hierarchy_key = dyn.group(1)
                name = cname.group(1)
            else:
                inferred = infer_title_from_path(source_path)
                if inferred:
                    hierarchy_key, name = inferred
                else:
                    lit = LITERAL_TITLE_RE.search(body)
                    if not lit or "/" not in lit.group(1):
                        # e.g. overview.stories.mdx — no component to catalog
                        continue
                    left, _, right = lit.group(1).partition("/")
                    # reverse-lookup the hierarchy by display name
                    hierarchy_key = next(
                        (k for k, v in HIERARCHY.items() if v == left), None
                    )
                    name = right
                    if not hierarchy_key:
                        continue

        if hierarchy_key not in HIERARCHY:
            continue

        if (hierarchy_key, name) in seen:
            continue
        seen.add((hierarchy_key, name))

        desc_m = DESC_RE.search(body)
        description = desc_m.group(1) if desc_m else None
        if description:
            description = description.replace("\\n", " ").replace("\n", " ").strip()
            # strip embedded markdown links like [foo](https://…) → foo
            description = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", description)
            # collapse whitespace
            description = re.sub(r"\s+", " ", description)

        title_for_slug = f"{HIERARCHY[hierarchy_key]}/{name}"
        base_slug = storybook_slug(title_for_slug)
        suffix = suffix_by_slug.get(base_slug)
        if suffix is None:
            # Fall back to the most common suffix in this hierarchy prefix.
            for prefix, default in suffix_by_prefix.items():
                if base_slug.startswith(f"{prefix}-"):
                    suffix = default
                    break
        story_slug = f"{base_slug}--{suffix or 'page'}"

        entries.append(
            Entry(
                hierarchy=HIERARCHY[hierarchy_key],
                name=name,
                description=description,
                story_slug=story_slug,
                source_path=source_path,
            )
        )

    return entries


# ----- rendering -----------------------------------------------------------


def story_url(slug: str) -> str:
    # ``docs/`` deep-links to the rendered MDX docs page (props table + examples).
    return f"{VIEW_DICT_ROOT}/?path=/docs/{slug}"


def render_section(heading: str, blurb: str, entries: list[Entry], *, with_props: bool) -> str:
    if not entries:
        return f"## {heading}\n\n{blurb}\n\n_(no entries found in upstream bundle)_\n"
    if with_props:
        lines = [
            f"## {heading}",
            "",
            blurb,
            "",
            "| Component | Required props | Description |",
            "| --- | --- | --- |",
        ]
        for e in sorted(entries, key=lambda x: x.name.casefold()):
            link = f"[{e.name}]({story_url(e.story_slug)})"
            desc = (e.description or "_(no description in source)_").strip().replace("|", r"\|")
            if e.required_props is None:
                required = "_(not captured)_"
            elif not e.required_props:
                required = "_(none)_"
            else:
                required = ", ".join(f"`{p}`" for p in e.required_props)
            lines.append(f"| {link} | {required} | {desc} |")
        return "\n".join(lines) + "\n"

    lines = [f"## {heading}", "", blurb, "", "| Component | Description |", "| --- | --- |"]
    for e in sorted(entries, key=lambda x: x.name.casefold()):
        link = f"[{e.name}]({story_url(e.story_slug)})"
        desc = (e.description or "_(no description in source)_").strip()
        # Escape any literal pipes that would break the markdown table.
        desc = desc.replace("|", r"\|")
        lines.append(f"| {link} | {desc} |")
    return "\n".join(lines) + "\n"


def content_hash(body: str) -> str:
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


FRONTMATTER_TEMPLATE = """\
---
inclusion: manual
last_refreshed: {today}
entry_count: {entry_count}
source_urls:
{source_url_lines}
content_checksum: {checksum}
---
"""


BODY_HEADER = """\
# Connect view dictionary catalog

Quick lookup table for every component, view template, and view-related
docs page in the public Amazon Connect View Dictionary, plus a curated
index of admin-guide topic pages that explain how Views and step-by-step
guides hang together at the flow / permissions / runtime layer. Both
sections are generated by
``uv run python .kiro/scripts/refresh_connect_views.py`` from two upstream
sources:

- the View Dictionary Storybook bundle (CloudFront, JS-rendered) — for
  the four component catalog tables.
- the Amazon Connect admin guide (``docs.aws.amazon.com/connect``,
  served as ``.md`` alongside ``.html``) — for the **Admin guide
  pages** group below.

**Activation:** this file is opt-in. Reference it from chat with
`#connect-views` when you're authoring a customer-managed view template,
picking a UI component for a `Show view` block, or wiring a form into
a flow.

**Freshness rule (for the agent):** before relying on this catalog,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 7 days, run
``uv run python .kiro/scripts/refresh_connect_views.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.
A regenerated file with no diff is fine — `last_refreshed` is the only
thing that needs updating, and the script handles that automatically.

For depth on any entry (full props table with descriptions, defaults,
examples, schema), call the `get_view_component_doc` MCP tool with the
component's story slug — it's the bit after `?path=/docs/` in the
component link, e.g. `ui-component-datepicker--with-all`. The tool
drives a headless Chromium against the View Dictionary Storybook and
returns structured props.

For depth on any **Admin guide** row, swap the link's `.html` for `.md`
(or open the rendered page) — the admin guide is plain markdown so a
direct fetch is enough; no browser needed.

For the higher-level view APIs (`CreateView`, `UpdateView`, …) see the
[Amazon Connect View resource APIs](https://docs.aws.amazon.com/connect/latest/APIReference/views-api.html).

"""


def build_document(
    entries_by_section: dict[str, list[Entry]],
    *,
    with_props: bool,
    admin_guide_entries: list[AdminGuideEntry],
) -> str:
    body_parts = [BODY_HEADER]
    for hierarchy_label, heading, blurb in SECTIONS:
        body_parts.append(
            render_section(
                heading,
                blurb,
                entries_by_section.get(hierarchy_label, []),
                with_props=with_props,
            )
        )
        body_parts.append("")

    admin_section = render_admin_guide_section(admin_guide_entries)
    if admin_section:
        body_parts.append(admin_section)
        body_parts.append("")

    body = "\n".join(body_parts).rstrip() + "\n"
    total = sum(len(v) for v in entries_by_section.values()) + len(admin_guide_entries)
    source_urls = [f"{VIEW_DICT_ROOT}/?path=/docs/overview--page"]
    if admin_guide_entries:
        source_urls.append(f"{ADMINGUIDE_ROOT}/step-by-step-guided-experiences.html")
    source_url_lines = "\n".join(f"  - {u}" for u in source_urls)
    frontmatter = FRONTMATTER_TEMPLATE.format(
        today=date.today().isoformat(),
        entry_count=total,
        source_url_lines=source_url_lines,
        checksum=content_hash(body),
    )
    return frontmatter + "\n" + body


# ----- admin-guide source catalog ----------------------------------------

# Curated index of admin-guide pages worth surfacing alongside the
# Storybook component catalog. Each row is ``(slug, bucket, title,
# editorial_blurb)``:
#
# - ``slug``: the page's URL stem under
#   ``https://docs.aws.amazon.com/connect/latest/adminguide/`` (no
#   extension). Swap ``.html`` ↔ ``.md`` to flip surface vs source.
# - ``bucket``: which subsection the row lands in.
# - ``title``: human-friendly title for the link text. ``None`` falls
#   back to the page's parsed top heading.
# - ``editorial_blurb``: hand-written one-liner used as the description.
#   ``None`` falls back to the page's parsed lead paragraph (truncated
#   to one sentence). The blurb is always preferred when present
#   because the lead paragraph is often too long or too generic to
#   serve as a tight catalog row.

ADMIN_GUIDE_BUCKETS: tuple[tuple[str, str], ...] = (
    ("setup", "Setup & permissions"),
    ("authoring", "Authoring views & guides"),
    ("integration", "Integration patterns & use cases"),
)

ADMIN_GUIDE_SOURCES: tuple[tuple[str, str, str | None, str | None], ...] = (
    # Setup & permissions
    (
        "step-by-step-guided-experiences", "setup", "Step-by-step guides — overview",
        "Umbrella page: build screen pops and multi-page agent guides by combining a flow, "
        "the Show view block, and one or more Views. Covers the runtime model where the "
        "guide runs as its own background chat contact, and complex JSON pass-through "
        "between the workspace and flows.",
    ),
    (
        "enable-guided-experiences-sg", "setup", "Enable step-by-step guides",
        "Permissions checklist: grant `Channels and flows - Views` plus `Flows - Edit, Create` "
        "to authors, `Agent Applications - Custom views` to agents, and bump the "
        "concurrent-active-chats service quota since each running guide spawns a chat contact.",
    ),
    (
        "enable-smart-default-guides-acw", "setup", "Smart default ACW guide",
        "New instances ship with a default after-contact-work guide; for older instances, "
        "import the provided flow JSON, point its Show view block at the AWS-managed "
        "`after contact work` view, and wire it in via a `Set event flow` block.",
    ),
    (
        "customize-theme-agent-workspace", "setup", "Customize the agent workspace theme",
        "Branding the agent workspace shell (logo, fonts, colors, light/dark mode) is a "
        "workspace-level theme — separate from view-level styling. Pair with persona-based "
        "workspaces to apply per-role.",
    ),

    # Authoring views & guides
    (
        "view-resources-sg", "authoring", "Views — UI templates overview",
        "What a View resource is: a template + input schema + actions, used by the Show view "
        "block. Recommends the **Set JSON** option in the block for the cleanest data mapping, "
        "and notes that every flow namespace (including `$.External`) is reachable from the view.",
    ),
    (
        "view-resources-managed-view", "authoring", "AWS-managed views",
        "Per-template configuration reference for the Detail, Form, List, Cards, and "
        "Confirmation managed views: required vs optional sections, supported components "
        "(AttributeBar, Sections), and what each renders.",
    ),
    (
        "view-resources-custom-view", "authoring", "Customer-managed views",
        "API-driven authoring: example `aws connect create-view` call, the `Template` + "
        "`Actions` `view-content.json` shape, CloudFormation/CloudTrail/tagging support, "
        "and a worked Body example with Container + Card + Button.",
    ),
    (
        "user-interface-component-library-sg", "authoring", "UI component library",
        "How the UI builder's Library tab maps to the Storybook component reference. Calls "
        "out Containers as the layout primitive and Form as the special container that "
        "submits captured fields back to the flow.",
    ),
    (
        "no-code-ui-builder-customize-panel", "authoring",
        "Customize panel — layout, colors, dynamic data",
        "The right-hand Customize panel toggles between global view settings (12-column "
        "flexbox, primary/secondary/neutral colors, alignment) and per-component settings.",
    ),
    (
        "no-code-ui-builder-properties-dynamic-fields", "authoring", "Dynamic fields",
        "Click the lightning-bolt icon on any property to bind it to runtime data passed in "
        "via Show view. The most common targets are `Value` on display components and "
        "`DefaultValue` on form inputs. Sample Data appears once a field is dynamic.",
    ),
    (
        "ui-conditions-on-views", "authoring", "Conditional UI",
        "Set Visibility, DefaultValue, Required, Disable, or Options on one component based "
        "on the value of another component in the same view. Authored from the **UI "
        "conditions** tab in the Customize panel.",
    ),
    (
        "customize-views-jsx-sg", "authoring", "HTML and JSX in Show view",
        "Pass HTML or JSX template strings into the Show view block (via **Set JSON**) to "
        "render rich content inside a managed view's `Sections.TemplateString` — useful for "
        "ordered lists, embedded markup, or inline scripts.",
    ),
    (
        "no-code-ui-builder-setting-actions-in-flows", "authoring", "Branch on view actions",
        "Each button's `Action` value becomes a branch on the Show view block in the flow. "
        "Define one Action per button and the flow gains one labelled exit per button.",
    ),

    # Integration patterns & use cases
    (
        "how-to-invoke-a-flow-sg", "integration", "Invoke a guide at the start of a contact",
        "Use a `Set event flow` block with the `DefaultFlowForAgentUI` event hook to "
        "dynamically pick which guide flow runs when the contact is offered — branch on "
        "IVR digits, queue, or attributes with `Check attribute` first.",
    ),
    (
        "display-contact-attributes-sg", "integration", "Display contact attributes (screen pop)",
        "Canonical screen-pop pattern: a Detail managed view with `Sections` + an optional "
        "`AttributeBar`, populated from contact attributes through Show view's Set JSON.",
    ),
    (
        "disposition-codes-sg", "integration", "Disposition codes (ACW form)",
        "End-of-contact wrap-up: a flow with one Show view (Form view) plus one "
        "`Set contact attributes` block, surfaced by setting the `DisconnectFlowForAgentUI` "
        "attribute before the contact ends. Optional Lambda block forwards the response to a CRM.",
    ),
    (
        "step-by-step-guides-pii-redaction", "integration", "PII redaction in guides",
        "Anything captured in a guide lands in the contact record transcript by default. "
        "Drop in a `Set recording and analytics behavior` block and enable Contact Lens "
        "redaction to keep PII out.",
    ),
    (
        "integrate-views-with-connect-resources", "integration",
        "Integrate views with Connect resources",
        "View-level **Tools** poll a Connect resource (e.g. a Flow module) on a refresh "
        "interval. Reference outputs in component props with "
        "`$.#[IntegrationName].[ReferenceObject]`. Best with one tab open per agent — "
        "multi-tab amplifies polling.",
    ),
    (
        "no-code-ui-builder-app-integration", "integration",
        "App integration (third-party screen pop)",
        "Three options for embedding third-party apps: the `Application` component "
        "(in-Guide), the App Launch component (separate workspace tab with auto-open), or "
        "a `Link` component with auto-open. App name must match the AWS Management Console "
        "registration exactly.",
    ),
    (
        "step-by-step-guides-chat", "integration", "Step-by-step guides in chat",
        "Reuse an agent guide as a customer self-service experience: the same Show view "
        "block runs in the chat flow and renders inside a hosted Amazon Connect chat widget "
        "before transferring to an agent.",
    ),
    (
        "use-views-to-create-persona-based-workspace-pages", "integration",
        "Persona-based workspace pages",
        "Use Views as single-step pages inside a persona-based Workspace (not a guide). "
        "Compatible components include Alert, Carousel, Containers, and Data Table. Input "
        "data flows in through the page configuration wizard.",
    ),
    (
        "use-guides-in-manager-workspace", "integration", "Guides in manager workspaces",
        "Embed a guide inside a static workspace view via the `Connect Application` "
        "component (set Application Namespace = Guide, ContactFlowId = the guide flow). "
        "Begin/Restart controls launch the background chat contact. Cannot be nested in "
        "another guide-driven view.",
    ),
)


@dataclass
class AdminGuideEntry:
    slug: str
    bucket: str
    title: str
    description: str
    url: str  # always the .html surface for human readers


def _admin_guide_url(slug: str, *, ext: str = "html") -> str:
    return f"{ADMINGUIDE_ROOT}/{slug}.{ext}"


def fetch_admin_guide_entries(
    sources: Sequence[
        tuple[str, str, str | None, str | None]
    ] = ADMIN_GUIDE_SOURCES,
) -> list[AdminGuideEntry]:
    """Fetch + parse each curated admin-guide page; fall back gracefully.

    For each ``(slug, bucket, title_override, blurb_override)`` row:

    1. ``GET`` the ``.md`` source.
    2. Use ``title_override`` if supplied; otherwise the parsed top
       heading from the page.
    3. Use ``blurb_override`` if supplied; otherwise the parsed lead
       paragraph (truncated to one sentence).
    4. If the fetch fails, fall back to whatever overrides are
       available so a transient docs outage doesn't blank the
       catalog.
    """
    # Lazy import to keep the module light when the script is imported
    # for testing without making a network call.
    from connect_knowledge.page_doc import (  # noqa: PLC0415  — local import is intentional
        _parse_lead_paragraph,
        _parse_top_title,
    )

    entries: list[AdminGuideEntry] = []
    for slug, bucket, title_override, blurb_override in sources:
        url_html = _admin_guide_url(slug, ext="html")
        title: str | None = title_override
        description: str | None = blurb_override
        try:
            final_url, md = fetch_with_fallback(
                _admin_guide_url(slug, ext="md"),
                query_hint=f"amazon connect admin guide {slug}",
            )
        except Exception as exc:
            # Network blip / page move with no resolver hit — keep the
            # curated overrides if any.
            print(
                f"  warning: could not fetch admin-guide page {slug}: {exc}",
                file=sys.stderr,
            )
            md = ""
        else:
            # If the page moved and the resolver redirected us, update
            # the html link so the rendered catalog points at the
            # live page instead of the dead one.
            if final_url.endswith(".md"):
                resolved_html = final_url[:-3] + ".html"
            else:
                resolved_html = final_url
            if resolved_html != url_html:
                url_html = resolved_html

        if md:
            if title is None:
                title = _parse_top_title(md)
            if description is None:
                lead = _parse_lead_paragraph(md)
                if lead:
                    # Tighten the lead to its first sentence so the
                    # catalog row stays scannable.
                    description = lead.split(". ", 1)[0].rstrip(".") + "."

        if title is None:
            title = slug
        if description is None:
            description = "_(no description available)_"

        entries.append(
            AdminGuideEntry(
                slug=slug,
                bucket=bucket,
                title=title.strip(),
                description=description.strip(),
                url=url_html,
            )
        )
    return entries


def render_admin_guide_section(entries: list[AdminGuideEntry]) -> str:
    """Render the ``## Admin guide pages`` group with three subsections."""
    if not entries:
        return ""

    by_bucket: dict[str, list[AdminGuideEntry]] = defaultdict(list)
    for e in entries:
        by_bucket[e.bucket].append(e)

    lines = [
        "## Admin guide pages",
        "",
        "Topic-level pages from the Amazon Connect admin guide that explain how",
        "views, step-by-step guides, and the no-code UI builder hang together.",
        "Use these when the Storybook component reference is not enough — for",
        "example, when you need permissions setup, the flow patterns that drive",
        "a view, or the runtime data plumbing.",
        "",
        "URLs link to the rendered HTML page; swap `.html` → `.md` to fetch the",
        "markdown source (the same source this catalog is generated from).",
        "",
    ]

    for bucket_key, bucket_label in ADMIN_GUIDE_BUCKETS:
        rows = by_bucket.get(bucket_key, [])
        if not rows:
            continue
        lines.extend([
            f"### {bucket_label}",
            "",
            "| Topic | Description |",
            "| --- | --- |",
        ])
        for e in rows:
            desc = e.description.replace("|", r"\|").replace("\n", " ")
            lines.append(f"| [{e.title}]({e.url}) | {desc} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the rendered document to stdout without writing.",
    )
    parser.add_argument(
        "--output", type=Path, default=OUTPUT_PATH,
        help=f"Output path (default: {OUTPUT_PATH.relative_to(REPO_ROOT)}).",
    )
    parser.add_argument(
        "--with-props", action="store_true",
        help=(
            "Enrich each catalog entry with its required props by rendering "
            "the Storybook docs page with Playwright. Playwright ships as a "
            "core dependency; just install the browser binary "
            "(`uv run python -m playwright install chromium`)."
        ),
    )
    parser.add_argument(
        "--no-admin-guide", action="store_true",
        help=(
            "Skip the admin-guide index. By default the script also "
            "fetches each curated admin-guide page from "
            "docs.aws.amazon.com/connect/ and renders the Admin guide "
            "pages section."
        ),
    )
    args = parser.parse_args(argv)

    print(f"fetching {INDEX_URL}", file=sys.stderr)
    iframe_html = fetch(INDEX_URL)
    bundle_url = discover_main_bundle_url(iframe_html)
    print(f"  bundle: {bundle_url}", file=sys.stderr)
    bundle = fetch(bundle_url)
    print(f"  fetched {len(bundle):,} chars", file=sys.stderr)

    entries = parse_entries(bundle)
    print(f"  parsed {len(entries)} catalog entries", file=sys.stderr)

    if args.with_props:
        try:
            from connect_knowledge.view_doc import get_view_component_docs_batch
        except ImportError as exc:
            print(f"error: cannot import view_doc helper: {exc}", file=sys.stderr)
            return 2
        slugs = [e.story_slug for e in entries]
        print(f"  enriching {len(slugs)} entries with required props (Playwright)", file=sys.stderr)
        try:
            details = get_view_component_docs_batch(slugs)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        for entry in entries:
            doc = details.get(entry.story_slug)
            if doc is None:
                # Couldn't render this component; leave required_props as None
                # so the table cell shows "(not captured)".
                continue
            entry.required_props = list(doc.get("required_props", []))
        captured = sum(1 for e in entries if e.required_props is not None)
        print(f"  captured props for {captured}/{len(entries)} entries", file=sys.stderr)

    if args.no_admin_guide:
        admin_guide_entries: list[AdminGuideEntry] = []
        print("  skipping admin-guide index (--no-admin-guide)", file=sys.stderr)
    else:
        print(
            f"  fetching {len(ADMIN_GUIDE_SOURCES)} admin-guide pages from {ADMINGUIDE_ROOT}",
            file=sys.stderr,
        )
        admin_guide_entries = fetch_admin_guide_entries()
        print(f"  fetched {len(admin_guide_entries)} admin-guide entries", file=sys.stderr)

    by_section: dict[str, list[Entry]] = defaultdict(list)
    for e in entries:
        by_section[e.hierarchy].append(e)

    for label, _, _ in SECTIONS:
        print(f"  {label}: {len(by_section.get(label, []))}", file=sys.stderr)
    if admin_guide_entries:
        for bucket_key, bucket_label in ADMIN_GUIDE_BUCKETS:
            count = sum(1 for e in admin_guide_entries if e.bucket == bucket_key)
            print(f"  Admin guide / {bucket_label}: {count}", file=sys.stderr)

    document = build_document(
        by_section,
        with_props=args.with_props,
        admin_guide_entries=admin_guide_entries,
    )

    if args.dry_run:
        sys.stdout.write(document)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding="utf-8")
    total = len(entries) + len(admin_guide_entries)
    print(f"wrote {args.output} ({total} entries)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
