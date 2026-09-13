# connect-knowledge-mcp

MCP server exposing eight Amazon Connect research and validation tools
over stdio. Any MCP client can call them: Kiro, Claude Desktop, Claude
Code, Strands, custom agents.

The server is a thin FastMCP wrapper around the
[`connect_knowledge`](connect_knowledge) package in this same folder.
That package holds the search, parse, and validation logic. This
directory is the MCP adapter.

## Tools at a glance

| Tool | Returns | Backing source |
|---|---|---|
| `search_docs` | `str` | `docs.aws.amazon.com` |
| `search_blogs` | `str` | AWS blogs (Contact Center, APN, Messaging) |
| `search_repost` | `str` | `repost.aws`, Connect-tagged |
| `get_block_doc` | `dict` | Admin-guide flow-block page |
| `get_action_doc` | `dict` | Flow language action reference page |
| `get_view_component_doc` | `dict` | View Dictionary Storybook page, Playwright-rendered |
| `validate_flow_json` | `dict` | Local, no network |
| `validate_view_json` | `dict` | Local, no network |

Three tools return formatted strings, five return structured dicts.
The search tools never raise on a failed fetch. They return the error
as a string, so an MCP client sees a normal tool result.

## Tool reference

### search_docs

```python
search_docs(query: str, limit: int = 10) -> str
```

Searches the official AWS documentation index. Use it for canonical
answers: API reference, admin guide chapters, flow block reference,
service quotas, supported regions, IAM actions.

In:
- `query`, free-text search string.
- `limit`, maximum hits, default 10. Raise to 15 or 20 when the first
  page is noisy.

Out: hits separated by `---`, each shaped as

```
Title: <page title>
URL: <full https URL>
Snippet: <summary or excerpt>
```

URLs are full https links, suitable for inline citation.

### search_blogs

```python
search_blogs(query: str, blogs: list[str] | None = None, all_blogs: bool = False) -> str
```

Searches AWS blogs through the public CloudSearch endpoint. Use it for
implementation patterns, walkthroughs, launches, and partner content.

In:
- `query`, free-text search string.
- `blogs`, optional list of blog display names. When `None` and
  `all_blogs` is `False`, the Connect-tuned default set applies:
  `AWS Contact Center`, `AWS Partner Network (APN) Blog`,
  `AWS Messaging Blog`. Pass an explicit list to redirect, for example
  `["AWS Machine Learning Blog"]`.
- `all_blogs`, when `True` searches every AWS blog and overrides
  `blogs`. Use it as a fallback when the default set returns nothing.

Out: same `Title / URL / Snippet` block format as `search_docs`.

### search_repost

```python
search_repost(query: str, tag_ids: list[str] | None = None,
              no_tag: bool = False, include_unanswered: bool = False) -> str
```

Searches AWS re:Post. Use it for debugging specific errors, finding
community-validated workarounds, and real customer Q&A.

In:
- `query`, free-text search string.
- `tag_ids`, optional list of re:Post tag IDs. Defaults to the Amazon
  Connect tag `TAC0wz6wJtRbuJVD4X7tUmWA`.
- `no_tag`, when `True` drops tag filtering and searches all of
  re:Post. Widens a search that returned nothing.
- `include_unanswered`, when `True` includes unanswered questions.
  Defaults to `False`, answered only. Turn it on for "is anyone else
  hitting this" signal even without a confirmed fix.

Out: sections grouped under `Questions`, `Articles`, and
`Knowledge Center`.

### get_block_doc

```python
get_block_doc(slug: str, section: str | None = None) -> dict[str, Any]
```

Fetches an admin-guide flow-block page as markdown. Use it when the
one-line entry in the `connect-blocks` steering catalog is not enough.
Pair it with `get_action_doc` when you also need the flow JSON shape.

In: `slug`, the URL stem under `/connect/latest/adminguide/`, without
extension. Examples: `invoke-lambda-function-block`,
`get-customer-input`, `customer-profiles-block`. The
`connect-blocks` catalog links carry the slug. Optionally `section`, a
`##` heading to return on its own.

Out: dict with `slug`, `name`, `title`, `url`, `sections` listing every
`##` heading on the page in order, `section` naming which one was
returned or `None` for the whole page, and `markdown` carrying the
content with relative cross-links rewritten to absolute URLs. A
`section` that matches nothing yields an empty `markdown` plus an
`error` listing the real headings.

### get_action_doc

```python
get_action_doc(slug: str, section: str | None = None) -> dict[str, Any]
```

