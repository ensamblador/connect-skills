"""Refresh ``.kiro/steering/connect-flow-language.md`` from the Connect Flow language docs.

Pulls the Flow language grammar plus the four action category index pages
(``contact-actions``, ``flow-control-actions``, ``interactions``,
``participant-actions``), walks each per-action page for its first
paragraph, and joins everything into a single steering file.

Source pages (markdown source, not HTML), all under
``https://docs.aws.amazon.com/connect/latest/APIReference/``:

    flow-language-actions.md   ← the grammar / Action shape spec
    contact-actions.md         ← ~28 contact actions
    flow-control-actions.md    ← ~15 flow-control actions
    interactions.md            ← ~8 interactions actions
    participant-actions.md     ← ~6 participant actions

Run:
    uv run python scripts/refresh_connect_flow_language.py            # write
    uv run python scripts/refresh_connect_flow_language.py --dry-run  # preview
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 30
PER_FETCH_SLEEP = 0.2  # be polite when crawling per-action pages

API_REF_ROOT = "https://docs.aws.amazon.com/connect/latest/APIReference"
GRAMMAR_URL = f"{API_REF_ROOT}/flow-language-actions.md"
GRAMMAR_HTML_URL = f"{API_REF_ROOT}/flow-language-actions.html"

# (category-name, index-page-md, index-page-html)
CATEGORIES = [
    ("Contact", "contact-actions.md", "contact-actions.html"),
    ("Flow control", "flow-control-actions.md", "flow-control-actions.html"),
    ("Interactions", "interactions.md", "interactions.html"),
    ("Participant", "participant-actions.md", "participant-actions.html"),
]

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / ".kiro" / "steering" / "connect-flow-language.md"
ACTION_TYPES_PATH = REPO_ROOT / "src" / "connect_knowledge" / "_action_types.py"


# ----- fetching -----------------------------------------------------------


def fetch(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


# ----- catalog parsing ----------------------------------------------------


# Index pages list actions like:
#     + [InvokeLambdaFunction](interactions-invokelambdafunction.md)
INDEX_LINK_RE = re.compile(r"^\+\s*\[(?P<name>[^\]]+)\]\((?P<href>[^)]+)\)\s*$")


@dataclass
class Action:
    name: str
    category: str
    page_md: str  # e.g. "interactions-invokelambdafunction.md"
    description: str | None = None


def parse_category_index(category: str, markdown: str) -> list[Action]:
    actions: list[Action] = []
    for line in markdown.splitlines():
        m = INDEX_LINK_RE.match(line.strip())
        if not m:
            continue
        actions.append(
            Action(
                name=m.group("name").strip(),
                category=category,
                page_md=m.group("href").strip(),
            )
        )
    return actions


# Per-action page first-paragraph extractor.
#
# Pages start with:
#     # ActionName
#     <a name="..."></a>
#
#     <description paragraph>
#
#     ## Parameter object   ← we stop here
#
# We grab everything between the anchor and the first ``## `` heading,
# strip blank lines, and take the first non-empty paragraph.


def extract_first_paragraph(markdown: str) -> str | None:
    lines = markdown.splitlines()
    # Find the closing of the leading anchor line.
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("<a name="):
            start = i + 1
            break
    body_lines: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body_lines.append(line)
    # Collapse to paragraphs.
    text = "\n".join(body_lines).strip()
    if not text:
        return None
    paragraph = text.split("\n\n", 1)[0]
    # Tidy: collapse internal newlines, strip trailing whitespace.
    return " ".join(p.strip() for p in paragraph.splitlines() if p.strip()) or None


def fill_descriptions(actions: list[Action]) -> None:
    for i, a in enumerate(actions, 1):
        url = f"{API_REF_ROOT}/{a.page_md}"
        try:
            md = fetch(url)
        except Exception as exc:  # noqa: BLE001 — keep going on individual failures
            print(
                f"  [{i}/{len(actions)}] {a.name}: fetch failed ({exc})",
                file=sys.stderr,
            )
            continue
        a.description = extract_first_paragraph(md)
        print(
            f"  [{i}/{len(actions)}] {a.name}: "
            f"{'ok' if a.description else 'no description found'}",
            file=sys.stderr,
        )
        time.sleep(PER_FETCH_SLEEP)


# ----- rendering ----------------------------------------------------------


def html_url_for(href: str) -> str:
    stem = href[:-3] if href.endswith(".md") else href
    return f"{API_REF_ROOT}/{stem}.html"


def render_action_table(actions: list[Action]) -> str:
    lines = [
        "| Action | Category | Description |",
        "| --- | --- | --- |",
    ]
    for a in sorted(actions, key=lambda x: (x.category.lower(), x.name.lower())):
        url = html_url_for(a.page_md)
        link = f"[{a.name}]({url})"
        desc = (a.description or "_(no description in source)_").replace("\n", " ").strip()
        lines.append(f"| {link} | {a.category} | {desc} |")
    return "\n".join(lines)


def content_hash(payload: str) -> str:
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


FRONTMATTER_TEMPLATE = """\
---
inclusion: manual
last_refreshed: {today}
action_count: {action_count}
source_urls:
  - {grammar_url}
{category_urls}
content_checksum: {checksum}
---
"""


BODY_HEADER = """\
# Connect Flow language reference

