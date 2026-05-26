# connect-knowledge-mcp

MCP server that exposes the `connect_knowledge` Python tools as tools any
MCP client can call (Kiro, Claude Desktop, Claude Code, Strands, custom
agents).

The server is a thin wrapper around the search functions already in
[`../src/connect_knowledge`](../src/connect_knowledge). One process, stdio
transport, three tools today.

## Tools

| Tool | Source / Purpose |
|---|---|
| `search_docs` | `docs.aws.amazon.com` — canonical API / admin-guide answers |
| `search_blogs` | AWS blogs (Contact Center / APN / Messaging) — patterns, walkthroughs, launches |
| `search_repost` | `repost.aws` (Connect-tagged) — debugging, community Q&A, edge cases |
| `get_block_doc` | Parsed admin-guide flow-block reference page (channels, properties, etc.) |
| `get_action_doc` | Parsed Flow language action reference page (parameter object, errors, etc.) |
| `validate_flow_json` | Structural validation of Flow language JSON against the grammar |

### Future tools

Stubbed for follow-up work, not implemented yet:

- `search_cdk_docs` — AWS CDK reference, scoped to Connect constructs
  (`@aws-cdk/aws-connect`, `@aws-cdk/aws-connectcampaigns`, etc.).
- `search_sdk_docs` — AWS SDK API references (boto3, JS v3, Java v2)
  for `connect`, `connectcases`, `connectparticipant`,
  `customer-profiles`, `voice-id`.

## Install

From this directory:

```bash
uv sync
```

That installs `mcp[cli]` plus the parent `connect-knowledge` package as an
editable dependency, so any changes to the underlying search functions
flow through without a reinstall.

## Run

Stdio server (the way MCP clients launch it):

```bash
uv run python connect_knowledge_mcp.py
```

The server logs nothing on stdout (stdio is reserved for MCP frames).
Use the MCP inspector for interactive testing:

```bash
uv run mcp dev connect_knowledge_mcp.py
```

## Wire into a client

### Kiro / Claude Desktop / Claude Code

Add to the relevant `mcp.json` (workspace at
`.kiro/settings/mcp.json`, user at `~/.kiro/settings/mcp.json`, or
`~/Library/Application Support/Claude/claude_desktop_config.json` for
Claude Desktop):

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
      "autoApprove": ["search_docs", "search_blogs", "search_repost"]
    }
  }
}
```

After saving, the client will pick up the server and expose
`search_docs`, `search_blogs`, and `search_repost` as callable tools.

### Strands

```python
from mcp import StdioServerParameters
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

## Tool reference

### `search_docs(query: str, limit: int = 10) -> str`

Searches `docs.aws.amazon.com`. Returns up to `limit` hits formatted as:

```
Title: <doc page title>
URL: <full https URL>
Snippet: <summary or excerpt>
---
```

### `search_blogs(query: str, blogs: list[str] | None = None, all_blogs: bool = False) -> str`

Searches AWS blogs. Defaults to the Connect-tuned set:
`AWS Contact Center`, `AWS Partner Network (APN) Blog`,
`AWS Messaging Blog`. Pass `blogs=["AWS Machine Learning Blog"]` to
override, or `all_blogs=True` to drop the filter entirely.

### `search_repost(query: str, tag_ids: list[str] | None = None, no_tag: bool = False, include_unanswered: bool = False) -> str`

Searches `repost.aws` across `questions`, `articles`, and
`knowledge-center`. Defaults to the Amazon Connect tag
(`TAC0wz6wJtRbuJVD4X7tUmWA`) and answered questions only. Set
`no_tag=True` to widen, `include_unanswered=True` to surface unresolved
threads.

## Failure modes

- 4xx / 5xx from any source → the underlying tool retries with
  exponential backoff. After exhaustion, the tool returns a string
  starting with `Error after N retries:` rather than raising. MCP
  clients see a normal tool result with the error message inside.
- Empty results → returns `No AWS <source> results found for: <query>`.
  Treat this as a signal to broaden the query, not a bug.
- re:Post WAF blocks → re:Post has historically blocked Lambda traffic.
  Running locally with the browser-shaped User-Agent already set in
  `connect_knowledge.repost` generally works, but watch for tightening.

## Layout

```
connect_knowledge_mcp/
├── README.md              # this file
├── .python-version        # 3.11
├── pyproject.toml         # mcp[cli] + editable parent
├── main.py                # placeholder (mirrors reference repo)
└── connect_knowledge_mcp.py  # FastMCP server, three @mcp.tool()s
```

The actual search logic lives in `../src/connect_knowledge/`. This
directory is the MCP adapter only.
