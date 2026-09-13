# AGENTS.md

Operating manual for coding agents working **on** this repository.

This repo is a Kiro workspace whose product is agent configuration: two
MCP servers, ten skills, thirteen steering catalogs, and the refresh
scripts that regenerate them. Human-facing setup lives in
[README.md](README.md). This file carries the commands and boundaries.

Distinguish the two jobs before you start:

- Working **on** the repo means editing MCP server code, skills,
  steering, or scripts. This file governs that.
- Working **with** the repo means using its skills for Amazon Connect
  work. The `.kiro/skills/*/SKILL.md` files govern that.

## Never do these

Ordered by damage. The first two have already cost this repo a git
history rewrite.

1. **Never commit
   `.kiro/skills/connect-ai-agent-author/system-prompts/*.yaml` or
   `_manifest.json`.** AWS-owned content, not under an open-source
   license and absent from the public docs. Gitignored on purpose. Each
   user pulls their own copy. See
   [NOTICE.md](.kiro/skills/connect-ai-agent-author/system-prompts/NOTICE.md).
2. **Never commit `.kiro/settings/mcp.json`.** It holds absolute paths
   naming one machine and one user account. Gitignored. The versioned
   template is [`.kiro/mcp.example.json`](.kiro/mcp.example.json).
3. **Never run `refresh_aws_workshops.py --only`.** Its help text
   promises a merge. It degrades the other 13 workshops, replacing real
   titles with slug stubs and dropping every module list, then rewrites
   `content_checksum` so nothing downstream notices. Run the full
   refresh; it is idempotent.
4. **Never run `refresh_connect_flow_language.py --skip-descriptions`.**
   Blanks all 56 action descriptions. Use `--dry-run` for a quick check.
5. **Never hand-edit a generated steering catalog.** The next refresh
   overwrites it. Change the script that owns it. The flow-language
   deploy-gaps section lives in `refresh_connect_flow_language.py` for
   exactly this reason, having twice been deleted by a refresh.
6. **Never run two refresh scripts concurrently.** They share the
   `.kiro/steering/` tree.
7. **Never put real identifiers in code, docs, or fixtures.** Use
   account `111122223333`, NANP `555` numbers such as `+12065550101`,
   Ofcom's drama range `07700 900000` to `07700 900999` for UK numbers,
   and `example.com` addresses.
8. **Never call a deploy script without `--dry-run`** unless the user
   asked for a deploy in that turn. `deploy_connect_view.py` and
   `deploy_lex_skill.py` create real AWS resources.

## Ask first

- Adding a dependency to either `pyproject.toml`.
- Changing an MCP tool's return shape. Callers include
  `connect_knowledge_mcp.py`, the `SKILL.md` files, and both server
  READMEs.
- Any `git push`, and any history rewrite.
- Running a refresh script without `--dry-run`, which rewrites steering.

## Commands

Every command runs from the repo root. `uv` is required on PATH; both
servers and all scripts run through it.

### Install

```bash
uv sync --directory .kiro/connect_knowledge_mcp
uv sync --directory .kiro/cdk_docs_mcp
# Only get_view_component_doc needs Chromium, a one-time ~260 MB download
uv run --directory .kiro/connect_knowledge_mcp python -m playwright install chromium
```

### Test

Run all four before finishing any task that touches Python. Expected
counts as of the last run:

```bash
# cdk_docs server, 41 tests (test_live_fetch.py hits the network, self-skips offline)
uv run --project .kiro/cdk_docs_mcp --with pytest --with hypothesis pytest .kiro/cdk_docs_mcp/cdk_docs/ -q

# connect_knowledge server, 26 tests, offline
uv run --project .kiro/connect_knowledge_mcp --with pytest python -m pytest .kiro/connect_knowledge_mcp/connect_knowledge/ -q

# refresh-script properties, 12 tests, offline
uv run --project .kiro/connect_knowledge_mcp --with pytest --with hypothesis pytest .kiro/scripts/ -q

# no-secrets scanner, 16 tests
cd .kiro/skills/connect-iac-cdk-author/scripts && python3 -m unittest test_secrets_scan
```

`pytest` and `hypothesis` are passed with `--with` because neither is a
declared dependency. Most tests are property-based, so `hypothesis` is
required wherever it appears above.

### Secrets gate

Run before any commit. Exit 1 means findings.

```bash
python3 .kiro/skills/connect-iac-cdk-author/scripts/secrets_scan.py .
```

Nine findings are expected and correct, all inside
`connect-iac-cdk-author/scripts/`: one in `secrets_scan.py`'s own
docstring, eight in `test_secrets_scan.py`'s fixtures. Those fixtures use
AWS's published `EXAMPLE`-suffixed placeholder credentials. A finding in
any other file is a real leak.

