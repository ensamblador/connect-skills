# cdk-docs-mcp

MCP server that exposes AWS CDK (Python) reference documentation as tools
any MCP client can call (Kiro, Claude Desktop, Claude Code, Strands, custom
agents).

The server is a thin wrapper around the fetch / parse / search functions in
the [`cdk_docs`](cdk_docs) Python package that ships in this same folder. It
is modeled 1:1 on the sibling [`connect_knowledge_mcp/`](../connect_knowledge_mcp)
server: one process, stdio transport, its own `pyproject.toml` and `uv`
environment.

> **Status: scaffold.** This folder currently contains the package
> structure, `pyproject.toml`, and console-script stubs only. The tools,
> the fetch / parse / search modules, and the FastMCP server file are
> delivered by downstream tasks.

## Construct-library scope

The server serves documentation for the four in-scope CDK construct
libraries relevant to Connect IaC work:

| Library | Reference |
|---|---|
| `aws_cdk.aws_connect` | Amazon Connect constructs (L1 `Cfn*`) |
| `aws_cdk.aws_lex` | Amazon Lex constructs |
| `aws_cdk.aws_wisdom` | Amazon Q in Connect (Wisdom) constructs |
| `aws_cdk.aws_bedrockagentcore` | Bedrock AgentCore gateway constructs |

## Tools (planned)

| Tool | Console script | Purpose |
|---|---|---|
| `search_cdk_docs(query, limit=10)` | `cdk-docs-search` | Free-text search over the CDK reference; returns `Title / URL / Snippet` blocks |
| `get_cdk_construct_doc(construct, library=None)` | `cdk-construct-doc` | Per-construct deep dive; returns parsed `{construct, library, url, properties, raw_sections}` |

## Install

From this directory:

```bash
uv sync
```

That installs `mcp[cli]`, `requests`, and `beautifulsoup4`, and builds the
`cdk_docs` package that lives in this folder, so any changes to the
underlying functions flow through without a reinstall.

## Run

Stdio server (the way MCP clients launch it):

```bash
uv run python cdk_docs_mcp.py
```

The server logs nothing on stdout (stdio is reserved for MCP frames). Use
the MCP inspector for interactive testing:

```bash
uv run mcp dev cdk_docs_mcp.py
```

## Wire into a client

Add to the relevant `mcp.json` (workspace at `.kiro/settings/mcp.json`,
user at `~/.kiro/settings/mcp.json`):

```json
{
  "mcpServers": {
    "cdk_docs": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/connect-skills/cdk_docs_mcp",
        "python",
        "cdk_docs_mcp.py"
      ],
      "disabled": false,
      "autoApprove": ["search_cdk_docs", "get_cdk_construct_doc"]
    }
  }
}
```

## Layout

```
cdk_docs_mcp/
├── README.md              # this file
├── .python-version        # 3.11
├── pyproject.toml         # mcp[cli] + builds the local cdk_docs package
├── main.py                # placeholder (mirrors connect_knowledge_mcp)
├── cdk_docs/              # fetch / parse / search / cli package (source of truth)
│   ├── __init__.py
│   └── cli.py             # console-script entry points
└── cdk_docs_mcp.py        # FastMCP("cdk_docs") server (downstream task)
```

The actual fetch / parse / search logic lives in `cdk_docs/`, shipped
alongside this server. This directory is the MCP adapter plus its package.
