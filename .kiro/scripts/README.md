# .kiro/scripts

Refresh scripts that regenerate the steering catalogs in
[`.kiro/steering`](../steering) from live upstream sources, plus two
shared helpers and three test modules.

Ask Kiro to refresh something and the
[`steering-refresher`](../skills/steering-refresher/SKILL.md) skill
dispatches to the right script here. Run them directly when you want
control over flags.

These were seven manual Kiro hooks until the hooks folder was removed.
The skill replaced them, so this folder holds implementation only.

## Contents

| File | Role |
|---|---|
| `refresh_aws_workshops.py` | Writes `steering/aws-workshops.md` |
| `refresh_cdk_docs.py` | Writes the four `steering/cdk-*.md` catalogs |
| `refresh_connect_ai_agents.py` | Updates `steering/connect-ai-agents.md` front matter |
| `refresh_connect_blocks.py` | Writes `steering/connect-blocks.md` |
| `refresh_connect_flow_language.py` | Writes `steering/connect-flow-language.md` and `_action_types.py` |
| `refresh_connect_views.py` | Writes `steering/connect-views.md` |
| `refresh_system_prompts.py` | Writes the cached AI system prompts |
| `_doc_fetcher.py` | Shared fetch with 404 self-healing through AWS docs search |
| `steering_freshness.py` | The freshness rule, `is_stale(last_refreshed, today)` |
| `refresh_cdk_docs_checksum_test.py` | Checksum integrity properties |
| `refresh_cdk_docs_writediscipline_test.py` | Write-discipline properties |
| `steering_freshness_test.py` | Freshness boundary properties |

## Running them

Six scripts run under the `connect_knowledge_mcp` project, which carries
`requests`, `beautifulsoup4`, and `playwright`:

```bash
uv run --project .kiro/connect_knowledge_mcp python .kiro/scripts/<script>.py [flags]
```

`refresh_system_prompts.py` is the exception. It needs `boto3` and calls
AWS APIs:

```bash
uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py --region <region>
```

Run every command from the repo root. Each script resolves its own
`REPO_ROOT` two levels up from this folder, then writes to absolute
paths under it. Allow up to 300 seconds per script, since several crawl
many pages. Do not run two at once, since they share the steering tree.

`--dry-run` exists on all seven. Use it whenever you want to preview.

## Script reference

### refresh_aws_workshops.py

Writes `steering/aws-workshops.md`, 14 workshops. Workshop Studio
landing pages are JavaScript-rendered, so a plain `requests.get`
returns an empty shell. The script drives headless Chromium through
Playwright, scrapes each landing page for its H1 and sidebar module
links, and merges that with curated one-liners held in the script.

The curated source list is the `CURATED` list of `WorkshopCurated`
entries. To add a workshop, append an entry with `slug`, `landing_url`,
and `one_liner`, then run the script. Title and module list are scraped.
Editing the steering file directly does not survive a refresh.

Flags: `--dry-run`, `--output PATH`, `--list`, `--only SLUG`.

`--list` prints the slugs and exits. Safe.

Do not use `--only`. Its help text promises it merges one workshop into
the existing entries, but it degrades the other 13: real titles are
replaced with slug-titlecased stubs, and every module list is dropped.
Verified 2026-09-10, 242 lines down to 168. It then rewrites
`content_checksum` to match the damaged table, so nothing downstream
flags it. Run the full refresh instead; it is idempotent.

### refresh_cdk_docs.py

Writes four catalogs from the CDK for Python API reference landing
pages:

| Catalog | Source library |
|---|---|
| `cdk-connect.md` | `aws_cdk.aws_connect` |
| `cdk-lex.md` | `aws_cdk.aws_lex` |
| `cdk-q-in-connect.md` | `aws_cdk.aws_wisdom` |
| `cdk-agentcore.md` | `aws_cdk.aws_bedrockagentcore` |

`cdk-iac.md` is hand-authored prose, not a construct list, and the
script leaves it alone.

The script parses each page into the authoritative set of `Cfn*`
constructs, then merges that with the curated one-line descriptions and
ordering already in the catalog. Constructs that vanished upstream are
dropped. New ones are appended with a placeholder description, so an
author notices and writes the one-liner.

There is no per-catalog flag. The script regenerates the set, and in
steady state an unchanged catalog only gets `last_refreshed` bumped.

Write discipline matters here: a catalog whose table did not change is
reported `unchanged` and is not rewritten at all. Fixing prose in the
script's header template does not reach a catalog until its table
changes, so edit those files directly when the prose must change now.

If one source page cannot be fetched, the failing URL is reported and
that catalog is left untouched while the others still refresh.

Flags: `--dry-run`, `--steering-dir PATH`.

### refresh_connect_ai_agents.py

Updates `steering/connect-ai-agents.md`. This file is hand-curated
prose, not a generated table, so the script only tracks its 20 source
pages and rewrites front matter. It never rewrites the body.

On drift it exits non-zero, lists the pages that changed, and tells you
to re-read them and update the prose. Pages newly added to
`source_urls` are reported as never checksummed. Re-running after you
update the prose settles the checksums and returns exit 0.

