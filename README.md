# connect-skills

A small kit for grounded Amazon Connect research and flow authoring.

- **MCP server** (`connect_knowledge`) — six tools today:
  - `search_docs`, `search_blogs`, `search_repost` — multi-source search
  - `get_block_doc`, `get_action_doc` — per-page deep dive (admin guide
    + Flow language reference)
  - `validate_flow_json` — structural validation against the Flow
    language grammar
- **Steering files** — generated catalogs the agent pulls in on demand:
  - `#connect-blocks` — every UI flow block, channel matrix, links
  - `#connect-flow-language` — Flow language grammar + every Action
    type, links to per-action reference pages
- **Kiro skills** — opinionated workflows on top of the above:
  - `connect-researcher` — multi-source research orchestrator
  - `connect-flow-author` — four-stage flow authoring (requirements →
    mermaid → JSON → deploy)
  - `q-in-connect-bot-deploy` — deploy a parameterized Lex V2 bot from
    `lex_skills/` (Q in Connect passthrough template, three locales,
    Nova Sonic v2)

The Python package under `src/connect_knowledge/` is the source of truth
for search logic, page parsing, and validation, and also exposes the
search functions as terminal CLIs.

Background and motivation: see
[`2026-05-22_kiro-claude-code-amazon-connect-dev.md`](./2026-05-22_kiro-claude-code-amazon-connect-dev.md).

## Repository layout

```
connect-skills/
├── README.md
├── pyproject.toml
├── .python-version
├── src/
│   └── connect_knowledge/        # search logic (used by MCP + CLIs)
│       ├── __init__.py
│       ├── docs.py            # aws_search
│       ├── blogs.py           # aws_blog_search
│       ├── repost.py          # aws_repost_search
│       ├── page_doc.py        # get_block_doc, get_action_doc
│       ├── validator.py       # validate_flow_json
│       ├── _action_types.py   # generated: VALID_ACTION_TYPES, ACTION_CATEGORY
│       └── cli.py             # console-script entry points
├── connect_knowledge_mcp/        # MCP server wrapping the search functions
│   ├── README.md
│   ├── pyproject.toml
│   └── connect_knowledge_mcp.py  # FastMCP("connect_knowledge") + 6 @mcp.tool()s
├── lex_skills/                # parameterized Lex V2 templates
│   └── q_in_connect_passthrough/
│       ├── README.md
│       ├── skill.json         # parameter manifest
│       └── template/          # Lex V2 import bundle (en_US, es_US, pt_BR)
├── flows/                     # per-flow design + JSON artifacts (created by connect-flow-author)
│   └── <flow-name>/
│       ├── design.md
│       ├── flow.mmd
│       └── flow.json
├── scripts/
│   ├── refresh_connect_blocks.py         # rebuilds the block-catalog steering file
│   ├── refresh_connect_flow_language.py  # rebuilds the flow-language steering file
│   └── deploy_lex_skill.py               # renders + deploys a lex_skills/ template
└── .kiro/
    ├── steering/
    │   ├── connect-blocks.md          # generated, ~55 UI blocks (use `#connect-blocks`)
    │   └── connect-flow-language.md   # generated, grammar + ~56 actions (use `#connect-flow-language`)
    └── skills/
        ├── connect-researcher/SKILL.md
        ├── connect-flow-author/SKILL.md
        └── q-in-connect-bot-deploy/SKILL.md
```

## Prerequisites

- Python 3.10 or newer
- [`uv`](https://docs.astral.sh/uv/) — `brew install uv` or
  `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Install

From the repository root:

```bash
uv sync                                           # installs the search package
uv sync --directory connect_knowledge_mcp            # installs the MCP server
```

The MCP project depends on the parent package as an editable install,
so any change to `src/connect_knowledge/` flows through without a
reinstall.

## Configure the MCP server in `mcp.json`

Two of the three skills (`connect-researcher` and `connect-flow-author`)
call MCP tools, so the server has to be registered with your MCP
client first.

### Kiro

Workspace-scoped (recommended for this repo): create or edit
`.kiro/settings/mcp.json` in the repo root.

User-scoped (available across every workspace): edit
`~/.kiro/settings/mcp.json`.

Add the `connect_knowledge` entry:

```json
{
  "mcpServers": {
    "connect_knowledge": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/connect-skills/connect_knowledge_mcp",
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
        "validate_flow_json"
      ]
    }
  }
}
```

Replace `/absolute/path/to/connect-skills` with the absolute path on
your machine. Kiro reconnects MCP servers automatically on config save
— no restart needed. You can also reconnect from the MCP Servers view
in the Kiro feature panel.