Distilled from the Connect Flow language API reference. Two parts:
the **grammar** (how every Action is shaped) and the **action catalog**
(every concrete Action type, its category, and a one-line description).

Refresh with ``uv run python scripts/refresh_connect_flow_language.py``.

**Activation:** opt-in. Reference from chat with `#connect-flow-language`
when generating, validating, or reviewing flow JSON. Pair with
`#connect-blocks` when you need both the UI block names and the
Flow language Action types.

**Freshness rule (for the agent):** before relying on this reference,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 7 days, run
``uv run python scripts/refresh_connect_flow_language.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.

For depth on any Action (full Parameters object, errors, examples),
follow the action name link. The
[Connect Flow language overview](https://docs.aws.amazon.com/connect/latest/APIReference/flow-language.html)
and the
[example flow](https://docs.aws.amazon.com/connect/latest/APIReference/flow-language-example.html)
are the authoritative entry points.

"""


GRAMMAR_SECTION = """\
## Action grammar

Every Action in a flow has four fields: `Identifier`, `Type`,
`Parameters`, `Transitions`.

### Identifier

A string unique among all Actions in the same flow. Up to 50 characters.
Can include unicode and spaces. May be opaque or human-friendly.

**Forbidden characters:** ``%``, ``:``, ``(``, ``\\``, ``/``, ``)``,
``=``, ``$``, ``,``, ``;``, ``[``, ``]``, ``{``, ``}``.

**Forbidden values:** ``__proto__``, ``constructor``, ``__defineGetter__``,
``__defineSetter__``, ``toString``, ``hasOwnProperty``, ``isPrototypeOf``,
``propertyIsEnumerable``, ``toLocaleString``, ``valueOf``.

### Type

The Action type, drawn from the Action catalog below
(``InvokeLambdaFunction``, ``Loop``, ``MessageParticipant``, etc.).

### Parameters

Per-Action object whose shape is defined on the individual Action's
reference page. Differs for every Action — follow the link in the
catalog to get the exact schema.

### Transitions

Defines how to leave this Action. Three sub-fields:

- **NextAction** *(string)* — Identifier of the Action to run if no
  error or condition preempts. For terminal Actions (e.g.
  `EndFlowExecution`), set Transitions to an empty object.
- **Errors** *(list)* — each entry: ``{ "ErrorType": "<error>", "NextAction": "<Identifier>" }``.
  The list of valid ``ErrorType`` values is per-Action.
- **Conditions** *(list, ordered)* — each entry:
  ``{ "NextAction": "<Identifier>", "Condition": { "Operator": ..., "Operands": [...] } }``.
  Evaluated in order; the first to evaluate true wins.

### The Condition object

A `Condition` has two required fields: `Operator` and `Operands`.

| Operator | Description | Operand type | Operand count |
| --- | --- | --- | --- |
| Equals | true if the string exactly equals the result. | String | One |
| TextStartsWith | true if the result, as text, begins with the string. | String | One |
| TextEndsWith | true if the result, as text, ends with the string. | String | One |
| TextContains | true if the result, as text, contains the string at least once. | String | One |
| NumberGreaterThan | true if the result, as a number, is larger than the string. False if either is not numeric. | String | One |
| NumberGreaterOrEqualTo | true if the result, as a number, is ≥ the string. False if either is not numeric. | String | One |
| NumberLessThan | true if the result, as a number, is smaller than the string. False if either is not numeric. | String | One |
| NumberLessOrEqualTo | true if the result, as a number, is ≤ the string. False if either is not numeric. | String | One |

**Nesting limits:** Conditions may not be nested more than 5 deep,
and a single Condition may not contain more than 50 sub-Conditions
total (regardless of nesting depth).

**Example Condition** — true if the result starts with ``ABC``:

```json
{
    "Operator": "TextStartsWith",
    "Operands": ["ABC"]
}
```

"""


def build_document(grammar_section: str, action_table: str, action_count: int) -> str:
    cat_urls = "\n".join(
        f"  - {API_REF_ROOT}/{html_name}" for _, _md, html_name in CATEGORIES
    )
    payload = grammar_section + action_table
    frontmatter = FRONTMATTER_TEMPLATE.format(
        today=date.today().isoformat(),
        action_count=action_count,
        grammar_url=GRAMMAR_HTML_URL,
        category_urls=cat_urls,
        checksum=content_hash(payload),
    )
    return (
        frontmatter
        + "\n"
        + BODY_HEADER
        + grammar_section
        + "## Action catalog\n\n"
        + action_table
        + "\n"
    )


# ----- valid-action-types module ------------------------------------------


_ACTION_TYPES_TEMPLATE = '''\
"""Auto-generated. Do not edit by hand.

Regenerate with:
    uv run python scripts/refresh_connect_flow_language.py

Source pages:
{source_comment}
"""

VALID_ACTION_TYPES: frozenset[str] = frozenset({{
{members}
}})

# Maps every Action type to its category, useful for error messages and
# catalog grouping.
ACTION_CATEGORY: dict[str, str] = {{
{categories}
}}
'''


def write_action_types_module(actions: list[Action]) -> None:
    members = "\n".join(f'    "{a.name}",' for a in sorted(actions, key=lambda x: x.name))
    categories = "\n".join(
        f'    "{a.name}": "{a.category}",'
        for a in sorted(actions, key=lambda x: x.name)
    )
    sources = [GRAMMAR_HTML_URL] + [f"{API_REF_ROOT}/{html}" for _, _md, html in CATEGORIES]
    source_comment = "\n".join(f"    {url}" for url in sources)
    body = _ACTION_TYPES_TEMPLATE.format(
        members=members,
        categories=categories,
        source_comment=source_comment,
    )
    ACTION_TYPES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTION_TYPES_PATH.write_text(body, encoding="utf-8")


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
        "--skip-descriptions",
        action="store_true",
        help=(
            "Skip the per-action page crawl. Faster, but the description "
            "column will be blank. Useful for quick structural changes."
        ),
    )
    args = parser.parse_args(argv)

    print(f"fetching {GRAMMAR_URL}", file=sys.stderr)
    fetch(GRAMMAR_URL)  # validates the URL is alive; we use the static distillation

    actions: list[Action] = []
    for category, md_name, _html_name in CATEGORIES:
        url = f"{API_REF_ROOT}/{md_name}"
        print(f"fetching {url}", file=sys.stderr)
        category_actions = parse_category_index(category, fetch(url))
        print(f"  parsed {len(category_actions)} {category} actions", file=sys.stderr)
        actions.extend(category_actions)

    if args.skip_descriptions:
        print("skipping per-action crawl (--skip-descriptions)", file=sys.stderr)
    else:
        print(f"crawling {len(actions)} per-action pages for descriptions", file=sys.stderr)
        fill_descriptions(actions)

    document = build_document(GRAMMAR_SECTION, render_action_table(actions), len(actions))

    if args.dry_run:
        sys.stdout.write(document)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding="utf-8")
    print(f"wrote {args.output} ({len(actions)} actions)", file=sys.stderr)

    write_action_types_module(actions)
    print(
        f"wrote {ACTION_TYPES_PATH} ({len(actions)} action types)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
