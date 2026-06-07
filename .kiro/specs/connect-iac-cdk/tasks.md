# Implementation Plan: Connect IaC (CDK for Python)

## Overview

This plan builds the three pillars from the design incrementally so the
repository stays working at every step:

1. **`CDK_Docs_MCP`** (C1) — a second FastMCP / `uv` server in a sibling
   `cdk_docs_mcp/` folder (knowledge plane, foundational), then its
   registration in `.kiro/settings/mcp.json` (C1 / Req 2).
2. **`IaC_Steering`** (C2) + **`CDK_Docs_Refresh`** hook (C3) — the five
   steering catalogs and the refresh script/hook that regenerate them.
3. **`IaC_Skill`** (C4) — skill scaffolding, the **Resource Resolver**
   (C5, the spine), the per-domain construct authors (C6, C7) that bind
   through the resolver and consume existing-skill artifact bodies (C8),
   security/credential handling (C9), deploy/verify workflow docs (C10),
   and the README update (Req 17.2).

The 11 correctness properties become `hypothesis` property-based tests
(≥100 iterations, tagged `Feature: connect-iac-cdk, Property {n}: {text}`)
for the pure-logic pieces (resolver decision, doc parser, MCP↔CLI parity,
checksum, freshness, discovery-URL, catalog completeness, write-discipline,
no-secrets scan, no-regression). CDK construct generation is validated with
`cdk synth` snapshot/structural tests, and external behavior (MCP
registration, live doc fetch, synth-before-deploy gate, `cdk diff`) with a
small number of integration/smoke tests, per the design's Testing Strategy.

Language: **Python** (matches the design — FastMCP server, `hypothesis`
tests, CDK for Python).

Manual operator actions (`cdk bootstrap` / `synth` / `diff` / `deploy`
against a live account) are documented in `SKILL.md`, not run as tasks.

## Tasks

- [ ] 1. Build the `CDK_Docs_MCP` server (C1)
  - [x] 1.1 Scaffold the `cdk_docs_mcp/` package and `pyproject.toml`
    - Create `cdk_docs_mcp/` as a sibling of `connect_knowledge_mcp/` with
      `README.md`, `pyproject.toml` (`name = "cdk-docs-mcp"`, `uv`-runnable,
      deps `mcp[cli]`, `requests`, `beautifulsoup4`), and the
      `cdk_docs/__init__.py` package
    - Declare console scripts `cdk-docs-search = "cdk_docs.cli:docs_main"`
      and `cdk-construct-doc = "cdk_docs.cli:construct_main"`
    - _Requirements: 1.1_

  - [x] 1.2 Implement `cdk_docs/fetch.py`
    - HTTP GET with retry/back-off modeled on `connect_knowledge/docs.py`
      (`MAX_RETRIES`, `BACKOFF_BASE`, `REQUEST_TIMEOUT`)
    - Define the closed `LIBRARIES` set (`aws_cdk.aws_connect`,
      `aws_cdk.aws_lex`, `aws_cdk.aws_wisdom`,
      `aws_cdk.aws_bedrockagentcore`) mapped to their reference URLs
    - _Requirements: 1.4, 1.6_

  - [x] 1.3 Implement `cdk_docs/construct_doc.py` parser
    - Parse a CDK construct reference page into the `ConstructDoc` model
      (M2): `construct`, `library`, `url`, `properties`, `description`,
      `raw_sections`; preserve construct name, source URL verbatim, and the
      property list
    - Return a descriptive error result naming the identifier and reason
      when a page cannot be retrieved or parsed (no raise)
    - _Requirements: 1.3, 1.5, 1.6_

  - [x] 1.4 Write property test for doc parse fidelity
    - **Property 3: Doc parse fidelity** — for any in-scope construct page
      the fetcher retrieves, parsing preserves construct name, source URL
      (verbatim), and a non-empty property list when the page documents any
    - `hypothesis`, ≥100 iterations, tag
      `Feature: connect-iac-cdk, Property 3: Doc parse fidelity`
    - **Validates: Requirements 1.3, 1.5**

  - [x] 1.5 Implement `cdk_docs/search.py`
    - `cdk_search(query, limit=10)` returning `Title / URL / Snippet` block
      output identical in format to the existing `aws_search`
    - _Requirements: 1.2_

  - [x] 1.6 Implement `cdk_docs/cli.py` console-script entry points
    - `docs_main` and `construct_main` calling the **same** package
      functions the MCP tools call, so terminal output matches tool output
    - _Requirements: 1.7_

  - [x] 1.7 Implement `cdk_docs_mcp.py` FastMCP server and tools
    - `FastMCP("cdk_docs")` exposing `search_cdk_docs(query, limit=10)` and
      `get_cdk_construct_doc(construct, library=None)`, each delegating to
      the shared package functions and returning descriptive error results
    - _Requirements: 1.2, 1.3, 1.4, 1.6_

  - [-] 1.8 Write property test for MCP tool / CLI parity
    - **Property 4: MCP tool / CLI parity** — for any lookup input, the MCP
      tool result and the console-script result are equivalent
    - `hypothesis`, ≥100 iterations, tag
      `Feature: connect-iac-cdk, Property 4: MCP tool / CLI parity`
    - **Validates: Requirements 1.7**

  - [-] 1.9 Write integration test for live per-library fetch
    - Fetch one real CDK reference page per `LIBRARIES` entry and assert a
      parsed result with name/properties/URL (1 example each, not PBT —
      external service)
    - _Requirements: 1.4_

