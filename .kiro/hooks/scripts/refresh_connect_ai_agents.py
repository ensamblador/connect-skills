"""Refresh ``.kiro/steering/connect-ai-agents.md`` from the Connect docs.

Unlike the other ``refresh_*.py`` scripts in this directory, the AI
agents steering file is **hand-curated prose**, not an auto-generated
table. The right job for this script is **drift detection**:

1. Re-fetch every page listed in the file's ``source_urls`` front
   matter.
2. Hash each page's body and compare against a stored checksum map
   embedded in the front matter (``source_checksums``).
3. If everything matches, just bump ``last_refreshed`` and rewrite
   the front matter — the prose is still accurate.
4. If anything differs, surface a clear diff report to stderr,
   update the checksum map, bump ``last_refreshed``, and exit
   non-zero so the hook surfaces the change. The user is expected
   to manually re-curate the prose for the changed pages.

Source pages: every URL listed under ``source_urls`` in
``.kiro/steering/connect-ai-agents.md`` front matter.

Run:
    uv run python .kiro/hooks/scripts/refresh_connect_ai_agents.py            # write
    uv run python .kiro/hooks/scripts/refresh_connect_ai_agents.py --dry-run  # preview
    uv run python .kiro/hooks/scripts/refresh_connect_ai_agents.py --check    # exit non-zero on drift, don't write
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# Shared HTTP fetcher with 404 self-healing via the connect-knowledge
# docs search. Lives next to this script in scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _doc_fetcher import fetch_with_fallback  # noqa: E402

# This script lives at ``.kiro/hooks/scripts/`` — three levels under the
# repo root (scripts → hooks → .kiro → repo root).
REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = REPO_ROOT / ".kiro" / "steering" / "connect-ai-agents.md"

ADMINGUIDE_ROOT = "https://docs.aws.amazon.com/connect/latest/adminguide"

# Per-page bias for the search resolver when an upstream URL 404s.
# Most pages can fall back to the same generic hint; a few need extra
# context because their slugs collide with non-Connect topics.
DEFAULT_QUERY_HINT = "amazon connect ai agents"
PER_URL_QUERY_HINT: dict[str, str] = {
    "ai-agent-mcp-tools": "amazon connect mcp tools agentcore",
    "ai-agent-security-profile-permissions": "amazon connect security profile ai agent",
    "agentic-self-service": "amazon connect agentic self service orchestrator",
    "agentic-assistance": "amazon connect agentic assistance agent workspace",
    "use-orchestration-ai-agent": "amazon connect orchestration message tags",
    "ai-agent-configure-language-support": "amazon connect ai agent locale language",
    "use-generative-ai-case-summarization": "amazon connect cases generative summarization",
    "ai-generated-note-taking": "amazon connect note taking ai agent",
    "monitor-ai-agents": "amazon connect ai agent cloudwatch logs",
    "ts-ai-agents-self-service": "amazon connect troubleshoot ai agent",
    "integrate-guides-with-ai-agents": "amazon connect step by step guide content association",
    "multiple-knowledge-base-setup-and-content-segmentation": "amazon connect multiple knowledge bases retrieve tool",
    "access-connect-assistant-in-workspace": "amazon connect assistant agent workspace url",
}


# ----- front matter --------------------------------------------------------


FRONT_MATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)


@dataclass
class FrontMatter:
    raw: str  # full ``---\n...\n---\n`` block
    inclusion: str
    last_refreshed: str
    source_urls: list[str]
    source_checksums: dict[str, str]  # url -> "sha256:abcdef…"


def parse_front_matter(text: str) -> FrontMatter:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        raise RuntimeError(
            f"could not find a front matter block at the top of {OUTPUT_PATH}"
        )
    body = m.group("body")
    raw = m.group(0)

    # YAML-lite parser: this file uses a strict, fixed shape so a real
    # YAML dependency would be overkill. Just walk lines and pick out
    # what we need.
    inclusion = ""
    last_refreshed = ""
    source_urls: list[str] = []
    source_checksums: dict[str, str] = {}

    section: str | None = None  # tracks the current list-valued key
    for line in body.splitlines():
        if not line.strip():
            section = None
            continue
        if line.startswith("  - ") and section == "source_urls":
            source_urls.append(line[4:].strip())
            continue
        if line.startswith("  ") and section == "source_checksums":
            # ``  https://…: sha256:abcdef…``. Split on the LAST ``: ``
            # rather than the first ``:`` because the key is a URL and
            # contains its own ``:``s.
            stripped = line[2:]
            sep = stripped.rfind(": ")
            if sep == -1:
                continue
            key = stripped[:sep].strip()
            val = stripped[sep + 2 :].strip()
            if key and val:
                source_checksums[key] = val
            continue
        # Top-level key: value
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if key == "inclusion":
                inclusion = val
                section = None
            elif key == "last_refreshed":
                last_refreshed = val
                section = None
            elif key == "source_urls":
                section = "source_urls"
            elif key == "source_checksums":
                section = "source_checksums"
            else:
                section = None

    if not source_urls:
        raise RuntimeError(
            f"front matter of {OUTPUT_PATH} has no source_urls list"
        )
    return FrontMatter(
        raw=raw,
        inclusion=inclusion or "manual",
        last_refreshed=last_refreshed,
        source_urls=source_urls,
        source_checksums=source_checksums,
    )


def render_front_matter(fm: FrontMatter) -> str:
    """Re-emit the front matter with stable key order and 2-space indent."""
    lines = ["---"]
    lines.append(f"inclusion: {fm.inclusion}")
    lines.append(f"last_refreshed: {fm.last_refreshed}")
    lines.append("source_urls:")
    for url in fm.source_urls:
        lines.append(f"  - {url}")
    lines.append("source_checksums:")
    for url in fm.source_urls:  # iterate in source_urls order, not dict order
        if url in fm.source_checksums:
            lines.append(f"  {url}: {fm.source_checksums[url]}")
    lines.append("---")
    lines.append("")  # trailing blank line before the body
    return "\n".join(lines)


# ----- fetching ------------------------------------------------------------


def md_url_for(html_url: str) -> str:
    """``…/foo.html`` → ``…/foo.md``. AWS docs serve both.

    The .md form skips the rendered chrome and gives us a stable input
    to checksum, so a layout-only change to the docs site doesn't fire
    a drift report.
    """
    if html_url.endswith(".html"):
        return html_url[:-5] + ".md"
    return html_url


def query_hint_for(html_url: str) -> str:
    slug = html_url.rsplit("/", 1)[-1]
    if slug.endswith(".html"):
        slug = slug[:-5]
    return PER_URL_QUERY_HINT.get(slug, DEFAULT_QUERY_HINT)


def normalize_body(body: str) -> str:
    """Strip trailing whitespace per line and collapse blank-line runs.

    The .md form is mostly stable, but AWS occasionally tweaks
    whitespace without changing the content. Normalize before
    checksumming so we don't fire spurious drift alerts.
    """
    lines = [line.rstrip() for line in body.splitlines()]
    out: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        out.append(line)
    return "\n".join(out).strip() + "\n"


def hash_body(body: str) -> str:
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


@dataclass
class FetchResult:
    url: str
    final_url: str
    checksum: str
    moved: bool


def fetch_one(html_url: str) -> FetchResult:
    md_url = md_url_for(html_url)
    final_url, body = fetch_with_fallback(
        md_url, query_hint=query_hint_for(html_url)
    )
    checksum = hash_body(normalize_body(body))
    moved = (
        final_url != md_url
        and final_url != html_url
        and final_url != md_url.replace(".md", ".html")
    )
    return FetchResult(url=html_url, final_url=final_url, checksum=checksum, moved=moved)


# ----- CLI ----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rebuilt front matter to stdout without writing.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Exit non-zero on drift without modifying the steering file. "
            "Useful in CI to surface upstream changes."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"Output path (default: {OUTPUT_PATH.relative_to(REPO_ROOT)}).",
    )
    args = parser.parse_args(argv)

    text = args.output.read_text(encoding="utf-8")
    fm = parse_front_matter(text)
    body = text[len(fm.raw):]

    print(
        f"checking {len(fm.source_urls)} source pages for drift…",
        file=sys.stderr,
    )

    drifted: list[tuple[str, str, str]] = []  # (url, old, new)
    new_pages: list[str] = []
    moved_pages: list[tuple[str, str]] = []  # (old, new)
    fetch_failures: list[tuple[str, str]] = []  # (url, error)

    new_checksums: dict[str, str] = {}
    for url in fm.source_urls:
        try:
            result = fetch_one(url)
        except Exception as exc:  # noqa: BLE001 — keep going, report at end
            print(f"  ERROR fetching {url}: {exc}", file=sys.stderr)
            fetch_failures.append((url, str(exc)))
            # Preserve the existing checksum so we don't lose state on
            # transient failures.
            if url in fm.source_checksums:
                new_checksums[url] = fm.source_checksums[url]
            continue

        new_checksums[url] = result.checksum
        if result.moved:
            moved_pages.append((url, result.final_url))

        old = fm.source_checksums.get(url)
        if old is None:
            new_pages.append(url)
            print(f"  NEW   {url} → {result.checksum}", file=sys.stderr)
        elif old != result.checksum:
            drifted.append((url, old, result.checksum))
            print(
                f"  DRIFT {url}\n        old: {old}\n        new: {result.checksum}",
                file=sys.stderr,
            )
        else:
            print(f"  ok    {url}", file=sys.stderr)

    # Decide outcome
    has_changes = bool(drifted or new_pages or moved_pages)
    if has_changes:
        print("", file=sys.stderr)
        print("Drift detected. The steering prose may be stale for:", file=sys.stderr)
        for url, _old, _new in drifted:
            print(f"  - {url}", file=sys.stderr)
        for url in new_pages:
            print(f"  - {url}  (new page added to source_urls but never checksummed)", file=sys.stderr)
        for old, new in moved_pages:
            print(f"  - {old}  →  moved to {new}", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "Re-read these pages and update the prose in "
            f"{OUTPUT_PATH.relative_to(REPO_ROOT)} where needed, then re-run "
            "this script to refresh the checksums.",
            file=sys.stderr,
        )
    elif fetch_failures:
        print("", file=sys.stderr)
        print(
            f"{len(fetch_failures)} fetch failure(s). Checksums for the "
            "failed pages were left unchanged.",
            file=sys.stderr,
        )
    else:
        print("", file=sys.stderr)
        print("All source pages match. Bumping last_refreshed only.", file=sys.stderr)

    # Build the new front matter — always update last_refreshed, always
    # update checksums (drift or no drift).
    fm.last_refreshed = date.today().isoformat()
    fm.source_checksums = new_checksums

    new_front_matter = render_front_matter(fm)

    if args.check:
        # CI mode: report-only, never write. Exit code = drift presence.
        sys.stdout.write(new_front_matter)
        return 1 if has_changes else 0

    if args.dry_run:
        sys.stdout.write(new_front_matter)
        return 0

    new_text = new_front_matter + body
    args.output.write_text(new_text, encoding="utf-8")
    print(
        f"wrote {args.output.relative_to(REPO_ROOT)} "
        f"({len(fm.source_urls)} sources, {len(drifted)} drifted)",
        file=sys.stderr,
    )

    # Non-zero exit on drift so the hook surfaces it as a failure even
    # though the file was rewritten. Use 0 when only last_refreshed
    # moved.
    if has_changes:
        return 2
    if fetch_failures:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