Verify by typing `@` (or whatever attaches a tool in your client) in
chat — the six `connect_knowledge` tools (`search_docs`,
`search_blogs`, `search_repost`, `get_block_doc`, `get_action_doc`,
`validate_flow_json`) should appear under the server.

### Claude Desktop

Edit
`~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or the equivalent on your OS, with the same shape:

```json
{
  "mcpServers": {
    "connect_knowledge": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/connect-skills/connect_knowledge_mcp",
        "python",
        "connect_knowledge_mcp.py"
      ]
    }
  }
}
```

Restart Claude Desktop after saving.

### Strands

```python
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from strands.tools.mcp import MCPClient

connect_knowledge = MCPClient(
    lambda: stdio_client(StdioServerParameters(
        command="uv",
        args=[
            "run",
            "--directory", "/absolute/path/to/connect-skills/connect_knowledge_mcp",
            "python", "connect_knowledge_mcp.py",
        ],
    ))
)

with connect_knowledge:
    tools = connect_knowledge.list_tools_sync()
    # ... pass tools to your Agent
```

For deeper detail (tool reference, failure modes, MCP inspector),
see [`connect_knowledge_mcp/README.md`](./connect_knowledge_mcp/README.md).

### Ask Kiro to do it for you

In a freshly opened workspace where you want the `connect_knowledge`
server registered, paste this prompt to Kiro:

> Set up the `connect_knowledge` MCP server in this workspace's
> `.kiro/settings/mcp.json`. Resolve the absolute path to the
> `connect_knowledge_mcp/` directory by locating it under this repo
> (search from the workspace root). Use the absolute path to the `uv`
> binary on this machine — find it with `command -v uv`, do not assume
> a fixed location. If `.kiro/settings/mcp.json` already exists, merge
> the new server entry into the existing `mcpServers` object without
> touching other servers; if it does not exist, create the file with
> just this entry. Do not modify `~/.kiro/settings/mcp.json`. The
> entry should set `disabled: false` and auto-approve all six tools:
> `search_docs`, `search_blogs`, `search_repost`, `get_block_doc`,
> `get_action_doc`, `validate_flow_json`. After writing, confirm the
> file path and the server entry shape, and tell me to verify the
> tools appear in the MCP Servers panel.

What this prompt is enforcing, and why:

- **Workspace scope, not user scope.** The server is project-specific
  and uses absolute paths tied to where this repo is checked out, so
  it should not pollute `~/.kiro/settings/mcp.json`.
- **Resolve `uv` dynamically.** `uv` lives at `~/.local/bin/uv` on
  most macOS installs, `~/.cargo/bin/uv` for some, `/opt/homebrew/bin/uv`
  via Homebrew, or just `uv` on `PATH` in containers. `command -v uv`
  picks the right one without guessing.
- **Resolve the MCP project path dynamically.** Don't hardcode a
  username or directory layout — search from the workspace root for
  `connect_knowledge_mcp/connect_knowledge_mcp.py` and use that file's
  parent.
- **Merge, don't overwrite.** Other workspace MCP servers may already
  be configured. Preserve them.
- **Don't touch user-global config.** Workspace setup should never
  modify `~/.kiro/settings/`.
- **Auto-approve all six tools.** The search and per-page tools are
  read-only against public AWS surfaces; the validator is pure
  in-memory. No reason for an approval prompt every call.

## Skills

Three skills live under `.kiro/skills/`. Workspace skills are picked
up automatically when you open this repo in Kiro. To use any skill
globally across every workspace:

```bash
mkdir -p ~/.kiro/skills
cp -R .kiro/skills/<skill-name> ~/.kiro/skills/
```

Use `cp -R`, not symlinks. Kiro has a known
[issue](https://github.com/kirodotdev/Kiro/issues/6401) where symlinks
under `~/.kiro/skills/` are not followed.

In chat, just describe the task — Kiro routes to the right skill
based on the description in each `SKILL.md`'s front matter.

### `connect-researcher`

Multi-source research orchestrator. Plans sub-queries, routes each
to the right MCP tool (`search_docs` / `search_blogs` /
`search_repost`), cross-references, and synthesizes an answer with
citations.

Use when the question benefits from triangulating across docs,
blogs, and community Q&A:

- "How does agentic self-service in Connect actually work end-to-end?"
- "Why does my Lex bot return null from a contact flow — docs and
  community?"
- "What's the current state of outbound campaigns in Connect?"

For single-source lookups (canonical API only, blog only, re:Post
only), call the MCP tool directly without the skill — the skill is
specifically for triangulation.

### `connect-flow-author`

Four-stage workflow for designing and producing Amazon Connect
contact flows: requirements capture → Mermaid sketch → Flow language
JSON → deployment guidance.

Pulls in `#connect-blocks` and `#connect-flow-language` automatically.
Uses `get_block_doc` / `get_action_doc` for per-block and per-action
detail when needed, and validates every JSON deliverable with
`validate_flow_json` before handing it back.

