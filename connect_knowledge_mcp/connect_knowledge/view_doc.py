"""Per-component deep-dive helper for the Amazon Connect View Dictionary.

The View Dictionary (https://d3irlmavjxd3d8.cloudfront.net/) is a
client-rendered Storybook bundle, so per-component pages — the props
table, examples, schema — are not reachable with a plain HTTP fetch.
We drive a headless Chromium via Playwright, navigate to the docs
page for the component, wait for the rendered ``ArgsTable`` to mount,
then extract a structured view of the props table plus the rendered
HTML for downstream callers.

Lazy import of Playwright keeps this module optional: callers that
never invoke it pay no cost, and the wider ``connect_knowledge``
package remains installable in environments where Chromium is not
available (e.g. the slim MCP server image).

DOM contract we rely on (Storybook 6 ``ArgsTable``):

    tr
      td (name cell)
        span:nth-of-type(1)        # property name, e.g. "Label"
        span[title="Required"]?    # required marker, present iff required
      td (description cell)
        div:nth-of-type(1) span    # human description text
        div:nth-of-type(2) span+   # one or more type-summary tokens
                                   # joined with ' | ' for multi-token types
      td (control cell, optional)
        span                       # "-" placeholder, or
        div span+                  # default value token(s)

We deliberately key off positional selectors (``> div:nth-of-type(N)``)
rather than emotion-CSS class names (``css-…``) because those class
names are regenerated on every Storybook build. Position is stable;
hashes are not.

Setup (one-time):

    uv sync --directory connect_knowledge_mcp                        # installs playwright (core dep)
    uv run --directory connect_knowledge_mcp python -m playwright install chromium

Public API:

    get_view_component_doc(slug, *, headless=True, timeout=30_000)
    get_view_component_docs_batch(slugs, *, headless=True, timeout=30_000)

where ``slug`` is the Storybook story id (e.g.
``ui-component-datepicker--with-all``,
``formview-component-datepicker--with-all``).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

VIEW_DICT_ROOT = "https://d3irlmavjxd3d8.cloudfront.net"

DOCS_ROOT_SELECTOR = "#docs-root"
ARGS_TABLE_SELECTOR = "#docs-root .docblock-argstable"
ARGS_ROW_SELECTOR = "#docs-root .docblock-argstable tbody tr"

_T = TypeVar("_T")


def _run_off_loop(fn: Callable[[], _T]) -> _T:
    """Run a blocking, sync-Playwright callable in a dedicated thread.

    Playwright's sync API raises if used inside a thread that owns a
    running asyncio event loop. The MCP server registers these tools
    as sync functions but invokes them on the loop thread, so calling
    ``sync_playwright()`` directly there fails with "It looks like you
    are using Playwright Sync API inside the asyncio loop." Running the
    work in a fresh worker thread (which has no event loop) sidesteps
    that, while still working fine when called from a plain sync
    context (scripts, tests).
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(fn).result()



