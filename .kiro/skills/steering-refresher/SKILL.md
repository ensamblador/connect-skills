---
name: steering-refresher
description: Refresh one, several, or all of the generated steering catalogs in .kiro/steering/ by dispatching to the right refresh script under .kiro/scripts/. Use this skill when the user asks to refresh, regenerate, update, or re-fetch a steering catalog (AWS workshops, CDK construct catalogs, Connect AI agents, Connect blocks, Connect flow language, Connect views, Q in Connect system prompts), asks which catalogs are stale or out of date, or asks to preview what a refresh would change. Also use it when a catalog's own 7-day freshness rule says it should be refreshed before being relied on.
---

# Steering catalog refresher

You dispatch steering-catalog refresh requests to the correct script.
Every generated catalog in `.kiro/steering/` has exactly one script that
owns it. Your job is to map the user's ask to the right script, run it
with the right flags, and report what changed.

This skill replaces the seven per-catalog manual hooks. It does not
introduce new fetch logic — the scripts already own that.

## Prerequisites

- `uv` on PATH. Six of the seven scripts run under the
  `.kiro/connect_knowledge_mcp` project; `refresh_system_prompts.py` is
  the exception (see its row below).
- Run every command from the **repo root**. All paths below are
  relative to it and the scripts resolve their own `REPO_ROOT`.
- `refresh_system_prompts.py` additionally needs **AWS credentials and a
  region** in the environment, because it calls `ListAssistants` /
  Q in Connect APIs via boto3. The other six only need network access to
  `docs.aws.amazon.com`.
- `refresh_connect_views.py --with-props` needs the Playwright Chromium
  binary (`uv run --project .kiro/connect_knowledge_mcp python -m
  playwright install chromium`). Without it, omit `--with-props`.

## Dispatch table

Match the user's ask to a row. Never guess — if the ask is ambiguous
between two rows, ask which catalog they mean.

| Ask mentions | Writes | Script |
|---|---|---|
| workshops, AWS workshops, workshop catalog | `steering/aws-workshops.md` | `refresh_aws_workshops.py` |
| CDK, constructs, `Cfn*`, cdk-connect / cdk-lex / cdk-q-in-connect / cdk-agentcore | those four `steering/cdk-*.md` | `refresh_cdk_docs.py` |
| AI agents, Q in Connect agents, agent docs | `steering/connect-ai-agents.md` | `refresh_connect_ai_agents.py` |
| blocks, contact blocks, flow blocks | `steering/connect-blocks.md` | `refresh_connect_blocks.py` |
| flow language, actions, flow JSON reference | `steering/connect-flow-language.md` | `refresh_connect_flow_language.py` |
| views, View Dictionary, components | `steering/connect-views.md` | `refresh_connect_views.py` |
| system prompts, default prompts, Q in Connect prompts | the system-prompt manifest + files | `refresh_system_prompts.py` |

Two things to hold onto:

- **`cdk-iac.md` is hand-authored prose, not a generated catalog.**
  `refresh_cdk_docs.py` deliberately leaves it alone. If the user asks
  to "refresh cdk-iac", tell them it's hand-maintained and ask what they
  actually want changed.
- **`refresh_cdk_docs.py` refreshes all four CDK catalogs at once.**
  There is no per-catalog flag. If the user only wants `cdk-lex.md`,
  explain that the script regenerates the set, and that in steady state
  the untouched catalogs only get their `last_refreshed` bumped.

## Commands

Six scripts share one invocation shape:

```bash
uv run --project .kiro/connect_knowledge_mcp python .kiro/scripts/<script>.py [flags]
```

`refresh_system_prompts.py` is different — it runs with an ad-hoc boto3
dependency instead of the MCP project:

```bash
uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py [flags]
```

Allow up to **300 seconds** per script; several crawl many pages.

## Flags per script

Only pass flags the script actually defines. They are not uniform.

| Script | Flags |
|---|---|
| `refresh_aws_workshops.py` | `--dry-run`, `--output PATH`, `--only SLUG`, `--list` |
| `refresh_cdk_docs.py` | `--dry-run`, `--steering-dir PATH` |
| `refresh_connect_ai_agents.py` | `--dry-run`, `--check`, `--output PATH` |
| `refresh_connect_blocks.py` | `--dry-run`, `--output PATH` |
| `refresh_connect_flow_language.py` | `--dry-run`, `--output PATH`, `--skip-descriptions` |
| `refresh_connect_views.py` | `--dry-run`, `--output PATH`, `--with-props`, `--no-admin-guide` |
| `refresh_system_prompts.py` | `--dry-run`, `--domain-id UUID`, `--region REGION`, `--output-dir PATH` |