Use when designing or critically reviewing a contact flow — anything
that would otherwise involve hand-writing Flow language JSON. Each
flow's deliverables go in `flows/<flow-name>/`:

- `design.md` — spec + Mermaid diagram + block-to-Action mapping
- `flow.mmd` — standalone Mermaid source
- `flow.json` — validated Flow language JSON

The skill bakes in best practices from
[`bp-contact-flows`](https://docs.aws.amazon.com/connect/latest/adminguide/bp-contact-flows.html)
plus rules for [flow modules](https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-modules.html),
[Nova Sonic Speech-to-Speech](https://docs.aws.amazon.com/connect/latest/adminguide/nova-sonic-speech-to-speech.html),
[agent-initiated flows](https://docs.aws.amazon.com/connect/latest/adminguide/agent-initiated-flows.html),
and the [contact initiation methods](https://docs.aws.amazon.com/connect/latest/adminguide/contact-initiation-methods.html)
matrix.

### `q-in-connect-bot-deploy`

Four-stage workflow for deploying a Lex V2 bot from the
`lex_skills/` template library: gather parameters → dry-run →
deploy → verify.

Uses `scripts/deploy_lex_skill.py` to render the template, upload,
import, build, version, alias, and (optionally) associate with an
Amazon Connect instance.

Use when the user asks to stand up or update a Q in Connect-backed
Lex bot. Not for designing flows (that's `connect-flow-author`) or
authoring custom Lex bots from scratch.

## CLIs (optional, for terminal use)

The same three search functions also ship as console scripts, useful
when you want a quick check from a terminal without an MCP client:

```bash
uv run connect-docs-search   "Amazon Connect StartOutboundVoiceContact"
uv run connect-blog-search   "agentic self service"
uv run connect-repost-search "contact flow Lambda timeout"
```

Add `-v` for retry/backoff logs on stderr. The CLIs and the MCP tools
share the same underlying functions, so output formatting is
identical.

## Steering: the block catalog

`.kiro/steering/connect-blocks.md` is a generated reference table of
every Connect flow block: name, channel support (Voice / Chat / Task /
Email), one-line description, and a link to the block's admin-guide
page. Useful when sketching a flow, picking blocks for a Mermaid
diagram, or generating Flow language JSON.

Activation is `inclusion: manual` — pull it into context with
`#connect-blocks` in chat. That keeps it out of unrelated prompts but
one keystroke away when you need it.

The file is generated by joining two upstream pages:

- [`contact-block-definitions`](https://docs.aws.amazon.com/connect/latest/adminguide/contact-block-definitions.html)
  for names and one-line descriptions
- [`block-support-by-channel`](https://docs.aws.amazon.com/connect/latest/adminguide/block-support-by-channel.html)
  for the channel matrix

### Refresh

```bash
uv run python scripts/refresh_connect_blocks.py            # write
uv run python scripts/refresh_connect_blocks.py --dry-run  # preview
```

The script reads the markdown source of both pages (AWS publishes
markdown alongside HTML), parses the tables, joins on block name, and
rewrites the steering file. The front matter records `last_refreshed`
and a content checksum so you can spot whether anything actually
changed across runs.

Cadence: re-run after Connect launch announcements (re:Invent, major
feature drops). The catalog is stable enough that monthly is plenty
between launches. Diffs in the resulting `connect-blocks.md` are the
audit trail of what changed upstream.

The agent itself enforces freshness: the steering file embeds a rule
to refresh when `last_refreshed` is more than 7 days old, or whenever
the user explicitly asks.

## Steering: the flow language reference

`.kiro/steering/connect-flow-language.md` is the API-side companion to
the block catalog. Two parts: the **grammar** (how every Action is
shaped — Identifier, Type, Parameters, Transitions, the Operators
table, nesting limits, an example Condition) and the **action catalog**
(every Action type, its category, a one-line description, and a link
to its full reference page).

Activation is `inclusion: manual` — pull it into context with
`#connect-flow-language` in chat. Pair with `#connect-blocks` when you
need both the UI block names and the underlying Flow language Action
types side by side.

The file is generated from five upstream pages:

- [`flow-language-actions`](https://docs.aws.amazon.com/connect/latest/APIReference/flow-language-actions.html)
  for the grammar
- [`contact-actions`](https://docs.aws.amazon.com/connect/latest/APIReference/contact-actions.html),
  [`flow-control-actions`](https://docs.aws.amazon.com/connect/latest/APIReference/flow-control-actions.html),
  [`interactions`](https://docs.aws.amazon.com/connect/latest/APIReference/interactions.html),
  [`participant-actions`](https://docs.aws.amazon.com/connect/latest/APIReference/participant-actions.html)
  for the action catalog (one row per action, joined by category)

The script also walks each per-action reference page to extract its
first-paragraph description, so the catalog table has real one-liners
rather than just names. Same `last_refreshed` + 7-day freshness rule
as the block catalog.

### Refresh

```bash
uv run python scripts/refresh_connect_flow_language.py                    # write (crawls per-action pages)
uv run python scripts/refresh_connect_flow_language.py --dry-run          # preview
uv run python scripts/refresh_connect_flow_language.py --skip-descriptions  # quick refresh, blank descriptions
```

The full refresh fetches ~60 pages (5 index pages + 1 per action) with
polite spacing, so it takes around 15 seconds. Use
`--skip-descriptions` when you only need to update the structural
parts (front matter, grammar, action names) without the per-action
crawl.

## Lex skills library

`lex_skills/` is a library of parameterized Lex V2 import bundles.
Today it contains one template:

- **`q_in_connect_passthrough`** — three-locale (`en_US`, `es_US`,
  `pt_BR`) Lex V2 bot using Nova Sonic v2 unified speech, with two
  intents per locale: `AmazonQinConnect` (built on
  `AMAZON.QInConnectIntent`, delegates every utterance to a Q in
  Connect / Wisdom assistant) and the required `FallbackIntent`.

Each template directory has:

- `template/` — Lex V2 import-bundle layout, mirrors what the Lex
  console exports.
- `skill.json` — manifest describing required parameters
  (`{{BOT_NAME}}`, `{{Q_ASSISTANT_ARN}}`) and the alias name.
- `README.md` — template-specific notes and update instructions.

### Deploy

The `q-in-connect-bot-deploy` skill is the recommended path — it
walks the workflow conversationally. For automation or scripted
use, call the deploy script directly:

```bash
# Dry-run: render and zip the bundle, no AWS calls
uv run --with boto3 python scripts/deploy_lex_skill.py \
    --skill q_in_connect_passthrough \
    --bot-name AcmeQPassthroughBot \
    --q-assistant-arn arn:aws:wisdom:us-east-1:111122223333:assistant/<id> \
    --artifact-dir /tmp/acme-render \
    --dry-run

# Real deploy
uv run --with boto3 python scripts/deploy_lex_skill.py \
    --skill q_in_connect_passthrough \
    --bot-name AcmeQPassthroughBot \
    --q-assistant-arn arn:aws:wisdom:us-east-1:111122223333:assistant/<id> \
    --bot-role-arn arn:aws:iam::111122223333:role/AWSServiceRoleForLexV2Bots_acme \
    --region us-east-1 \
    --connect-instance-id <connect-instance-id>
```

The script walks the standard Lex V2 import path
(`CreateUploadUrl` → presigned `PUT` → `StartImport` → poll →
`BuildBotLocale` per locale → `CreateBotVersion` → `CreateBotAlias`)
and optionally calls `connect.associate_bot` to wire the alias into
a Connect instance.

Final `botId`, `botVersion`, and `aliasArn` are printed as JSON on
stdout. See `lex_skills/q_in_connect_passthrough/README.md` for the
template-specific details and the round-trip workflow for editing
the template via the Lex console.

## Future tools

Planned for the MCP server, not implemented yet:

- `search_cdk_docs` — AWS CDK reference scoped to Connect constructs
  (`@aws-cdk/aws-connect`, `@aws-cdk/aws-connectcampaigns`, etc.).
- `search_sdk_docs` — AWS SDK API references (boto3, JS v3, Java v2)
  for `connect`, `connectcases`, `connectparticipant`,
  `customer-profiles`, `voice-id`.

Beyond the search surface, the broader
[`kiro-connect-dev` kit](./2026-05-22_kiro-claude-code-amazon-connect-dev.md#4-what-i-would-build-proposed-kiro-connect-dev-kit)
backlog covers steering files (Connect API surface, contact flow JSON
conventions), generative skills (`/contact-flow-from-spec`,
`/connect-cdk-scaffold`), and hooks (flow JSON schema validation on
save).

## License

Internal — AWS-only sources, intended for partner-SA use.