Do not paste those placeholder values into new files. Writing them here
verbatim made this document the tenth finding, which is how this note
came to exist. `test_secrets_scan.py` splits its own literals across a
concatenation for the same reason.

### Refresh a steering catalog

Six scripts run under the `connect_knowledge_mcp` project. Always
`--dry-run` first. Allow up to 300 seconds each; several crawl many
pages.

```bash
uv run --project .kiro/connect_knowledge_mcp python .kiro/scripts/<script>.py --dry-run
```

`refresh_system_prompts.py` is the exception and needs `boto3` plus AWS
credentials:

```bash
uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py --dry-run --region <region>
```

## Project structure

```
.kiro/
├── connect_knowledge_mcp/   # MCP server, 8 Connect doc + validation tools
│   └── connect_knowledge/   # package: docs, blogs, repost, page_doc, validators
├── cdk_docs_mcp/            # MCP server, 2 CDK reference tools
│   └── cdk_docs/            # package: fetch, search, construct_doc
├── scripts/                 # 7 refresh scripts + 2 shared helpers + 3 test modules
├── skills/                  # 10 SKILL.md workflows, some with scripts/ and reference/
├── steering/                # 13 catalogs: 9 generated, 4 hand-authored
├── settings/mcp.json        # gitignored, machine-local
└── mcp.example.json         # versioned template for the above
```

Stack: Python 3.11 pinned via `.python-version` in both servers, `uv` for
every invocation, FastMCP through `mcp[cli]>=1.14`, `requests`,
`beautifulsoup4`, `playwright>=1.46`, and `boto3` as an optional extra
used only by deploy scripts and `refresh_system_prompts.py`.

No linter or formatter is configured. No `[tool.pytest.ini_options]`
either; pytest is invoked with explicit paths.

## Conventions

### Generated versus hand-authored steering

Nine catalogs are script-owned: `connect-blocks`, `connect-flow-language`,
`connect-views`, the four `cdk-*` construct lists, `aws-workshops`, and
`connect-ai-agents`. Four are hand-authored and no script touches them:
`cdk-iac`, `connect-view-patterns`, `troubleshoot-ai-agents`, `concise`.

Every generated file carries `last_refreshed`, a count, and a
`content_checksum` in front matter, updated together on write. A refresh
that only bumps `last_refreshed` means the upstream table did not change.
That is the steady state, not a failure.

The four hand-authored files also carry `last_refreshed` but have no
refresh script, so freshness tooling flags them permanently. Known and
accepted.

### Test file naming

Two conventions, both live. Match the directory you are in.

- MCP server packages use a `test_` prefix:
  `connect_knowledge/test_page_doc.py`.
- `.kiro/scripts/` uses a `_test` suffix:
  `steering_freshness_test.py`.

### Docstrings

Google style, with `Args:` and `Returns:`. Module docstrings explain the
design decision, not the mechanics. When you fix a non-obvious bug,
record the cause in the docstring so the next reader does not re-litigate
it. `cdk_docs/fetch.py:decoded_text` is the model: it explains that AWS
serves bare `text/html`, that `requests` then defaults to ISO-8859-1, and
what that does to a UTF-8 en dash.

### Parse only when there is no markdown source

`get_block_doc` and `get_action_doc` return AWS's own `.md` verbatim with
relative links absolutised, plus a `sections` list and an optional
`section` filter. They do not map headings onto fixed fields. An earlier
version did, and AWS's rename of `Supported channels` to `Contact types`
silently emptied three keys on 10 of 58 block pages.

`get_cdk_construct_doc` and `get_view_component_doc` do parse, correctly:
their sources are Sphinx HTML and a JavaScript-rendered Storybook page,
so there is no markdown to forward.

Apply the same rule to new tools. Forward the source when one exists.
When you must parse, report a miss rather than returning an empty value
that reads like a real one.

### Git

Conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`,
with an optional scope such as `fix(repost):`. One subject line under 70
characters; use a bulleted body for unrelated changes. Work on `main`.

## Gotchas that cost real time

- MCP servers are long-running. Editing server code does not take effect
  until the user reconnects them from the MCP Server view. Verify changes
  against the library directly, then tell the user to reconnect.
- A `1` reference count inside a file does not mean dead code. Deleting
  `_parse_lead_paragraph` from `page_doc.py` broke
  `.kiro/scripts/refresh_connect_views.py`, which imports it lazily
  inside a function. Grep the whole repo before deleting anything.
- `refresh_system_prompts.py` exits 1 with "no domains found" when the
  region has no Q in Connect assistant. That is correct behaviour, not a
  bug. Confirm with
  `aws qconnect list-assistants --region <region>`.
- Absolute paths are mandatory in `mcp.json`. Kiro expands neither `~`
  nor `${workspaceFolder}` in `command` or `args`; relative paths fail
  with `spawn ENOENT`.
