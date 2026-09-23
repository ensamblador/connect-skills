# connect-skills

A Kiro workspace for Amazon Connect work. It ships two MCP servers, ten
skills, thirteen steering files, and the refresh scripts that keep the
generated reference catalogs current.

Everything lives under [`.kiro/`](.kiro). Point Kiro at this folder and
the skills and steering load themselves. The two MCP servers need one
config entry each, covered in [Configure mcp.json](#configure-mcpjson).

## Let Kiro do this for you

Fresh clone? Open a Kiro session on this folder and paste the prompt
below. It covers dependencies, the Chromium binary, `mcp.json`, the
cached prompts, and a verification pass. Every step has a manual
equivalent from [Prerequisites](#prerequisites) onward.

````text
Set up this connect-skills workspace end to end. Work from the workspace
root. Report what you verified and what you could not.

1. Record the absolute path of uv from `which uv`. If it is missing,
   stop and point me at
   https://docs.astral.sh/uv/getting-started/installation/

2. Sync both MCP servers:
   uv sync --directory .kiro/connect_knowledge_mcp
   uv sync --directory .kiro/cdk_docs_mcp

3. Install the Playwright Chromium binary, roughly 260 MB, unless a
   chromium-* directory already sits in ~/Library/Caches/ms-playwright
   on macOS or ~/.cache/ms-playwright on Linux:
   uv run --directory .kiro/connect_knowledge_mcp python -m playwright install chromium
   Only get_view_component_doc needs it. The other seven tools work
   without it.

4. Write .kiro/settings/mcp.json by copying .kiro/mcp.example.json and
   replacing its two placeholders, ABSOLUTE_PATH_TO_UV and
   ABSOLUTE_PATH_TO_REPO. Its __setup__ key carries the steps; delete
   that key afterwards. Use the absolute uv path from step 1 and an
   absolute --directory path for each server. Relative paths fail with
   spawn ENOENT. autoApprove the eight connect_knowledge tools and the
   two cdk_docs tools. Check ~/.kiro/settings/mcp.json first and tell me
   if either server name is already taken there. If a permission rule
   blocks writes to .kiro/settings/, print the finished JSON with paths
   resolved and ask me to save it.

5. Tell me to reconnect both servers from the MCP Server view in the
   Kiro feature panel. If a server keeps failing on a path that is not
   in the config, tell me to reload the window.

6. Verify. Three suites should pass, 12 tests, then 41, then 26:
   uv run --project .kiro/connect_knowledge_mcp --with pytest --with hypothesis pytest .kiro/scripts/ -q
   uv run --project .kiro/cdk_docs_mcp --with pytest --with hypothesis pytest .kiro/cdk_docs_mcp/cdk_docs/ -q
   uv run --project .kiro/connect_knowledge_mcp --with pytest python -m pytest .kiro/connect_knowledge_mcp/connect_knowledge/ -q

   Then call four tools and show me the real output:
   - get_block_doc with slug invoke-lambda-function-block
   - get_view_component_doc with slug ui-component-datepicker--with-all,
     which proves Chromium works
   - search_cdk_docs for CfnContactFlow
   - validate_flow_json on flow JSON you deliberately broke, so I can
     see it catch the errors

   Then dry-run one refresh script, which writes nothing:
   uv run --project .kiro/connect_knowledge_mcp python .kiro/scripts/refresh_cdk_docs.py --dry-run

7. Optional, and only with AWS credentials for an account that has a
   Connect AI agents domain. Check whether
   .kiro/skills/connect-ai-agent-author/system-prompts/ already holds 15
   YAML files plus _manifest.json. If it does, skip this step. If not,
   ask me for a region, confirm the domain exists with
   `aws qconnect list-assistants --region <region>`, and run:
   uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py --region <region>
   An empty assistantSummaries means that account has no domain. Say so
   and move on rather than guessing at other regions.

Two flags to never run: refresh_aws_workshops.py --only and
refresh_connect_flow_language.py --skip-descriptions. Both corrupt the
catalog they touch. Never hand-edit a generated steering file either;
the next refresh overwrites it.
````

The same prompt works in Claude Code with step 4 swapped for this, and
with step 5 dropped:

````text
4. Write .mcp.json at the repo root instead of .kiro/settings/mcp.json,
   by running from the repo root:
   claude mcp add connect_knowledge -s project -- "$(which uv)" run --directory "$PWD/.kiro/connect_knowledge_mcp" python connect_knowledge_mcp.py
   claude mcp add cdk_docs -s project -- "$(which uv)" run --directory "$PWD/.kiro/cdk_docs_mcp" python cdk_docs_mcp.py
   Then approve both by adding
   {"enabledMcpjsonServers": ["connect_knowledge", "cdk_docs"]} to
   .claude/settings.json, and confirm with `claude mcp list` that both
   report Connected. Details in README, Configure mcp.json, Claude Code.
````

## Repository layout

```
.kiro/
├── settings/mcp.json          # MCP server config for this workspace
├── connect_knowledge_mcp/     # MCP server: 8 Connect research + validation tools
├── cdk_docs_mcp/              # MCP server: 2 CDK reference tools
├── scripts/                   # refresh scripts for the steering catalogs
├── skills/                    # 10 authoring and research workflows
├── steering/                  # 13 reference catalogs and conventions
└── mcp.example.json           # template for settings/mcp.json, which is gitignored
```

[AGENTS.md](AGENTS.md) at the root carries the commands and boundaries
for coding agents working on this repo. Tools other than Kiro read it.

Each folder carries its own README:
[connect_knowledge_mcp](.kiro/connect_knowledge_mcp/README.md),
[cdk_docs_mcp](.kiro/cdk_docs_mcp/README.md),
[scripts](.kiro/scripts/README.md).

## MCP servers

### connect_knowledge

Eight tools over Amazon Connect documentation and validation. Full
reference in
[.kiro/connect_knowledge_mcp/README.md](.kiro/connect_knowledge_mcp/README.md).

| Tool | Purpose |
|---|---|
| `search_docs` | Canonical answers from `docs.aws.amazon.com` |
| `search_blogs` | Patterns and launches from the AWS blogs |
| `search_repost` | Debugging and community Q&A from `repost.aws` |
| `get_block_doc` | Admin-guide flow-block page as markdown, whole or one section |
| `get_action_doc` | Flow language action page as markdown, whole or one section |
| `get_view_component_doc` | Rendered View Dictionary props table |
| `validate_flow_json` | Structural validation of flow JSON |
| `validate_view_json` | Structural validation of view JSON |

### cdk_docs

Two tools over the AWS CDK for Python reference, scoped to
`aws_cdk.aws_connect`, `aws_cdk.aws_lex`, `aws_cdk.aws_wisdom`, and
`aws_cdk.aws_bedrockagentcore`. Full reference in
[.kiro/cdk_docs_mcp/README.md](.kiro/cdk_docs_mcp/README.md).

| Tool | Purpose |
|---|---|
| `search_cdk_docs` | Find the right construct or property |
| `get_cdk_construct_doc` | Full property list for one construct |

## Skills

Skills load on demand. Kiro activates one when your request matches its
description, or you invoke it directly with `/name`.

| Skill | What it does |
|---|---|
| [`connect-flow-author`](.kiro/skills/connect-flow-author/SKILL.md) | Authors a contact flow through four stages: requirements, Mermaid sketch, Flow language JSON, validation |
| [`connect-view-author`](.kiro/skills/connect-view-author/SKILL.md) | Authors a customer-managed view: requirements, layout outline, view JSON, validation |
| [`connect-ai-agent-author`](.kiro/skills/connect-ai-agent-author/SKILL.md) | Authors an AI agent: requirements, agent shape, prompt YAML and CLI bodies, deploy |
| [`connect-kb-author`](.kiro/skills/connect-kb-author/SKILL.md) | Authors Q in Connect knowledge base entries and a content-segmentation tag plan |
| [`connect-prompt-reviewer`](.kiro/skills/connect-prompt-reviewer/SKILL.md) | Reviews an existing AI prompt against AWS best practices and the cached defaults |
| [`connect-researcher`](.kiro/skills/connect-researcher/SKILL.md) | Triangulates docs, blogs, and re:Post before answering an open-ended question |
| [`connect-iac-cdk-author`](.kiro/skills/connect-iac-cdk-author/SKILL.md) | Writes CDK Python for the Connect deployment chain |
| [`mcp-gateway-author`](.kiro/skills/mcp-gateway-author/SKILL.md) | Exposes an API Gateway REST API as MCP tools through a Bedrock AgentCore gateway |
| [`q-in-connect-bot-deploy`](.kiro/skills/q-in-connect-bot-deploy/SKILL.md) | Deploys a three-locale Lex V2 Q in Connect passthrough bot |
| [`steering-refresher`](.kiro/skills/steering-refresher/SKILL.md) | Refreshes the generated steering catalogs. See [Refreshing the catalogs](#refreshing-the-catalogs) |

## Steering

Steering files carry project reference material. All are
`inclusion: manual` except `concise`, so they load only when you pull
them in with `#name` or a skill consults them. That keeps the large
catalogs out of context until needed.

Generated catalogs, rewritten by [`.kiro/scripts`](.kiro/scripts/README.md):

| File | Contents | Entries |
|---|---|---|
| `#connect-blocks` | Every flow block, with the Voice, Chat, Task, Email matrix | 58 |
| `#connect-flow-language` | Flow language grammar, the Action catalog, and the server-side deploy gaps | 56 |
| `#connect-views` | View Dictionary components, view templates, admin-guide pages | 66 |
| `#cdk-connect` | `aws_cdk.aws_connect` constructs | 37 |
| `#cdk-agentcore` | `aws_cdk.aws_bedrockagentcore` constructs | 26 |
| `#cdk-q-in-connect` | `aws_cdk.aws_wisdom` constructs | 12 |
| `#cdk-lex` | `aws_cdk.aws_lex` constructs | 4 |
| `#aws-workshops` | AWS-published Connect workshops with deep-linked modules | 14 |
| `#connect-ai-agents` | AI agent design, configuration, troubleshooting. Prose, with tracked sources | 20 sources |

Hand-authored files, which no script overwrites:

| File | Contents |
|---|---|
| `#cdk-iac` | CDK Python conventions for Connect IaC |
| `#connect-view-patterns` | Worked Body examples for common view shapes |
| `#troubleshoot-ai-agents` | Playbook for agents that greet then stall |
| `#concise` | Output style. The one file loaded always |

Each generated catalog states its own freshness window in a paragraph
near the top. `#aws-workshops` uses 30 days. The rest use 7.

## Skills and steering in Claude Code

Skills port unchanged. Kiro's `SKILL.md` front matter, `name` plus
`description`, is the format Claude Code expects, and Claude Code follows
symlinks when it scans for skills. One relative symlink exposes all ten:

```
.claude/skills -> ../.kiro/skills
```

`.kiro/skills` stays the single source. Nothing is copied: `.claude/skills`
contains zero files and zero bytes, so editing through either path edits
one inode, and a rename or a `git grep` touches each file once.

The link is versioned, so a fresh clone gets it for free. Git stores a
symlink as a mode `120000` blob whose content is the literal string
`../.kiro/skills`; because that target is relative, it resolves in any
clone directory under any user account.

Recreate it only when a checkout drops it. That happens on Windows
without developer mode or `core.symlinks=true`, where git materializes
the link as a text file holding the target path and Claude Code then
finds no skills:

```bash
ln -s ../.kiro/skills .claude/skills
```

Steering has no direct counterpart, so the three Kiro inclusion modes map
differently:

| Kiro | Claude Code |
|---|---|
| `inclusion: always` | An `@.kiro/steering/name.md` import in [CLAUDE.md](CLAUDE.md). Loaded every session, so reserve it for small files. `#concise` is imported this way. |
| `inclusion: manual`, cited as `#name` | A skill resolves it through the `#name` rule CLAUDE.md states, which retrieves one section or one table row rather than the whole file. Type `@.kiro/steering/<name>.md` yourself only when you want a catalog loaded in full. |
| `inclusion: fileMatch` | No native equivalent. A `PostToolUse` hook on `Edit\|Write` that tests the path and prints a pointer to the catalog is the deterministic version. No catalog here uses this mode. |

Keep the manual ones manual. The thirteen catalogs total 213 KB and
`connect-ai-agents.md` alone is 44 KB, so importing them all into
CLAUDE.md would spend the context window before the first question.

Retrieval is partial by default, which is what keeps the manual mode
usable. The catalogs are tables and `##`-sectioned notes, so
`grep -n '^## ' .kiro/steering/<name>.md` gives the section map and a
second read takes just that section. `Language alignment (CRITICAL)` is
63 lines of `connect-ai-agents.md` rather than all 843. Catalogs with no
headings, `connect-blocks.md` among them, are one table: grep the row.
CLAUDE.md states this rule, so a skill citing `#name` does not need a
wrapper skill to make the catalog reachable.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) on
  PATH. Both MCP servers and every script run through it.
- Python 3.10 or newer. `uv` provisions it if missing.
- AWS credentials and a region, for the two AWS-calling paths only:
  `refresh_system_prompts.py` and the skill deploy scripts. The MCP
  servers and the doc-scraping scripts need neither.

## Install

```bash
uv sync --directory .kiro/connect_knowledge_mcp
uv sync --directory .kiro/cdk_docs_mcp
```

One tool, `get_view_component_doc`, renders Storybook pages in headless
Chromium. Playwright ships as a core dependency, but the browser binary
is a separate one-time download of roughly 260 MB:

```bash
uv run --directory .kiro/connect_knowledge_mcp python -m playwright install chromium
```

Skip it and the other seven tools work fine. That one fails with
`BrowserType.launch: Executable doesn't exist`.

## Configure mcp.json

Two clients, two files. Kiro reads `.kiro/settings/mcp.json`. Claude Code
reads `.mcp.json` at the repo root and adds an approval step on top of
it. Both files are gitignored because both hardcode absolute paths.

### Kiro

Workspace config lives at `.kiro/settings/mcp.json`. User config lives
at `~/.kiro/settings/mcp.json` and applies across workspaces. Configs
merge, with workspace winning.

Use absolute paths for both `command` and `--directory`. MCP servers
launch with an arbitrary working directory, so relative paths fail with
`spawn ENOENT`.

```json
{
  "mcpServers": {
    "connect_knowledge": {
      "command": "/absolute/path/to/uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/connect-skills/.kiro/connect_knowledge_mcp",
        "python",
        "connect_knowledge_mcp.py"
      ],
      "disabled": false,
      "autoApprove": [
        "search_docs",
        "search_blogs",
        "search_repost",
        "get_block_doc",
        "get_action_doc",
        "get_view_component_doc",
        "validate_flow_json",
        "validate_view_json"
      ]
    },
    "cdk_docs": {
      "command": "/absolute/path/to/uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/connect-skills/.kiro/cdk_docs_mcp",
        "python",
        "cdk_docs_mcp.py"
      ],
      "disabled": false,
      "autoApprove": [
        "search_cdk_docs",
        "get_cdk_construct_doc"
      ]
    }
  }
}
```

Find your `uv` path with `which uv`. On macOS with the standard
installer it is `/Users/<you>/.local/bin/uv`.

After saving, reconnect the servers from the MCP Server view in the Kiro
feature panel. If a server keeps failing with a path that is not in your
config, reload the window: Kiro can hold a cached config snapshot.

### Claude Code

Project-scope servers live in `.mcp.json` at the repo root. Claude Code
does not read `.kiro/settings/mcp.json`. Write the file with the CLI,
from the repo root, so the shell resolves both paths at add time:

```bash
claude mcp add connect_knowledge -s project -- "$(which uv)" run --directory "$PWD/.kiro/connect_knowledge_mcp" python connect_knowledge_mcp.py
claude mcp add cdk_docs -s project -- "$(which uv)" run --directory "$PWD/.kiro/cdk_docs_mcp" python cdk_docs_mcp.py
```

That writes the `mcpServers` block below. Hand-authoring it is fine too;
`type` and `env` are optional, and `stdio` is the default transport.

```json
{
  "mcpServers": {
    "connect_knowledge": {
      "type": "stdio",
      "command": "/absolute/path/to/uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/connect-skills/.kiro/connect_knowledge_mcp",
        "python",
        "connect_knowledge_mcp.py"
      ],
      "env": {}
    },
    "cdk_docs": {
      "type": "stdio",
      "command": "/absolute/path/to/uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/connect-skills/.kiro/cdk_docs_mcp",
        "python",
        "cdk_docs_mcp.py"
      ],
      "env": {}
    }
  }
}
```

Unlike Kiro, Claude Code expands `${VAR}` and `${VAR:-default}` inside
`command` and `args`, so `${HOME}/.local/bin/uv` works and survives a
change of username. There is still no workspace-folder variable, and a
relative `--directory` still fails with `spawn ENOENT`.

#### Approve the servers

A `.mcp.json` server is inert until approved, since the file is
repo-supplied and could name any binary. `claude mcp list` shows an
unapproved one as `⏸ Pending approval`. Three ways to clear it:

- Start Claude Code in this folder and answer the one-time prompt. The
  answer is stored per project in `~/.claude.json`.
- Pre-approve by name, which skips the prompt. Put this in
  `.claude/settings.json` to share it with everyone who clones, or in
  `.claude/settings.local.json` to keep it personal. Names only, no
  paths, so either file stays machine-independent:

  ```json
  {
    "enabledMcpjsonServers": ["connect_knowledge", "cdk_docs"]
  }
  ```

- `"enableAllProjectMcpServers": true` in the same file approves whatever
  `.mcp.json` happens to hold, including servers added later. Naming the
  two is narrower and preferred.

`disabledMcpjsonServers` is the inverse list. `claude mcp
reset-project-choices` clears every approval and rejection for this
project, which is how you get the prompt back after rejecting one by
mistake.

#### Auto-approve the tool calls

Kiro's `autoApprove` array has no `.mcp.json` counterpart. Claude Code
gates tool calls through permission rules instead, in
`.claude/settings.json` or `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": ["mcp__connect_knowledge", "mcp__cdk_docs"]
  }
}
```

Both servers only read public AWS documentation over HTTPS and validate
JSON in memory. They take no credentials and write nothing, so allowing
them wholesale carries no more risk than a web fetch. For a narrower
rule, name single tools as `mcp__<server>__<tool>`, for example
`mcp__cdk_docs__search_cdk_docs`.

#### Verify

```bash
claude mcp list
```

Both entries should read `✔ Connected`. In a session, `/mcp` lists the
servers, their approval state, and their tools; it also reconnects one
after you edit its server code. Tools are addressed as
`mcp__connect_knowledge__search_docs` and friends.

`.mcp.json` is gitignored here for the same reason as
`.kiro/settings/mcp.json`: it names one `uv` binary and one checkout.
Recreate it with the two commands above.

### Claude Desktop and Strands

Claude Desktop uses the same `mcpServers` block in
`~/Library/Application Support/Claude/claude_desktop_config.json`.
Strands examples are in each server's README.

## Pull the cached AI system prompts

The `connect-ai-agent-author` and `connect-prompt-reviewer` skills read
the default Amazon Connect AI system prompts as a structural reference.
Those YAML files are AWS-owned content, not published under an
open-source license and not in the public docs, so they are gitignored.
Every user pulls their own copy from their own Connect instance.

You need AWS credentials for an account with a Connect AI agents domain,
and permissions for `qconnect:ListAssistants`,
`qconnect:ListAIPrompts`, and `qconnect:GetAIPrompt`.

```bash
uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py #optional --region us-west-2
```

That writes one YAML per SYSTEM prompt plus `_manifest.json` into
`.kiro/skills/connect-ai-agent-author/system-prompts/`, 15 prompts as of
this writing.

Pass `--region` explicitly. The script falls back to `AWS_REGION` or
`AWS_DEFAULT_REGION`, and it finds no domains when pointed at a region
without one. Use `--domain-id <uuid>` to target a specific assistant;
the default is the first from `ListAssistants`. Add `--dry-run` to list
the prompts without writing.

Read
[NOTICE.md](.kiro/skills/connect-ai-agent-author/system-prompts/NOTICE.md)
before sharing anything you pull. Use inside your organization is
appropriate. Redistribution is not.

## Refreshing the catalogs

The generated steering catalogs go stale as AWS ships changes. The
[`steering-refresher`](.kiro/skills/steering-refresher/SKILL.md) skill
owns refreshing them. It maps a request to the one script that owns each
catalog, runs it, and reports what changed.

Ask in plain language:

```
refresh the workshops
refresh the connect blocks catalog
which catalogs are stale?
preview what a views refresh would change
refresh everything
```

The skill activates on description match. It knows which of the seven
scripts owns each file, which flags each script accepts, and which flags
are unsafe.

To bypass the skill, call a script directly. Six run under the
`connect_knowledge_mcp` project:

```bash
uv run --project .kiro/connect_knowledge_mcp python .kiro/scripts/refresh_connect_blocks.py
```

`refresh_system_prompts.py` runs with `boto3` instead, as shown above.

Four things to know before running one:

- `--dry-run` works on all seven scripts. Prefer it when unsure.
- A refresh that only bumps `last_refreshed` is normal. It means the
  upstream table did not change.
- New upstream entries arrive with a placeholder description and need a
  human one-liner.
- Never hand-edit a generated catalog. The next refresh overwrites it.
  Change the script instead. This is why the flow-language deploy-gaps
  section lives in `refresh_connect_flow_language.py` rather than in the
  steering file, having twice been deleted by a refresh.

Two flags to avoid. `refresh_aws_workshops.py --only` corrupts the other
entries. `refresh_connect_flow_language.py --skip-descriptions` blanks
every description. Details in
[.kiro/scripts/README.md](.kiro/scripts/README.md).

## Tests

```bash
# refresh-script properties, 12 tests, no network
uv run --project .kiro/connect_knowledge_mcp --with pytest --with hypothesis pytest .kiro/scripts/ -q

# cdk_docs server, 41 tests
uv run --project .kiro/cdk_docs_mcp --with pytest --with hypothesis pytest .kiro/cdk_docs_mcp/cdk_docs/ -q

# connect_knowledge server, 26 tests, no network
uv run --project .kiro/connect_knowledge_mcp --with pytest python -m pytest .kiro/connect_knowledge_mcp/connect_knowledge/ -q

# no-secrets scanner, 16 tests
cd .kiro/skills/connect-iac-cdk-author/scripts && python3 -m unittest test_secrets_scan
```

The first two suites are largely property-based through `hypothesis`,
which is why it is passed explicitly. `cdk_docs/test_live_fetch.py` hits
the network and self-skips when offline; every other test parses
fixtures.

Agents working on this repo should read [AGENTS.md](AGENTS.md), which
carries these commands alongside the destructive-flag boundaries.