- [ ] 2. Register `CDK_Docs_MCP` in MCP settings (Req 2)
  - [-] 2.1 Add the `cdk_docs` server entry to `.kiro/settings/mcp.json`
    - Add a second top-level entry, leaving the existing `connect_knowledge`
      entry byte-for-byte unchanged
    - `command` = absolute `uv` path consistent with the existing entry;
      `args` = `["run", "--directory", "<abs>/cdk_docs_mcp", "python",
      "cdk_docs_mcp.py"]`; `disabled: false`
    - `autoApprove` lists the read-only tools `search_cdk_docs` and
      `get_cdk_construct_doc`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [~] 2.2 Write integration smoke test for MCP registration
    - Assert the `cdk_docs` entry is present with both tools, the
      `connect_knowledge` entry is unchanged, and the JSON parses
    - _Requirements: 2.1, 2.4_

- [x] 3. Build `IaC_Steering` catalogs and the `CDK_Docs_Refresh` hook (C2, C3)
  - [x] 3.1 Author the five steering files with the front-matter contract
    - Create `cdk-connect.md`, `cdk-lex.md`, `cdk-q-in-connect.md`,
      `cdk-agentcore.md` (per-domain construct catalogs) and `cdk-iac.md`
      (general IaC conventions, project layout, bootstrap/synth/diff/deploy,
      resolver pattern, security baseline) under `.kiro/steering/`
    - Each file: `inclusion: manual`, `last_refreshed`, `source_urls`,
      `content_checksum` (and `construct_count` on catalog files); each
      catalog entry is a row of `construct name | one-line description |
      link to CDK doc page` (M1); embed the 7-day freshness rule text
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 3.2 Write property test for catalog entry completeness
    - **Property 5: Catalog entry completeness** — every generated catalog
      entry has a non-empty construct name, a description field, and a link
      to the construct's CDK doc page
    - `hypothesis`, ≥100 iterations, tag
      `Feature: connect-iac-cdk, Property 5: Catalog entry completeness`
    - **Validates: Requirements 3.3**

  - [x] 3.3 Write property test for the steering freshness rule
    - **Property 8: Steering freshness rule** — for any file and current
      date, the check flags stale iff `current_date - last_refreshed > 7
      days`
    - `hypothesis`, ≥100 iterations, tag
      `Feature: connect-iac-cdk, Property 8: Steering freshness rule`
    - **Validates: Requirements 3.6**

  - [x] 3.4 Implement `.kiro/hooks/scripts/refresh_cdk_docs.py`
    - Fetch the four CDK reference pages (reusing
      `_doc_fetcher.fetch_with_fallback` for 404 self-healing), parse each
      into a construct catalog, and rewrite the four `cdk-*.md` catalog
      files, updating `last_refreshed` and `content_checksum`
      (`"sha256:" + sha256(table_body).hexdigest()[:16]`) together
    - Support `--dry-run` (print, no write); on a fetch failure report the
      failing source URL and leave that catalog file unchanged
    - _Requirements: 4.1, 4.3, 4.4, 4.5_

  - [x] 3.5 Write property test for refresh checksum integrity
    - **Property 6: Refresh checksum integrity** — `content_checksum` is a
      deterministic function of content (same content → same checksum, any
      change → different), and regeneration updates `last_refreshed` and
      `content_checksum` together
    - `hypothesis`, ≥100 iterations, tag
      `Feature: connect-iac-cdk, Property 6: Refresh checksum integrity`
    - **Validates: Requirements 4.3**

  - [x] 3.6 Write property test for refresh write-discipline
    - **Property 7: Refresh write-discipline** — `--dry-run` leaves all
      steering files unchanged, and a failed source fetch leaves the
      corresponding file unchanged (with the failing URL reported); use
      mocked fetches
    - `hypothesis`, ≥100 iterations, tag
      `Feature: connect-iac-cdk, Property 7: Refresh write-discipline`
    - **Validates: Requirements 4.4, 4.5**

  - [x] 3.7 Create `.kiro/hooks/refresh-cdk-docs.kiro.hook`
    - `userTriggered` hook with
      `runCommand: uv run python .kiro/hooks/scripts/refresh_cdk_docs.py`,
      matching the existing `refresh-*.kiro.hook` JSON shape
    - _Requirements: 4.2_