def _ensure_playwright() -> Any:
    """Import sync_playwright lazily and surface a friendly error if missing."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover — exercised in environments without playwright
        raise RuntimeError(
            "playwright is not installed. It is a core dependency of the "
            "MCP server; sync it and install the Chromium browser:\n"
            "    uv sync --directory connect_knowledge_mcp\n"
            "    uv run --directory connect_knowledge_mcp python -m playwright install chromium"
        ) from exc
    return sync_playwright


# ----- data shape ---------------------------------------------------------


@dataclass
class PropDoc:
    name: str
    required: bool
    description: str | None
    type_summary: str | None
    default_summary: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "required": self.required,
            "description": self.description,
            "type_summary": self.type_summary,
            "default_summary": self.default_summary,
        }


@dataclass
class ViewComponentDoc:
    slug: str
    url: str
    title: str | None
    description: str | None
    props: list[PropDoc] = field(default_factory=list)
    docs_html: str | None = None  # rendered #docs-root subtree

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "props": [p.to_dict() for p in self.props],
            "required_props": [p.name for p in self.props if p.required],
            "optional_props": [p.name for p in self.props if not p.required],
            "docs_html": self.docs_html,
        }


# ----- extraction --------------------------------------------------------


def _docs_url(slug: str) -> str:
    """Translate a Storybook story id into a fetchable iframe URL.

    The catalog links use ``/?path=/docs/<slug>`` against the parent
    page, but Storybook itself reads the iframe directly from
    ``iframe.html?id=<slug>&viewMode=docs`` — that's the URL the
    parent navigates the iframe to once the user clicks a sidebar
    entry. Going straight to the iframe skips loading the manager
    chrome and shaves about a second per call.
    """
    return f"{VIEW_DICT_ROOT}/iframe.html?id={slug}&viewMode=docs"


def _split_required(name_cell: str) -> tuple[str, bool]:
    """Storybook marks required props by appending ``*`` to the name.

    Kept as a fallback for environments where the
    ``span[title="Required"]`` marker isn't present.
    """
    name = name_cell.strip()
    if name.endswith("*"):
        return name.rstrip("*").strip(), True
    return name, False


def _extract_row(row: Any) -> PropDoc | None:
    """Extract a PropDoc from a single ArgsTable ``<tr>`` element.

    Reads the precise DOM contract documented at the top of this
    module (positional selectors against the cell sub-tree). Returns
    ``None`` if the row doesn't have a name in cell 0.
    """
    cells = row.locator("td").all()
    if not cells:
        return None

    # Cell 0: name + optional required marker
    name_locator = cells[0].locator("span").first
    if not name_locator.count():
        return None
    name = name_locator.inner_text().strip().rstrip("*").strip()
    if not name:
        return None
    required = bool(cells[0].locator('span[title="Required"]').count())

    # Cell 1: description + type summary
    description: str | None = None
    type_summary: str | None = None
    if len(cells) >= 2:
        desc_block = cells[1].locator("> div").nth(0)
        if desc_block.count():
            text = desc_block.inner_text().strip()
            description = text or None
        type_block = cells[1].locator("> div").nth(1)
        if type_block.count():
            tokens = [
                t.strip()
                for t in type_block.locator("span").all_inner_texts()
                if t.strip()
            ]
            if tokens:
                type_summary = " | ".join(tokens)

    # Cell 2: control / default (optional)
    default_summary: str | None = None
    if len(cells) >= 3:
        # The "no default" placeholder is a bare ``<span>-</span>``.
        bare = cells[2].locator("> span").first
        if bare.count():
            text = bare.inner_text().strip()
            if text and text not in {"-", "–", "—"}:
                default_summary = text
        # When there is a default, it lives inside a ``<div>``.
        if default_summary is None:
            div = cells[2].locator("> div").first
            if div.count():
                tokens = [
                    t.strip()
                    for t in div.locator("span").all_inner_texts()
                    if t.strip()
                ]
                if tokens:
                    default_summary = " | ".join(tokens)

    return PropDoc(
        name=name,
        required=required,
        description=description,
        type_summary=type_summary,
        default_summary=default_summary,
    )


def _component_title_from_slug(slug: str) -> str:
    """Reverse the slug into a readable hierarchy/name pair, e.g.
    ``ui-component-datepicker--with-all`` →
    ``UI Component / DatePicker (with-all)``.

    Used when the rendered page omits an explicit title heading we can
    capture cheaply.
    """
    base, _, story = slug.partition("--")
    parts = base.split("-")
    # Heuristic: hierarchy is the leading 1-3 lowercased segments.
    known_hierarchies = [
        ("ui-component", "UI Component"),
        ("formview-component", "FormView Component"),
        ("aws-managed-views", "AWS-managed Views"),
        ("customer-managed-views", "Customer-managed Views"),
    ]
    hierarchy = None
    name_parts = parts
    for prefix, label in known_hierarchies:
        prefix_parts = prefix.split("-")
        if parts[: len(prefix_parts)] == prefix_parts:
            hierarchy = label
            name_parts = parts[len(prefix_parts):]
            break
    name = "".join(p.capitalize() for p in name_parts) if name_parts else base
    if hierarchy:
        title = f"{hierarchy} / {name}"
    else:
        title = name
    if story:
        title = f"{title} ({story})"
    return title


def get_view_component_doc(
    slug: str,
    *,
    headless: bool = True,
    timeout: int = 30_000,
    capture_html: bool = False,
) -> dict[str, Any]:
    """Fetch and parse a View Dictionary component docs page.

    Args:
        slug: The Storybook story id (the bit after ``?path=/docs/`` in
            the catalog link), e.g. ``ui-component-datepicker--with-all``
            or ``formview-component-datepicker--with-all``. The
            ``connect-views`` steering catalog has the canonical slug
            for every component.
        headless: Run Chromium headless (default) or visible — set to
            ``False`` only for local debugging.
        timeout: Per-step timeout in milliseconds for navigation and
            selector waits.
        capture_html: When ``True``, also return the rendered
            ``#docs-root`` subtree as ``docs_html``. Off by default to
            keep responses small for callers that only need the props.

    Returns:
        Dict shaped like ``ViewComponentDoc.to_dict()``: ``slug``,
        ``url``, ``title``, ``description``, ``props`` (list of
        ``{name, required, description, type_summary, default_summary}``),
        ``required_props`` (names only), ``optional_props`` (names
        only), and optionally ``docs_html``.

    Raises:
        RuntimeError: If Playwright is not installed (see the
            module-level setup notes).
        playwright.sync_api.TimeoutError: If the docs page does not
            render an ``ArgsTable`` within ``timeout`` ms.
    """
    sync_playwright = _ensure_playwright()

    url = _docs_url(slug)

    def _work() -> dict[str, Any]:
        doc = ViewComponentDoc(
            slug=slug,
            url=url,
            title=_component_title_from_slug(slug),
            description=None,
        )
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context(viewport={"width": 1280, "height": 1600})
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                page.wait_for_selector(ARGS_TABLE_SELECTOR, timeout=timeout)

                # Description is rendered as the first ``.sbdocs-p`` paragraph
                # under the docs root (set by Storybook from the
                # ``docs.description.component`` parameter).
                try:
                    first_paragraph = page.locator("#docs-root .sbdocs-p").first
                    if first_paragraph.count():
                        text = first_paragraph.inner_text(timeout=2_000).strip()
                        doc.description = text or None
                except Exception:  # pragma: no cover — best effort
                    logger.debug("could not extract component description", exc_info=True)

                for row in page.locator(ARGS_ROW_SELECTOR).all():
                    prop = _extract_row(row)
                    if prop is not None:
                        doc.props.append(prop)

                if capture_html:
                    doc.docs_html = page.locator(DOCS_ROOT_SELECTOR).inner_html()
            finally:
                browser.close()
        return doc.to_dict()

    return _run_off_loop(_work)


def get_view_component_docs_batch(
    slugs: list[str],
    *,
    headless: bool = True,
    timeout: int = 30_000,
) -> dict[str, dict[str, Any]]:
    """Fetch many components in a single Playwright session.

    Useful for the ``refresh_connect_views.py`` enrichment pass — one
    Chromium launch, N navigations, instead of N launches.

    Args:
        slugs: Story ids to fetch.
        headless: Run Chromium headless (default).
        timeout: Per-step timeout in milliseconds.

    Returns:
        Mapping of ``slug → ViewComponentDoc.to_dict()``. Slugs that
        fail to load (e.g. the docs page has no ArgsTable) are
        silently omitted; check missing keys to detect failures.
    """
    sync_playwright = _ensure_playwright()

    def _work() -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context(viewport={"width": 1280, "height": 1600})
            page = context.new_page()
            try:
                for slug in slugs:
                    url = _docs_url(slug)
                    doc = ViewComponentDoc(
                        slug=slug,
                        url=url,
                        title=_component_title_from_slug(slug),
                        description=None,
                    )
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                        page.wait_for_selector(ARGS_TABLE_SELECTOR, timeout=timeout)
                    except Exception:
                        logger.warning("no ArgsTable for %s", slug)
                        continue

                    try:
                        first_paragraph = page.locator("#docs-root .sbdocs-p").first
                        if first_paragraph.count():
                            doc.description = first_paragraph.inner_text(timeout=2_000).strip() or None
                    except Exception:
                        logger.debug("description extraction failed for %s", slug, exc_info=True)

                    for row in page.locator(ARGS_ROW_SELECTOR).all():
                        prop = _extract_row(row)
                        if prop is not None:
                            doc.props.append(prop)

                    results[slug] = doc.to_dict()
            finally:
                browser.close()
        return results

    return _run_off_loop(_work)
