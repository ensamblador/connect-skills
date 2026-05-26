"""Refresh ``.kiro/steering/connect-blocks.md`` from the Connect docs.

Pulls the markdown source of the two upstream pages, joins them on
block name, and writes a denormalized table to the steering file.

Source pages (markdown source, not HTML):
    - https://docs.aws.amazon.com/connect/latest/adminguide/contact-block-definitions.md
    - https://docs.aws.amazon.com/connect/latest/adminguide/block-support-by-channel.md

Run:
    uv run python scripts/refresh_connect_blocks.py            # write
    uv run python scripts/refresh_connect_blocks.py --dry-run  # preview
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 30

ADMINGUIDE_ROOT = "https://docs.aws.amazon.com/connect/latest/adminguide"
DEFINITIONS_URL = f"{ADMINGUIDE_ROOT}/contact-block-definitions.md"
CHANNEL_URL = f"{ADMINGUIDE_ROOT}/block-support-by-channel.md"

DEFINITIONS_HTML_URL = f"{ADMINGUIDE_ROOT}/contact-block-definitions.html"
CHANNEL_HTML_URL = f"{ADMINGUIDE_ROOT}/block-support-by-channel.html"

EXPECTED_DEF_HEADERS = ("Block", "Description")
EXPECTED_CHANNEL_HEADERS = ("Block", "Voice", "Chat", "Task", "Email")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / ".kiro" / "steering" / "connect-blocks.md"


# ----- channel cell encoding ----------------------------------------------


def encode_channel(value: str) -> str:
    """Compress a channel-support cell to a single character.

    ``Yes``                  → ``+``
    ``No - Error branch``    → ``~``
    ``No``                   → ``-``
    Anything else            → ``?``
    """
    v = value.strip().lower()
    if v == "yes":
        return "+"
    if v.startswith("no - error"):
        return "~"
    if v == "no":
        return "-"
    return "?"


def channel_summary(voice: str, chat: str, task: str, email: str) -> str:
    """Render channel support as ``V+ C+ T~ E+``."""
    return f"V{encode_channel(voice)} C{encode_channel(chat)} T{encode_channel(task)} E{encode_channel(email)}"


# ----- markdown table parsing ---------------------------------------------


def fetch(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def split_row(line: str) -> list[str]:
    """Split a markdown table row into trimmed cells.

    Tolerates both `| a | b |` and `|a|b|`. Strips the leading/trailing
    empty cells produced by the surrounding pipes.
    """
    parts = [c.strip() for c in line.strip().split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def parse_md_table(markdown: str, expected_headers: tuple[str, ...]) -> list[list[str]]:
    """Find the first markdown table whose header row matches and return data rows."""
    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        if "|" not in line:
            continue
        cells = split_row(line)
        if tuple(cells) != expected_headers:
            continue
        # Next line must be the separator (---).
        if i + 1 >= len(lines) or not re.match(r"^\s*\|?\s*-+", lines[i + 1]):
            continue
        rows: list[list[str]] = []
        for body in lines[i + 2 :]:
            if "|" not in body:
                break
            cells = split_row(body)
            if not cells:
                break
            rows.append(cells)
        return rows
    raise RuntimeError(
        f"could not find a markdown table with headers {expected_headers}; "
        "upstream page format may have changed"
    )


# ----- block extraction ---------------------------------------------------


LINK_RE = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<href>[^)]+)\)")


@dataclass
class Block:
    name: str
    description: str | None
    doc_md: str | None  # the .md href, e.g. ``connect-assistant-block.md``
    channels: str | None  # encoded summary or None if not in channel table


def parse_block_cell(cell: str) -> tuple[str, str | None]:
    """Pull the block name and href out of a cell like ``[Cases](cases-block.md)``.

    Falls back to (cell, None) for plain-text cells.
    """
    cell = cell.strip()
    m = LINK_RE.search(cell)
    if not m:
        return cell, None
    return m.group("text").strip(), m.group("href").strip()


def parse_definitions(md: str) -> dict[str, Block]:
    rows = parse_md_table(md, EXPECTED_DEF_HEADERS)
    out: dict[str, Block] = {}
    for row in rows:
        if len(row) < 2:
            continue
        name, href = parse_block_cell(row[0])
        # description cells can have escaped pipes / inline markdown — keep as-is
        description = row[1].strip()
        out[name] = Block(
            name=name, description=description, doc_md=href, channels=None
        )
    return out


def parse_channels(md: str) -> dict[str, str]:
    rows = parse_md_table(md, EXPECTED_CHANNEL_HEADERS)
    out: dict[str, str] = {}
    for row in rows:
        if len(row) < 5:
            continue
        name, _href = parse_block_cell(row[0])
        out[name] = channel_summary(row[1], row[2], row[3], row[4])
    return out


def join_blocks(defs: dict[str, Block], chans: dict[str, str]) -> list[Block]:
    """Outer-join, preserving alphabetical order by name."""
    all_names = sorted(set(defs) | set(chans), key=str.casefold)
    out: list[Block] = []
    for name in all_names:
        b = defs.get(name) or Block(name=name, description=None, doc_md=None, channels=None)
        b.channels = chans.get(name)  # may be None if absent
        out.append(b)
    return out


# ----- rendering -----------------------------------------------------------


def md_url_for(href: str | None) -> str:
    if not href:
        return ""
    # ``connect-assistant-block.md`` → ``.../connect-assistant-block.html``
    stem = href[:-3] if href.endswith(".md") else href
    return f"{ADMINGUIDE_ROOT}/{stem}.html"


def render_table(blocks: list[Block]) -> str:
    lines = [
        "| Block | Channels | Description |",
        "| --- | --- | --- |",
    ]
    for b in blocks:
        url = md_url_for(b.doc_md)
        link_cell = f"[{b.name}]({url})" if url else b.name
        channels = b.channels or "?"
        description = (b.description or "").replace("\n", " ").strip() or "_(no description in source)_"
        lines.append(f"| {link_cell} | {channels} | {description} |")
    return "\n".join(lines)


def content_hash(table: str) -> str:
    return "sha256:" + hashlib.sha256(table.encode("utf-8")).hexdigest()[:16]


FRONTMATTER_TEMPLATE = """\
---
inclusion: manual
last_refreshed: {today}
block_count: {block_count}
source_urls:
  - {def_url}
  - {chan_url}
