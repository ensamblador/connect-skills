---
inclusion: manual
last_refreshed: 2026-06-04
source_urls:
  - https://docs.aws.amazon.com/cdk/v2/guide/home.html
  - https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html
  - https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping-env.html
content_checksum: sha256:ec81be4e3b6886fa
---

# CDK IaC conventions for `connect-skills`

General Infrastructure-as-Code conventions for authoring AWS CDK (Python)
projects in this repository. The four per-domain construct catalogs
(`#cdk-connect`, `#cdk-lex`, `#cdk-q-in-connect`, `#cdk-agentcore`) tell you
*which construct* to reach for; this file tells you *how the project is laid
out, deployed, and kept safe*.

**Activation:** this file is opt-in. Reference it from chat with `#cdk-iac`
whenever you scaffold or extend a `CDK_Project`, apply the reuse-vs-create
pattern, or run the bootstrap / synth / diff / deploy workflow.

**Freshness rule (for the agent):** before relying on this file, compare the
`last_refreshed` date in the front matter with today's date. If the file is
older than 7 days, run
``uv run python .kiro/scripts/refresh_cdk_docs.py`` to refresh the CDK
catalogs before answering. Always refresh when the user explicitly asks for
it. A regenerated file with no diff is fine — `last_refreshed` is the only
thing that needs updating, and the script handles that automatically.

## Project layout (M6)

Every project's IaC lives under a per-project CDK subfolder:

```
projects/<project>/<project>-cdk/
├── app.py                      # CDK app entry
├── cdk.json                    # app command + context (reuse-vs-create keys)
├── requirements.txt            # PINNED deps (aws-cdk-lib, constructs)
├── requirements-dev.txt        # optional dev/test deps
├── .venv/                      # project-local virtualenv (gitignored)
├── README.md                   # bootstrap / synth / diff / deploy notes
├── stacks/
│   └── <project>_stack.py      # composition root; composes the constructs
├── lambda/                     # Lambda constructs + handler code
├── databases/                  # DynamoDB constructs
├── apis/                       # API Gateway REST API
│   ├── openapi/<domain>.json   # OpenAPI schema artifact
│   └── agentcore/              # AgentCore gateway + target
├── connect/                    # instance, q, integrations, experience, ai, security
└── schemas/                    # shared schema artifacts
```

Constructs are organised into per-resource-type subfolders (the
primitive-repo convention), so a reader finds the Lambda code under
`lambda/`, the tables under `databases/`, and the REST API under `apis/`.

## Dependencies and environment

- Pin `aws-cdk-lib` and `constructs` in `requirements.txt`; install into the
  project-local `.venv` so each `CDK_Project` is self-contained.
- Source the deployment account and region from the environment
  (`CDK_DEFAULT_ACCOUNT` / `CDK_DEFAULT_REGION` via `Stack(env=...)`). Never
  hardcode an account id or region in committed code.

## Bootstrap / synth / diff / deploy workflow

Run these from the `CDK_Project` directory with the project venv active:

```
cdk bootstrap     # one-time per account/region — provisions the CDK toolkit stack
cdk synth         # render the CloudFormation template; the synth-before-deploy gate
cdk diff          # preview the change set against the deployed stack (on request)
cdk deploy        # provision/update resources
```

**Synth-before-deploy gate:** always run `cdk synth` and surface any
synthesis error *before* any deploy step. A project that does not synth is
never deployed. On request, run `cdk diff` and present the difference before
provisioning.

## Reuse vs create — the authoring pattern

Authors frequently already own parts of the deployment chain (a live Connect
instance, an existing AgentCore gateway). When you author **any**
provisionable dependency, apply this one decision:

```
force_new == True                       -> create a new Cfn* resource
existing_id supplied (not None / blank)  -> reference the existing resource
otherwise                               -> create a new Cfn* resource
```