- [~] 4. Checkpoint — knowledge plane complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Scaffold the `IaC_Skill` and CDK project layout (C4)
  - [x] 5.1 Create the skill shell
    - Create `.kiro/skills/connect-iac-cdk-author/` with a `SKILL.md`
      (front matter `name` + `description`, matching the other skills) and
      an empty `scripts/` folder
    - _Requirements: 5.1_

  - [x] 5.2 Implement project scaffolding to the M6 layout
    - Scaffold `projects/<project>/<project>-cdk/` with `app.py`,
      `cdk.json` (context keys for the reuse-vs-create inputs of M3),
      pinned `requirements.txt` (`aws-cdk-lib`, `constructs`),
      `requirements-dev.txt`, `README.md`, `stacks/`, and the
      per-resource-type subfolders (`lambda/`, `databases/`, `apis/` with
      `openapi/` and `agentcore/`, `connect/`, `schemas/`)
    - Support both scaffolding options — CLI (`cdk init app
      --language=python`) and manual — both converging on the same layout
      and a project-local venv installed from the pinned requirements
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 5.3 Implement the `cdk synth` scaffold gate
    - Run `cdk synth` after scaffolding and report any synthesis error
      before reporting the scaffold complete
    - _Requirements: 5.7_

  - [-] 5.4 Write integration test for the scaffold synth gate
    - Scaffold a project and assert `cdk synth` exits 0 (run as a gate,
      not 100 iterations — high cost, deterministic)
    - _Requirements: 5.7_

- [ ] 6. Implement the Resource Resolver (C5, the spine)
  - [x] 6.1 Implement `resolve()` and the `ResourceHandle` model
    - Pure decision function over `(resource_type, existing_id, force_new)`
      following the decision table (force_new → created; existing_id
      supplied → imported; otherwise → created), returning a uniform
      `ResourceHandle` (M5: `kind`, `identifier`, `arn`, `ref`) that
      dependent constructs bind to without branching on `kind`
    - Read reuse-vs-create inputs from the `CdkProjectContext` (M3) CDK
      context keys
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 6.2 Implement unresolved-identifier safety
    - When a supplied `existing_id` cannot be resolved to a reachable
      resource (pre-flight/context lookup), report the unresolved
      identifier and abort that binding without producing a `created`
      handle (no duplicate)
    - _Requirements: 6.6_

  - [x] 6.3 Write property test for the conditional-provisioning invariant
    - **Property 1: Conditional-provisioning invariant (reuse vs create)** —
      for any resource type and any input combination, `resolve()` returns
      imported when `existing_id` supplied and `force_new` false, created
      when no `existing_id`, and created whenever `force_new` is true
    - `hypothesis`, ≥100 iterations, tag
      `Feature: connect-iac-cdk, Property 1: Conditional-provisioning invariant (reuse vs create)`
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.5**

  - [-] 6.4 Write property test for unresolved-identifier safety
    - **Property 2: Unresolved-identifier safety** — for any supplied
      `existing_id` that cannot be resolved, the resolver reports it and
      never returns a `created` handle in its place
    - `hypothesis`, ≥100 iterations, tag
      `Feature: connect-iac-cdk, Property 2: Unresolved-identifier safety`
    - **Validates: Requirements 6.6**

- [~] 7. Checkpoint — scaffold and resolver complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement backend application constructs (C6)
  - [x] 8.1 Implement the backend REST API author (`apis/`)
    - Generate an API Gateway REST API construct from an OpenAPI schema
      artifact for the project's industry domain and store the schema under
      `apis/openapi/<domain>.json`
    - On missing/invalid industry-domain config, report it and emit a
      minimal valid REST API scaffold that still `cdk synth`s
    - _Requirements: 7.1, 7.4, 7.5_

  - [x] 8.2 Implement the Lambda compute author (`lambda/`)
    - Generate `aws_lambda.Function` constructs (plus handler code) backing
      the REST API operations
    - _Requirements: 7.2_

  - [x] 8.3 Implement the DynamoDB data author (`databases/`)
    - Generate `aws_dynamodb.Table` constructs the backend Lambdas read and
      write
    - _Requirements: 7.3_

  - [-] 8.4 Write synth-snapshot tests for backend constructs
    - Assert the synthesized template contains the REST API, Lambda, and
      table resources, and that the degraded path still synthesizes
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