Notable behaviors worth using:

- `--dry-run` exists on **all seven**. Use it whenever the user says
  "preview", "what would change", "check first", or is unsure.
- `--check` (AI agents only) exits non-zero on upstream drift without
  writing. This is the right tool for "did the docs change?".
- `--list` (workshops only) enumerates slugs. Safe, read-only.
- **`--only SLUG` (workshops) is BROKEN — do not use it.** Its help text
  promises it merges the named workshop into the existing entries, but
  in practice it degrades the other 12: real titles are replaced with
  slug-titlecased stubs ("Building Intelligent Customer Service with
  Agentic AI on Amazon Connect" → "Self Service Ai Agents") and every
  module list is dropped (verified 2026-09-10: 242 → 168 lines, 98
  deletions). It then rewrites `content_checksum` to match the damaged
  table, so the corruption looks internally consistent and nothing
  downstream flags it. To refresh a single workshop, run the **full**
  refresh instead — it is idempotent and in steady state only bumps
  `last_refreshed`.
- `--skip-descriptions` (flow language) skips the per-action page crawl.
  Much faster, but leaves the description column blank. Only use it when
  the user explicitly wants speed over completeness, and say so.
- `--with-props` (views) enriches entries with required props via
  Playwright. Slower. Requires the Chromium binary.

## Workflow

1. **Identify the target(s).** Map the ask to one or more dispatch rows.
   "Refresh everything" means all seven.
2. **Decide write vs preview.** Default to writing. Use `--dry-run` when
   the user asks to preview, or when they're clearly exploring.
3. **Check staleness if asked.** Every generated catalog carries
   `last_refreshed` in its front matter. The window is **per catalog** —
   read the "Freshness rule" paragraph in the file itself rather than
   assuming:
   - `aws-workshops.md` → **30 days**
   - all others (`cdk-*.md`, `connect-ai-agents.md`,
     `connect-blocks.md`, `connect-flow-language.md`,
     `connect-views.md`) → **7 days**

   The shared helper `.kiro/scripts/steering_freshness.py`
   implements the 7-day default (`FRESHNESS_MAX_AGE_DAYS = 7`) with an
   exact boundary: a gap of exactly the window is still fresh, one day
   more is stale. To answer "what's stale?", read the `last_refreshed`
   values and compare against today — don't run the scripts just to
   find out.
4. **Run.** One script at a time. They write to the same
   `.kiro/steering/` tree, so do not parallelize them.
5. **Report.** For each script: whether it wrote or was a no-op, which
   files changed, and the new `last_refreshed` / count / checksum if the
   script printed them. A no-diff refresh that only bumps
   `last_refreshed` is normal and expected — say so rather than implying
   nothing happened.

## Interpreting results

The scripts share a write discipline: on every write they update
`last_refreshed`, the relevant count (`block_count`, `construct_count`,
…), and `content_checksum` together. So:

- **Content changed** → count and/or checksum differ from before.
- **Steady state** → same table, only `last_refreshed` moves. This is
  the common case and is not a failure.
- **New upstream entries** → appended with a placeholder description.
  Flag these to the user; they need a human to write the one-liner.
- **Entries vanished upstream** → dropped from the table. Worth
  mentioning, since it can mean AWS renamed or retired something.

## Failure modes

- **A source page 404s.** The fetcher self-heals through AWS docs search.
  If it still fails, the script reports the failing URL and leaves that
  one catalog unchanged while the others still refresh. Report which
  catalog was skipped; don't retry blindly.
- **`refresh_system_prompts.py` fails on credentials or region.** Surface
  it as a credentials/region problem, not a script bug. Ask the user to
  set `AWS_REGION` (or pass `--region`) and confirm credentials. Do not
  print credential values.
- **Playwright executable missing** on `--with-props`. Install the
  Chromium binary, then retry the same command.
- **Non-zero exit from `--check`.** That is the signal, not an error:
  upstream drifted. Tell the user and offer to run the real refresh.
- **Timeout.** These crawl a lot. Raise the timeout and retry once
  before concluding anything is broken.

## Do not

- Do not hand-edit a generated steering catalog to "fix" content. The
  next refresh overwrites it. Change the script or the upstream source.
- Do not run `refresh_aws_workshops.py --only`. See the flags section.
- Do not run `refresh_cdk_docs.py` expecting to touch `cdk-iac.md`.
- Do not run multiple refresh scripts concurrently.
- Do not invent flags. The table above is the complete set per script.
- Do not claim a catalog is fresh or stale without reading its actual
  `last_refreshed` front-matter value.