Fetches a Flow language action reference page as markdown. Use it when
generating, validating, or debugging flow JSON. The
`connect-flow-language` catalog one-liners are not sufficient for
writing JSON on their own.

In: `slug`, the URL stem under `/connect/latest/devguide/`. Examples:
`interactions-invokelambdafunction`, `contact-actions-tagcontact`,
`flow-control-actions-loop`. Pass `section="Parameter object"` for just
the Parameters schema, which is the usual need when writing flow JSON.

Out: same shape as `get_block_doc`.

### Why these two return markdown

Both pages are published by AWS as `.md` alongside `.html`, and the
consumer is a model that reads markdown natively, so there is little to
gain from pre-digesting them into fixed fields.

There was a cost, though. An earlier version mapped `##` headings onto
named keys, and AWS is migrating these pages to new wording:
`Supported channels` became `Contact types`, `Properties` became
`How to configure this block`, and the flow-type bullet list became a
table. That silently emptied `channels`, `flow_types`, and `properties`
on 10 of the 58 catalogued blocks, including `play`,
`get-customer-input`, `transfer-to-queue`, and `show-view-block`. The
content was sitting in the page the whole time, and an empty value was
indistinguishable from a legitimately empty one.

It did not even save tokens. Because the old shape returned
`raw_sections` (the whole document) *plus* named slices of it, the
payload ran 1.0x to 1.6x the size of the raw markdown.

Splitting on `##` hardcodes no heading names, so it cannot drift. The
`section` argument covers the one thing the field mapping was good for,
returning a slice: `Contact types` on `get-customer-input` is 267
characters against 31,000 for the whole page.

The other two doc tools still parse, and should. `get_cdk_construct_doc`
reads Sphinx HTML and `get_view_component_doc` reads a JavaScript-
rendered Storybook page, so neither has a markdown source to forward.

### get_view_component_doc

```python
get_view_component_doc(slug: str, capture_html: bool = False) -> dict[str, Any]
```

Renders a View Dictionary component docs page in headless Chromium and
extracts a structured props table. Use it when authoring a
customer-managed view, wiring a Show view block, or building a Form.

In:
- `slug`, the Storybook story id, the part after `?path=/docs/`.
  Examples: `ui-component-datepicker--with-all`,
  `formview-component-datepicker--with-all`,
  `ui-component-attributebar--with-attributes`. The `connect-views`
  catalog links carry the slug.
- `capture_html`, when `True` also returns the rendered `#docs-root`
  subtree as `docs_html`. Off by default because the payload is large:
  Storybook wrapper markup, inline SVGs, Prism-tokenized spans, and the
  component JSON schema. Turn it on when you need the example View
  Template definition or the nested schema for a composite prop type,
  neither of which the props table carries.

Out: dict with `slug`, `url`, `title`, `description`, `props` as a list
of `{name, required, description, type_summary, default_summary}`,
`required_props` and `optional_props` as name lists, and `docs_html`
which is `null` unless `capture_html` is set.

This is the one tool needing the Chromium binary. See Install.

### validate_flow_json

```python
validate_flow_json(json_str: str) -> dict[str, Any]
```

Validates Flow language JSON structure locally, no network.

Checks the top-level shape (`Version`, `StartAction`, `Actions`),
per-Action required fields, `Identifier` length and forbidden
characters and uniqueness, `Type` against the known catalog,
`Transitions` shape, `Operator` against the closed set, `Condition`
nesting limits, and `NextAction` reference resolution. Unreachable
Actions come back as warnings.

In: `json_str`, the flow JSON as a string. The runtime needs real
JSON. The docs example uses `//` comments for narration, so strip
those first.

Out: dict with `valid` as bool, `error_count`, `warning_count`,
`issues` as a list of `{severity, path, message}`, `summary` string,
and `action_categories` mapping Identifier to category name.

Two limits worth knowing. Per-Action `Parameters` schemas are not
validated here, so use `get_action_doc` for the canonical shape. And
the checks are looser than the `CreateContactFlow` server schema: a
`{"valid": true}` result is necessary but not sufficient. Read the
"Server-side deploy gaps" section of `#connect-flow-language` before
deploying.

### validate_view_json

```python
validate_view_json(json_str: str) -> dict[str, Any]
```

Validates a customer-managed view `Content` payload locally, the body
of `CreateView` and `UpdateView`.

