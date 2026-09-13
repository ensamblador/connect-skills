"""Refresh ``connect_knowledge_mcp/connect_knowledge/_view_component_types.py``.

Generates the catalog of valid component ``Type`` values that
``view_validator.validate_view_json`` checks against. Also emits a
required-props snapshot per component so the validator can flag
missing required props without making a Playwright call on every
``validate_view_json`` invocation.

Two-step pipeline:

1. Parse the View Dictionary Storybook bundle (cheap HTTP) — every
   component story carries its hierarchy and component name. This is
   the same parse ``refresh_connect_views.py`` does.
2. Drive Playwright against each component's docs page to read the
   ``ArgsTable`` and capture which props are required. This is the
   same call ``get_view_component_doc`` makes, batched.

Run:
    uv run python .kiro/skills/connect-view-author/scripts/refresh_connect_view_component_types.py            # write
    uv run python .kiro/skills/connect-view-author/scripts/refresh_connect_view_component_types.py --dry-run  # preview

Setup:
    uv sync --directory connect_knowledge_mcp                        # installs playwright (core dep)
    uv run --directory connect_knowledge_mcp python -m playwright install chromium
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# This script lives at ``.kiro/skills/connect-view-author/scripts/`` —
# four levels under the repo root (scripts → connect-view-author →
# skills → .kiro → repo root).
REPO_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_PATH = (
    REPO_ROOT / "connect_knowledge_mcp" / "connect_knowledge" / "_view_component_types.py"
)

# Component names that the docs include as catalog entries but that are
# not real component Types (umbrella reference pages, prose-only entries).
SKIP_TYPES: set[str] = {
    "Common Configuration",
    "Customer-managed Views",
    "UI Components",
}

FILE_TEMPLATE = '''\
"""Auto-generated. Do not edit by hand.

Regenerate with:
    uv run python .kiro/skills/connect-view-author/scripts/refresh_connect_view_component_types.py

Source:
    https://d3irlmavjxd3d8.cloudfront.net/  (Amazon Connect View Dictionary)
"""

VALID_VIEW_COMPONENT_TYPES: frozenset[str] = frozenset({{
{types_block}
}})

# Maps every component type to the set of View Dictionary hierarchies
# it appears in (``UI Component``, ``FormView Component``,
# ``AWS-managed Views``, ``Customer-managed Views``). A type that
# appears in multiple hierarchies is valid in any of them; a type that
# appears only in ``FormView Component`` is only valid inside a
# ``Form`` ancestor.
COMPONENT_HIERARCHIES: dict[str, frozenset[str]] = {{
{hierarchy_block}
}}

# Convenience: types that only appear in the FormView hierarchy. The
# validator surfaces a warning when one of these is used outside a
# ``Form`` ancestor.
FORMVIEW_ONLY_TYPES: frozenset[str] = frozenset({{
{formview_only_block}
}})

# Required props per component, snapshotted from each Storybook docs
# page's ArgsTable. The validator uses this to flag components that
# lack a required prop.
#
# Components that don't appear here had no ArgsTable on their docs
# page (e.g. umbrella reference entries, the standalone ``Image``
# story) — for those, ``validate_view_json`` only checks that ``Type``
# is recognized.
REQUIRED_PROPS: dict[str, frozenset[str]] = {{
{required_block}
}}
'''


def _format_set(values: list[str], indent: str = "    ") -> str:
    return "\n".join(f'{indent}"{v}",' for v in values)


def _format_hierarchy_dict(items: dict[str, set[str]], indent: str = "    ") -> str:
    out: list[str] = []
    for name in sorted(items, key=str.casefold):
        hierarchies = sorted(items[name])
        inner = ", ".join(f'"{h}"' for h in hierarchies)
        out.append(f'{indent}"{name}": frozenset({{{inner}}}),')
    return "\n".join(out)


def _format_required(items: dict[str, list[str]], indent: str = "    ") -> str:
    if not items:
        return f"{indent}# (none captured — run with --with-props on a network-connected machine)"
    out: list[str] = []
    for name in sorted(items, key=str.casefold):
        props = items[name]
        if not props:
            out.append(f'{indent}"{name}": frozenset(),')
        else:
            inner = ", ".join(f'"{p}"' for p in props)
            out.append(f'{indent}"{name}": frozenset({{{inner}}}),')
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the rendered module to stdout without writing.",
    )
    parser.add_argument(
        "--output", type=Path, default=OUTPUT_PATH,
        help=f"Output path (default: {OUTPUT_PATH.relative_to(REPO_ROOT)}).",
    )
    args = parser.parse_args(argv)

    # Reuse the existing bundle parser — keeps a single source of truth
    # for the Storybook scrape. ``refresh_connect_views.py`` lives in
    # ``.kiro/scripts``; import it from there. The module inserts its own
    # dir on sys.path at import time so its ``_doc_fetcher`` sibling
    # resolves.
    refresh_scripts_dir = REPO_ROOT / ".kiro" / "scripts"
    sys.path.insert(0, str(refresh_scripts_dir))
    from refresh_connect_views import (  # noqa: PLC0415
        INDEX_URL,
        discover_main_bundle_url,
        fetch,
        parse_entries,
    )

    print(f"fetching {INDEX_URL}", file=sys.stderr)
    iframe_html = fetch(INDEX_URL)
    bundle_url = discover_main_bundle_url(iframe_html)
    print(f"  bundle: {bundle_url}", file=sys.stderr)
    bundle = fetch(bundle_url)
    entries = parse_entries(bundle)
    print(f"  parsed {len(entries)} catalog entries", file=sys.stderr)

    # Filter to component-typed entries (drop umbrella / prose-only).
    typed = [e for e in entries if e.name not in SKIP_TYPES]
    print(f"  emitting {len(typed)} component types", file=sys.stderr)

    type_names = sorted({e.name for e in typed}, key=str.casefold)

    # Aggregate hierarchies: a Type can appear in several (e.g. DatePicker
    # is documented as both UI Component and FormView Component).
    hierarchies_by_type: dict[str, set[str]] = {}
    for e in typed:
        hierarchies_by_type.setdefault(e.name, set()).add(e.hierarchy)

    formview_only = sorted(
        n for n, hs in hierarchies_by_type.items() if hs == {"FormView Component"}
    )

    # Drive Playwright for required-props.
    try:
        from connect_knowledge.view_doc import get_view_component_docs_batch
    except ImportError as exc:
        print(f"error: cannot import view_doc helper: {exc}", file=sys.stderr)
        return 2

    slugs = [e.story_slug for e in typed]
    print(
        f"  fetching required props for {len(slugs)} components via Playwright",
        file=sys.stderr,
    )
    try:
        details = get_view_component_docs_batch(slugs)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    required: dict[str, list[str]] = {}
    captured = 0
    for entry in typed:
        doc = details.get(entry.story_slug)
        if doc is None:
            continue  # no ArgsTable; skip in REQUIRED_PROPS map
        required[entry.name] = list(doc.get("required_props", []))
        captured += 1
    print(f"  captured props for {captured}/{len(typed)} components", file=sys.stderr)

    rendered = FILE_TEMPLATE.format(
        types_block=_format_set(type_names),
        hierarchy_block=_format_hierarchy_dict(hierarchies_by_type),
        formview_only_block=_format_set(formview_only),
        required_block=_format_required(required),
    )

    if args.dry_run:
        sys.stdout.write(rendered)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output} ({len(type_names)} types)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
