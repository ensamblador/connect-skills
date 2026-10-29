# cdk-docs-mcp

MCP server exposing the Python side of the AWS CDK v2 reference over
stdio. Two
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
| `aws_cdk.aws_connect` | Amazon Connect L1 `Cfn*` constructs | `#cdk-connect`, 39 constructs |
| `aws_cdk.aws_lex` | Amazon Lex constructs | `#cdk-lex`, 4 constructs |
| `aws_cdk.aws_wisdom` | Amazon Q in Connect (Wisdom) constructs | `#cdk-q-in-connect`, 14 constructs |
| `aws_cdk.aws_bedrockagentcore` | Bedrock AgentCore gateway constructs | `#cdk-agentcore`, 27 constructs |

The catalogs in [`.kiro/steering`](../steering) hold the construct lists
with one-line descriptions. Use them to find the right construct name,
then use `get_cdk_construct_doc` here for its properties. The refresh
script `refresh_cdk_docs.py` regenerates all four from the same upstream
pages this server reads.

## Tool reference

### search_cdk_docs

```python
search_cdk_docs(query: str, limit: int = 10,
                module: str | None = None, kind: str | None = None) -> str
```

Searches the CDK v2 reference through the site's own search index, the
one behind the search box on `docs.aws.amazon.com/cdk/api/v2/docs`. It
ranks on page content, so a description finds pages without a construct
name: "agentcore gateway target" returns the AgentCore `GatewayTarget*`
pages. Only stable `aws-cdk-lib` pages are kept. CDK v1, the
`@aws-cdk/*` alpha packages and the mixin pages are dropped.

In:
- `query`, free-text search string.
- `limit`, maximum hits, default 10.
- `module`, optional. Restricts to one CDK module. `aws-connect`,
  `aws_connect` and `aws_cdk.aws_connect` are equivalent.
- `kind`, optional. Restricts to one page kind: `construct`, `struct`,
  `interface`, `enum` or `class`. Property-type pages (`struct`) often
  outrank the construct itself, so pass `construct` when you want
  constructs only.

An unknown `module` or `kind` returns an error naming the closest valid
values, for example `aws-conect` suggests `aws-connect`.

Out: hits separated by `---`, each shaped as

```
Title: CfnContactFlow (L1 construct)
URL: https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnContactFlow.html?lang=python
Snippet: Specifies a flow for an Connect Customer instance.
```

The title carries the page kind in brackets. The snippet is the page's
own text around the match. URLs carry `?lang=python`, so a browser opens
the Python tab rather than TypeScript.

#### How it runs

The site searches a [Pagefind](https://pagefind.app) index in the
browser, and Pagefind has no HTTP search API or Python client. Its search
core is a WASM module the site serves as `wasm.en-us.pagefind`.
`cdk_docs/pagefind.py` loads that module with
[`wasmtime`](https://pypi.org/project/wasmtime/) and makes the same calls
the site's `pagefind.js` makes, so results match the site's search box.

The engine stays loaded in the server process. The first query after
start-up downloads about 500 KB and takes about a second; later queries
fetch only index chunks and result pages not seen before, typically 0.1
to 0.4 seconds. A new index build on the site, which changes the hash in
`pagefind-entry.json`, reloads the engine automatically.

The WASM module cannot do I/O on its own. Python does every fetch, always
under `docs.aws.amazon.com/cdk/api/pagefind/`, and checks every hash the
index returns before putting it into a URL. The code supports Pagefind
1.5.x; an index built by another version falls back rather than risking
wrong results.

If the Pagefind path fails, for example on a network error or a Pagefind
version change, the tool still answers from the AWS docs search index.
The reply then starts with a `Note:` line naming the reason. That index
matches construct names best, ignores `kind`, applies `module` to the
URL, and returns the same site blurb as every snippet.

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

The source page is `aws-cdk-lib.<module>.<Construct>.html?lang=python`.
It renders every language, and the parser reads only the Python variant,
so names are snake_case and types are Python annotations such as
`typing.Union[IResolvable, AttributesProperty]`. The page's markdown twin
holds TypeScript only, which is why the tool parses HTML.

Out on failure: a descriptive string naming the requested identifier and
the reason per library tried. `HTTP 404` means no such construct in that
library. `HTTP 403` comes from CloudFront throttling a burst of requests,
not from a missing page, so wait a minute and retry.

A page without a construct heading and an Initializer section returns
`failed to parse ... no construct heading and Initializer section`
rather than an empty property list. That covers a future AWS layout
change, and it covers nested property types. On the current site a
nested type such as `CfnGateway.AuthorizerConfigurationProperty` has its
own struct page with no Initializer, so this tool rejects it, and the
parent page's `raw_sections["Attributes"]` lists only the parent's own
attributes. Read nested fields from the struct page linked in the
property's `type`.

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
uv run cdk-docs-search "contact flow" --module aws-connect --kind construct
uv run cdk-construct-doc CfnInstance --library aws_cdk.aws_connect
```

## Tests

```bash
uv run --with pytest --with hypothesis pytest cdk_docs/ -q
```

74 tests. `hypothesis` is needed because `test_parse_fidelity.py` and
`test_mcp_cli_parity.py` are property-based; without it those two error
on collection.

`test_live_fetch.py` hits the network, including one real WASM search
per library, and skips when offline. The rest use fixtures and mocks.
`test_pagefind.py` pins the ports of the `pagefind.js` query and excerpt
logic, the hash checks, engine reuse, and the failure paths.
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

- `HTTP 404` from `get_cdk_construct_doc`. The construct does not exist
  in that library. Check spelling, or run `search_cdk_docs` first to
  find the correct module.
- `HTTP 403` from `get_cdk_construct_doc`. CloudFront throttled the
  request. Wait a minute and retry.
- `failed to parse ... no construct heading and Initializer section`.
  The identifier names a nested struct page, or AWS changed the page
  layout again. Check the page in a browser before changing the parser.
- `spawn uv ENOENT` in the client log. The `command` path does not
  resolve. Use the absolute path to `uv`, for example
  `/Users/<you>/.local/bin/uv`, and confirm `--directory` points at this
  folder.
- A `search_cdk_docs` reply that starts with `Note: CDK site search
  unavailable (...)`. The Pagefind path could not run and the reply came
  from the docs index fallback. `GET ... failed` is a network error or a
  moved search index. `the site's Pagefind is version X` means AWS
  upgraded Pagefind past 1.5.x and `cdk_docs/pagefind.py` needs updating.
  `the wasmtime package is not installed` means the server's environment
  is out of date; run `uv sync` in this folder.

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
│   ├── search.py        # backs search_cdk_docs: Pagefind, then docs-index fallback
│   ├── pagefind.py      # the site's Pagefind WASM in wasmtime, kept loaded
│   ├── construct_doc.py # backs get_cdk_construct_doc
│   ├── cli.py           # console-script entry points
│   └── test_*.py        # 7 test modules
└── cdk_docs_mcp.py      # FastMCP server, two @mcp.tool() functions
```

The fetch, parse, and search logic lives in `cdk_docs/`. This directory
is the MCP adapter plus its package.