- [ ] 9. Implement the AgentCore gateway construct (C7)
  - [x] 9.1 Implement the OIDC discovery-URL derivation function
    - Pure `oidc_discovery_url(instance_alias)` returning
      `https://<instance-alias>.my.connect.aws/.well-known/openid-configuration`
      and an `allowed_audience` equal to the gateway identifier
    - _Requirements: 8.5_

  - [x] 9.2 Write property test for the discovery-URL derivation
    - **Property 9: AgentCore discovery-URL derivation** — for any instance
      alias, the derived discovery URL equals the canonical form and the
      allowed audience equals the gateway identifier
    - `hypothesis`, ≥100 iterations, tag
      `Feature: connect-iac-cdk, Property 9: AgentCore discovery-URL derivation`
    - **Validates: Requirements 8.5**

  - [-] 9.3 Implement the AgentCore gateway author (`apis/agentcore/`)
    - Generate `CfnGateway` (`protocol_type="MCP"`, JWT inbound authorizer
      using the discovery URL + audience from 9.1) and `CfnGatewayTarget`
      (REST/OpenAPI target read from S3), routed through the resolver (C5)
      so an existing gateway/MCP backend is referenced instead, and publish
      the resulting MCP backend handle/stack output for AI-agent wiring
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.6_

  - [~] 9.4 Write synth-snapshot test for the AgentCore gateway
    - Assert the JWT authorizer config and the S3-backed OpenAPI REST
      target appear in the synthesized template
    - _Requirements: 8.3, 8.4_

- [ ] 10. Implement Connect instance and Q in Connect constructs (C6)
  - [x] 10.1 Implement the Connect instance author (`connect/`)
    - Generate `CfnInstance` or an imported handle via the resolver, and
      publish the instance identifier once for all dependent associations
    - _Requirements: 9.1, 9.2, 9.3_

  - [-] 10.2 Implement the Q in Connect author (`connect/q/`)
    - Generate `CfnAssistant` + `CfnAssistantAssociation` and a
      `wisdom.CfnKnowledgeBase` over an S3 source, routed through the
      resolver, and associate the knowledge base with the Q in Connect
      domain in use
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [~] 10.3 Write synth-snapshot tests for Connect instance + Q in Connect
    - Assert imported-vs-created handles produce a reference vs a new
      `Cfn*` resource, and that the KB associates to the domain in use
    - _Requirements: 9.1, 9.2, 10.1, 10.5_

- [ ] 11. Implement integrations, experience, AI config, and security (C6, C8)
  - [-] 11.1 Implement the instance integrations author (`connect/integrations/`)
    - Generate the MCP integration against the instance, the Lex bot
      (`lex.CfnBot` + Connect bot association, routed through the resolver
      for an existing bot id/ARN), and the Lambda function associations
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [-] 11.2 Implement the experience author (`connect/experience/`)
    - Generate `CfnContactFlow` consuming validated `flow.json` from
      `connect-flow-author` and `CfnView` consuming `view.json` from
      `connect-view-author` as construct inputs (not re-authored)
    - _Requirements: 12.1, 12.2, 17.1_

  - [~] 11.3 Implement the AI config author (`connect/ai/`)
    - Generate the Connect AI agent, AI prompts, guardrail reference, and
      AI agent tools (including MCP integration tools wired to the C7
      backend), consuming agent/prompt bodies from `connect-ai-agent-author`
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 17.1_

  - [x] 11.4 Implement the security profile author (`connect/security/`)
    - Generate `Cfn*` Connect security profile constructs for agent
      permissions
    - _Requirements: 14.1_

  - [~] 11.5 Wire consumption of remaining existing-skill artifacts (C8)
    - Use `connect-kb-author` documents as the S3 source for the knowledge
      base and the `q-in-connect-bot-deploy` bundle for the Lex bot
      definition; when an upstream body is missing, direct the operator to
      the owning skill rather than re-authoring it
    - _Requirements: 17.1_

  - [~] 11.6 Write synth-snapshot/structural tests for these constructs
    - Assert integrations, contact flow, view, AI agent/prompt/tool, and
      security profile resources appear in the synthesized template
    - _Requirements: 11.1, 11.4, 12.1, 12.2, 13.1, 13.2, 13.3, 13.4, 14.1_