content_checksum: {checksum}
---
"""


BODY_HEADER = """\
# Connect flow block catalog

Quick lookup table for every flow block in Amazon Connect, joined from
the two source pages below. Refresh with
``uv run python scripts/refresh_connect_blocks.py``.

**Activation:** this file is opt-in. Reference it from chat with
`#connect-blocks` when you're sketching a flow, picking blocks for a
mermaid diagram, or generating Flow language JSON.

**Freshness rule (for the agent):** before relying on this catalog,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 7 days, run
``uv run python scripts/refresh_connect_blocks.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.
A regenerated file with no diff is fine — `last_refreshed` is the only
thing that needs updating, and the script handles that automatically.

**Channel column legend** (in `V C T E` order: Voice, Chat, Task, Email):
``+`` supported, ``~`` not supported but emits an Error branch,
``-`` not supported, ``?`` not listed in the channel-support page.

For depth on any block (parameters, branches, examples), follow the
block name link. For the language and JSON shape see the
[Connect Flow language reference](https://docs.aws.amazon.com/connect/latest/APIReference/flow-language.html).

"""


def build_document(blocks: list[Block]) -> str:
    table = render_table(blocks)
    frontmatter = FRONTMATTER_TEMPLATE.format(
        today=date.today().isoformat(),
        block_count=len(blocks),
        def_url=DEFINITIONS_HTML_URL,
        chan_url=CHANNEL_HTML_URL,
        checksum=content_hash(table),
    )
    return frontmatter + "\n" + BODY_HEADER + table + "\n"


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
    args = parser.parse_args(argv)

    print(f"fetching {DEFINITIONS_URL}", file=sys.stderr)
    defs = parse_definitions(fetch(DEFINITIONS_URL))
    print(f"  parsed {len(defs)} block definitions", file=sys.stderr)

    print(f"fetching {CHANNEL_URL}", file=sys.stderr)
    chans = parse_channels(fetch(CHANNEL_URL))
    print(f"  parsed {len(chans)} channel rows", file=sys.stderr)

    blocks = join_blocks(defs, chans)

    only_in_defs = sorted(set(defs) - set(chans), key=str.casefold)
    only_in_chans = sorted(set(chans) - set(defs), key=str.casefold)
    if only_in_defs:
        print(
            f"  note: {len(only_in_defs)} block(s) in definitions but not channel matrix: "
            f"{', '.join(only_in_defs)}",
            file=sys.stderr,
        )
    if only_in_chans:
        print(
            f"  note: {len(only_in_chans)} block(s) in channel matrix but not definitions: "
            f"{', '.join(only_in_chans)}",
            file=sys.stderr,
        )

    document = build_document(blocks)

    if args.dry_run:
        sys.stdout.write(document)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding="utf-8")
    print(f"wrote {args.output} ({len(blocks)} blocks)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