Flags: `--dry-run`, `--check`, `--output PATH`.

`--check` exits non-zero on drift without writing. Use it in CI to
surface upstream changes.

### refresh_connect_blocks.py

Writes `steering/connect-blocks.md`, 58 blocks. Pulls the markdown
source of two pages, `contact-block-definitions` and
`block-support-by-channel`, joins them on block name, and writes a
denormalized table carrying the channel matrix as `V C T E` flags.

The join is imperfect upstream. Blocks present in the definitions page
but absent from the channel matrix are reported as a note, currently 6
of them, and rendered without channel flags.

Flags: `--dry-run`, `--output PATH`.

### refresh_connect_flow_language.py

Writes two files. `steering/connect-flow-language.md` carries the
grammar plus a 56-action catalog. The generated module
`.kiro/connect_knowledge_mcp/connect_knowledge/_action_types.py` gives
`validate_flow_json` its `VALID_ACTION_TYPES` frozenset, so refreshing
this catalog is what teaches the validator about new Action types.

The script pulls the grammar page plus four action category index pages,
then crawls each action page for its description.

It also emits the hand-authored `DEPLOY_GAPS_SECTION`, which documents
four `CreateContactFlow` 400s that `validate_flow_json` passes. That
section previously lived in the generated steering file, where every
refresh silently deleted it. Add new deploy findings to that constant in
the script, not to the steering file. It is deliberately excluded from
`content_checksum`, so the checksum keeps meaning "the AWS docs
changed".

Flags: `--dry-run`, `--output PATH`, `--skip-descriptions`.

`--skip-descriptions` skips the per-action crawl. Much faster, and every
description becomes `_(no description in source)_`. That degrades the
catalog, so prefer `--dry-run` for a quick check.

### refresh_connect_views.py

Writes `steering/connect-views.md`, 66 entries across the View
Dictionary and the admin guide: AWS-managed views, customer-managed
views, UI components, FormView components, and three admin-guide
groups.

Flags: `--dry-run`, `--output PATH`, `--with-props`, `--no-admin-guide`.

`--with-props` enriches each entry with its required props by rendering
the Storybook page through Playwright. Slower, and it needs the Chromium
binary:

```bash
uv run --project .kiro/connect_knowledge_mcp python -m playwright install chromium
```

`--no-admin-guide` skips the admin-guide index, which is included by
default.

### refresh_system_prompts.py

Writes `.kiro/skills/connect-ai-agent-author/system-prompts/`: one YAML
per SYSTEM AI prompt plus `_manifest.json`, currently 15 prompts.

This is the only script calling AWS rather than reading docs. It needs
valid credentials and a region, and it lists prompts from a Q in Connect
assistant domain. The YAML files are gitignored, since they are
AWS-owned content. Each user pulls their own copy. See
[NOTICE.md](../skills/connect-ai-agent-author/system-prompts/NOTICE.md).

Region matters. The script uses `AWS_REGION` or `AWS_DEFAULT_REGION`
unless you pass `--region`, and it finds no domains when pointed at the
wrong one.

```bash
uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py --region us-west-2
```

Flags: `--dry-run`, `--domain-id UUID`, `--region REGION`,
`--output-dir PATH`.

`--domain-id` targets a specific assistant. The default is the first
domain from `ListAssistants`.

## Shared helpers

### _doc_fetcher.py

Wraps fetching with retry and 404 self-healing: when AWS moves a page,
it re-finds the URL through the AWS docs search. It resolves the
`connect_knowledge` package through candidate paths, preferring the
`.kiro/` copy and falling back to a repo-root checkout.

### steering_freshness.py

Holds the freshness rule as a pure function over two dates, so the
property tests can drive it with no I/O.

```python
is_stale(last_refreshed: date, current_date: date, max_age_days: int = 7) -> bool
```

`FRESHNESS_MAX_AGE_DAYS` is 7. The boundary is exact: a gap of exactly
the window is fresh, one day more is stale.

The window is per catalog, and each catalog states its own rule in its
freshness paragraph. `aws-workshops.md` uses 30 days. Every other
generated catalog uses 7. Read the file rather than assuming.

## Write discipline

Every script updates `last_refreshed`, the relevant count
(`block_count`, `construct_count`, `action_count`, `workshop_count`,
`entry_count`), and `content_checksum` together on each write. So:

- Content changed when the count or checksum differs.
- Steady state means the same table with only `last_refreshed` moving.
  This is the common case and not a failure.
- New upstream entries arrive with a placeholder description and need a
  human one-liner.
- Entries that vanished upstream are dropped, which can mean AWS renamed
  or retired something.

Never hand-edit a generated catalog to fix content. The next refresh
overwrites it. Change the script or the upstream source.

## Tests

```bash
uv run --project .kiro/connect_knowledge_mcp --with pytest --with hypothesis pytest .kiro/scripts/ -q
```

12 tests, all property-based through `hypothesis`, no network. They
cover checksum integrity, write discipline against a mocked fetch, and
the freshness boundary.