- [ ] 12. Wire the stack together
  - [~] 12.1 Compose all constructs in `stacks/<project>_stack.py`
    - Wire the resolver and every construct author, thread the Connect
      instance identifier into dependent associations, and source env from
      `CDK_DEFAULT_ACCOUNT` / `CDK_DEFAULT_REGION` (no hardcoded account)
    - _Requirements: 6.5, 9.3_

  - [~] 12.2 Write integration test for full-scaffold synth (reuse vs create)
    - Synth the composed stack under both "existing id supplied" and "none
      supplied" context, asserting imported-reference vs new-`Cfn*` output
      (Properties 1–2 at the CloudFormation level)
    - _Requirements: 6.1, 6.2, 6.3, 5.7_

- [~] 13. Checkpoint — full construct chain synthesizes
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Implement credential handling and deploy/verify docs (C9, C10)
  - [x] 14.1 Implement credential resolution and the no-secrets scan
    - Resolve AWS access from the operator's `AWS_Profile` / SSO at deploy
      time; on missing credentials, report it and write no credential
      material into the project; implement a scan that asserts generated
      artifacts contain no access key, secret key, or session token
    - _Requirements: 15.1, 15.2, 15.3_

  - [-] 14.2 Write property test for the no-secrets invariant
    - **Property 10: No-secrets invariant** — for any generated artifact
      (CDK code, context/config, steering, SKILL.md, OpenAPI schema, spec),
      no AWS access key, secret key, or session token is present; and a
      deploy without resolvable credentials writes no credential material
    - `hypothesis`, ≥100 iterations, tag
      `Feature: connect-iac-cdk, Property 10: No-secrets invariant`
    - **Validates: Requirements 15.2, 15.3**

  - [x] 14.3 Document the deploy/verify workflow in `SKILL.md` (C10)
    - Document `cdk bootstrap`, `cdk synth`, `cdk diff`, `cdk deploy`;
      describe the synth-before-deploy gate (synth runs and reports errors
      before any deploy) and the on-request `cdk diff` preview
    - _Requirements: 16.1, 16.2, 16.3_

  - [-] 14.4 Write integration test for the synth-before-deploy gate and diff
    - Assert deploy is blocked when `cdk synth` errors, and that a preview
      runs `cdk diff` and presents the difference before provisioning
    - _Requirements: 16.2, 16.3_

- [ ] 15. Guard regression and document the capability (Req 17)
  - [~] 15.1 Write the no-regression test for `connect_knowledge`
    - **Property 11: No-regression on existing `connect_knowledge`** —
      re-run the existing `connect_knowledge` MCP tool / CLI / refresh
      smoke checks and assert equivalent behavior after this change
    - tag `Feature: connect-iac-cdk, Property 11: No-regression on existing connect_knowledge`
    - **Validates: Requirements 17.3**

  - [~] 15.2 Update the root `README.md`
    - Document the `CDK_Docs_MCP` server, the `IaC_Steering` catalogs, and
      the `IaC_Skill`, leaving existing documentation intact
    - _Requirements: 17.2_

- [~] 16. Final checkpoint — full capability validated
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional (tests) and can be skipped for a
  faster MVP; core implementation tasks are never optional.
- Each task references the specific requirement clauses it implements for
  traceability.
- The 11 correctness properties map to `hypothesis` property-based tests
  over the pure-logic pieces; CDK construct generation is covered by
  `cdk synth` snapshot/structural tests; external behavior (MCP
  registration, live fetch, synth gate, `cdk diff`) by integration/smoke
  tests — per the design's Testing Strategy.
- Manual operator deployment (`cdk bootstrap` / `deploy` against a live
  account) is documented in `SKILL.md`, not executed as a task.
- The existing `connect_knowledge` MCP server, its tools, steering
  catalogs, hooks, and skills are left unchanged (Req 17.3); Task 15.1
  verifies this.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "3.1", "5.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.5", "3.2", "3.3", "3.4", "5.2", "6.1", "9.1"] },
    { "id": 2, "tasks": ["1.4", "1.6", "1.7", "3.5", "3.6", "3.7", "5.3", "6.2", "6.3", "8.1", "8.2", "8.3", "9.2", "10.1", "11.4", "14.1", "14.3"] },
    { "id": 3, "tasks": ["1.8", "1.9", "2.1", "5.4", "6.4", "8.4", "9.3", "10.2", "11.1", "11.2", "14.2", "14.4"] },
    { "id": 4, "tasks": ["2.2", "9.4", "10.3", "11.3"] },
    { "id": 5, "tasks": ["11.5", "11.6", "12.1"] },
    { "id": 6, "tasks": ["12.2", "15.1", "15.2"] }
  ]
}
```