Read the existing-id / force_new inputs from CDK context (`cdk.json`
`context` or `-c key=value`), for example `existing_connect_instance_id`,
`existing_agentcore_gateway_id`, or `existing_q_in_connect_domain_id`, plus
a `force_new` map. Resolve the dependency's identifier/ARN once and thread
that single value into every dependent association, so dependent constructs
bind to whichever resource is in use without caring whether it was created
or referenced. Keep this decision in one small helper per resource type in
the stack (see the `connect-iac-cdk-author` skill for a reference snippet)
rather than scattering `try_get_context` branches across constructs.

**Unresolved-identifier safety:** if a supplied `existing_id` cannot be
resolved to a reachable resource (a pre-flight `aws connect describe-*` or
a `cdk context` lookup fails), report the unresolved identifier and stop
that binding. Do NOT silently fall through to creating a duplicate.

## Security baseline

- **No secrets in the repo.** No AWS access keys, secret keys, session
  tokens, or live-account-bound secrets appear in any generated artifact
  (CDK code, `cdk.json`/context, OpenAPI schema, steering, or `SKILL.md`).
- **Credentials come from the operator.** All AWS access resolves from the
  operator's local AWS profile / SSO environment at deploy time
  (`AWS_PROFILE`, `aws sso login`). The CDK app and skill never read or write
  credentials.
- **Missing credentials fail safe.** If a deploy is attempted without
  resolvable credentials, report that credentials are missing and write no
  credential material into the project.

## Seeding sample data into DynamoDB

To load demo/sample data into a table at deploy time, use an
`AwsCustomResource` calling DynamoDB `BatchWriteItem` (no seeder Lambda to
maintain). Keep the data in `databases/data/<table>.json` in DynamoDB's
native attribute-value format (`{"S": "..."}`, `{"N": "..."}`, `{"BOOL": true}`),
read it at synth, and pass it as `RequestItems`:

```python
cr.AwsCustomResource(
    self, "SeedAccounts",
    on_update=cr.AwsSdkCall(
        service="dynamodb", action="BatchWriteItem",
        parameters={"RequestItems": {table.table_name: [
            {"PutRequest": {"Item": item}} for item in items]}},
        # New physical id when the data changes → re-seeds on update.
        physical_resource_id=cr.PhysicalResourceId.of(f"seed-{table.table_name}-{len(items)}"),
    ),
    policy=cr.AwsCustomResourcePolicy.from_sdk_calls(resources=[table.table_arn]),
)
```

Notes: `BatchWriteItem` caps at 25 items per call (batch if you have more);
add a dependency on the table so the write never runs before the table
exists; numeric JSON values are strings in attribute-value format
(`{"N": "42.5"}`), and Lambda handlers should convert DynamoDB `Decimal`
back to int/float when serializing JSON responses.

## Exposing a REST API as MCP tools (API key chain)

When fronting an API Gateway REST API with an AgentCore gateway using an
**inline OpenAPI** target and **API-key** auth, one Secrets Manager secret is
the single source of truth for the key value, consumed by both ends:

```
Secret (generated apiKey)
  ├─> API Gateway ApiKey + UsagePlan   (the API enforces x-api-key)
  └─> AgentCore API Key credential provider (EXTERNAL → the secret)
         └─> GatewayTarget (API_KEY provider injects x-api-key per call)
```

The plaintext key never appears in code or the template — only the secret ARN
and a dynamic reference. See `#cdk-agentcore` "Hard-won deploy learnings" for
the gateway/target/credential-provider specifics (Token Vault permission,
`install_latest_aws_sdk`, immutable target type, etc.).

## Authoring the constructs

Kiro writes the CDK code for each project — there is no generator script.
Ground every construct in the canonical docs: for the construct to use per
domain, see the catalogs `#cdk-connect`, `#cdk-lex`, `#cdk-q-in-connect`,
`#cdk-agentcore`; for a per-construct deep dive (exact property names,
required fields), call the `get_cdk_construct_doc` MCP tool (or run
``cdk-construct-doc`` from a terminal) with the construct name. Connect /
Lex / Wisdom are **L1-only** (`Cfn*`), so look up the precise `Cfn*`
properties rather than assuming an L2 convenience API exists. The
`connect-iac-cdk-author` skill carries reference snippets and resource
best practices (AgentCore JWT/OIDC gateway, backend API/Lambda/DynamoDB,
the reuse-vs-create helper).
