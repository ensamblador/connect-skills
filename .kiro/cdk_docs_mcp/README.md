# cdk-docs-mcp

MCP server exposing the AWS CDK for Python reference over stdio. Two
tools: free-text search across the reference, and a per-construct
property dump. Any MCP client can call them.

The server is a thin FastMCP wrapper around the fetch, parse, and search
functions in the [`cdk_docs`](cdk_docs) package in this same folder. It
mirrors the sibling
[`connect_knowledge_mcp`](../connect_knowledge_mcp/README.md) server:
one process, stdio transport, its own `pyproject.toml` and `uv`
environment.

## Construct-library scope

Four in-scope libraries cover Connect IaC work:

| Library | Covers | Paired catalog |
|---|---|---|
| `aws_cdk.aws_connect` | Amazon Connect L1 `Cfn*` constructs | `#cdk-connect`, 37 constructs |
| `aws_cdk.aws_lex` | Amazon Lex constructs | `#cdk-lex`, 4 constructs |
| `aws_cdk.aws_wisdom` | Amazon Q in Connect (Wisdom) constructs | `#cdk-q-in-connect`, 12 constructs |
| `aws_cdk.aws_bedrockagentcore` | Bedrock AgentCore gateway constructs | `#cdk-agentcore`, 26 constructs |

The catalogs in [`.kiro/steering`](../steering) hold the construct lists
with one-line descriptions. Use them to find the right construct name,
then use `get_cdk_construct_doc` here for its properties. The refresh
script `refresh_cdk_docs.py` regenerates all four from the same upstream
pages this server reads.

## Tool reference

### search_cdk_docs

```python
search_cdk_docs(query: str, limit: int = 10) -> str
```

Searches the CDK for Python reference at
`docs.aws.amazon.com/cdk/api/v2/python`. Use it to find the right
construct or property when authoring CDK Python infrastructure.

In:
- `query`, free-text search string.
- `limit`, maximum hits, default 10.

Out: hits separated by `---`, each shaped as

```
Title: <construct or props page title>
URL: <full https URL>
Snippet: <excerpt>
```

Search matches construct names across every CDK module, not only the
four in-scope libraries. A query for `CfnInstance` returns
`aws_connect.CfnInstance` alongside `aws_opsworks.CfnInstance` and
`aws_sso.CfnInstance`. Naming the service in the query improves ranking
but does not filter, so check the module segment in the URL when a
construct name is common.

Snippets are thin on some pages. Props pages in particular often return
a copyright line or a boilerplate import block. That reflects the source
page, not a parse failure. Follow up with `get_cdk_construct_doc`.

### get_cdk_construct_doc

```python
get_cdk_construct_doc(construct: str, library: str | None = None) -> dict[str, Any] | str
```

Fetches and parses one construct reference page. Use it when authoring
or reviewing a construct and you need the canonical property list rather
than a search snippet.

In:
- `construct`, the identifier, for example `CfnInstance`.
- `library`, one of the four in-scope libraries. When `None`, each is
  tried in order until one resolves: `aws_cdk.aws_connect`,
  `aws_cdk.aws_lex`, `aws_cdk.aws_wisdom`,
  `aws_cdk.aws_bedrockagentcore`. Auto-resolution is convenient for
  unambiguous names like `CfnBot`, which lands in `aws_cdk.aws_lex`.
  Pass `library` explicitly for names that exist in several modules.

Out on success: dict with `construct`, `library`, `url`, `properties` as
a list of `{name, type?, required?, description?}`, `description`, and
`raw_sections` as an escape hatch holding `Description`, `Parameters`,
`Attributes`, and `Methods` as raw text.

Out on failure: a descriptive string naming the requested identifier and
the reason per library tried. The docs CDN answers non-existent pages
with `HTTP 403` rather than 404, so a 403 here means no such construct,
not an auth or rate-limit problem.

Two notes on the output. `properties` is the field to rely on; it is
parsed and typed. `raw_sections["Attributes"]` can be very large for
complex constructs, since it flattens every nested property type in the
service model, so reach for it only when you need nested detail such as
the inner fields of `AuthorizerConfigurationProperty`. Unicode in
`raw_sections` arrives mojibaked, with em dashes and curly quotes
rendering as `â`, so treat that text as approximate when quoting.

## Install

From this directory:

```bash
uv sync
```

That installs `mcp[cli]`, `requests`, and `beautifulsoup4`, and builds
the local `cdk_docs` package so edits to the underlying functions take
effect without a reinstall. Python 3.10 or newer. No browser binary is
needed, unlike the `connect_knowledge` server.

## Run

Stdio server, the way MCP clients launch it:

```bash
uv run python cdk_docs_mcp.py
```

Nothing is logged to stdout, since stdio carries MCP frames. For
interactive testing use the inspector:

```bash
uv run mcp dev cdk_docs_mcp.py
```

Two console scripts cover terminal use without an MCP client:

```bash
uv run cdk-docs-search "CfnInstance Amazon Connect"
uv run cdk-construct-doc CfnInstance --library aws_cdk.aws_connect
```

## Tests

```bash
uv run --with pytest --with hypothesis pytest cdk_docs/ -q
```

32 tests. `hypothesis` is needed because `test_parse_fidelity.py` and
`test_mcp_cli_parity.py` are property-based; without it those two error
on collection.

`test_live_fetch.py` hits the network. The rest parse fixtures.
`test_mcp_cli_parity.py` asserts the MCP tools and the console scripts
return the same data, so add new behavior in `cdk_docs/` rather than in
the server file.

## Wire into a client

### Kiro

Workspace config at `.kiro/settings/mcp.json`, user config at
`~/.kiro/settings/mcp.json`. Use absolute paths, since the server is
launched with an arbitrary working directory.

```json
{
  "mcpServers": {
    "cdk_docs": {
      "command": "uv",
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

Claude Desktop uses the same block in
`~/Library/Application Support/Claude/claude_desktop_config.json`.

## Failure modes

- `HTTP 403` from `get_cdk_construct_doc`. The construct does not exist
  in that library. Check spelling, or run `search_cdk_docs` first to
  find the correct module.
- `spawn uv ENOENT` in the client log. The `command` path does not
  resolve. Use the absolute path to `uv`, for example
  `/Users/<you>/.local/bin/uv`, and confirm `--directory` points at this
  folder.
- Thin or boilerplate snippets from `search_cdk_docs`. Expected on props
  and mixin pages. Follow up with `get_cdk_construct_doc`.

## Layout

```
.kiro/cdk_docs_mcp/
├── README.md            # this file
├── .python-version      # 3.11
├── pyproject.toml       # deps, console scripts, builds cdk_docs
├── main.py              # placeholder
├── cdk_docs/            # fetch, parse, search, cli package
│   ├── __init__.py
│   ├── fetch.py
│   ├── search.py        # backs search_cdk_docs
│   ├── construct_doc.py # backs get_cdk_construct_doc
│   ├── cli.py           # console-script entry points
│   └── test_*.py        # 5 test modules
└── cdk_docs_mcp.py      # FastMCP server, two @mcp.tool() functions
```

The fetch, parse, and search logic lives in `cdk_docs/`. This directory
is the MCP adapter plus its package.