Checks the top-level shape (`Template`, `Actions`), `Template.Head`
and `Template.Body` shape, per-component required fields (`_id`,
`Type`, `Props`), `_id` uniqueness across the view, `Type` against the
known catalog, `Content` shape, required props per Type, and
cross-checks between component `Props.Action` references and the
top-level `Actions` list.

In: `json_str`, the view `Content` JSON as a string. Strip `//`
comments first.

Out: dict with `valid`, `error_count`, `warning_count`, `issues`,
`summary`, and `component_hierarchies` mapping `_id` to the View
Dictionary hierarchies the Type is documented under. That last field
helps sanity-check FormView components.

Only required prop names are checked, not full Props schemas. Use
`get_view_component_doc` for the canonical per-component shape.

## Install

From this directory:

```bash
uv sync
```

That installs `mcp[cli]`, `requests`, `beautifulsoup4`, and
`playwright`, all core dependencies, and builds the local
`connect_knowledge` package so edits to the search functions take
effect without a reinstall. Python 3.10 or newer.

`get_view_component_doc` also needs the Chromium binary Playwright
drives, a separate one-time download of roughly 260 MB:

```bash
uv run python -m playwright install chromium
```

Skipping it leaves the other seven tools fully working.
`get_view_component_doc` fails with
`BrowserType.launch: Executable doesn't exist`.

`boto3` is an optional extra, used by the skill deploy scripts rather
than the server:

```bash
uv sync --extra deploy
```

## Run

Stdio server, the way MCP clients launch it:

```bash
uv run python connect_knowledge_mcp.py
```

Nothing is logged to stdout, since stdio carries MCP frames. For
interactive testing use the inspector:

```bash
uv run mcp dev connect_knowledge_mcp.py
```

Three console scripts cover terminal use without an MCP client:

```bash
uv run connect-docs-search "contact flow blocks"
uv run connect-blog-search "agentic self-service"
uv run connect-repost-search "lex bot returns null"
```

If one fails with `Failed to spawn`, the venv predates the script
entries in `pyproject.toml`. `uv sync` reports the project as audited
and does not re-add them. Force it:

```bash
uv sync --reinstall-package connect-knowledge-mcp
```

## Wire into a client

### Kiro

Workspace config at `.kiro/settings/mcp.json`, user config at
`~/.kiro/settings/mcp.json`. Use absolute paths, since the server is
launched with an arbitrary working directory.

```json
{
  "mcpServers": {
    "connect_knowledge": {
      "command": "uv",
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
    }
  }
}
```

Claude Desktop uses the same block in
`~/Library/Application Support/Claude/claude_desktop_config.json`.

### Strands

```python
from mcp import StdioServerParameters, stdio_client
from strands.tools.mcp import MCPClient

connect_knowledge = MCPClient(
    lambda: stdio_client(StdioServerParameters(
        command="uv",
        args=[
            "run",
            "--directory",
            "/absolute/path/to/connect-skills/.kiro/connect_knowledge_mcp",
            "python",
            "connect_knowledge_mcp.py",
        ],
    ))
)

with connect_knowledge:
    tools = connect_knowledge.list_tools_sync()
    # pass tools to your Agent
```

## Failure modes

- 4xx or 5xx from any source. The underlying tool retries with
  exponential backoff, then returns a string starting with
  `Error after N retries:` instead of raising.
- Empty results. Returns `No AWS <source> results found for: <query>`.
  Broaden the query rather than treating it as a bug.
- `spawn uv ENOENT` in the client log. The `command` path does not
  resolve. Use the absolute path to `uv`, for example
  `/Users/<you>/.local/bin/uv`, and confirm the `--directory` argument
  points at this folder.
- Playwright executable missing. Run the `playwright install chromium`
  step above, then retry the same call.
- re:Post WAF blocks. re:Post has historically blocked Lambda traffic.
  Running locally with the browser-shaped User-Agent set in
  `connect_knowledge.repost` generally works.

## Layout

```
.kiro/connect_knowledge_mcp/
├── README.md                 # this file
├── .python-version           # 3.11
├── pyproject.toml            # deps, console scripts, builds connect_knowledge
├── main.py                   # placeholder
├── connect_knowledge/        # search, parse, validate package
└── connect_knowledge_mcp.py  # FastMCP server, eight @mcp.tool() functions
```

`connect_knowledge/_action_types.py` and `_view_component_types.py` are
generated. The refresh scripts in
[`.kiro/scripts`](../scripts/README.md) rewrite them, so edit the
generator rather than the file.
