---
name: mcp-gateway-author
description: Author a Bedrock AgentCore MCP gateway over an Amazon API Gateway REST API with AWS CDK (Python), so a Connect AI agent can call your backend as MCP tools. Use this skill when the user wants to expose a REST API (API Gateway + Lambda + DynamoDB) as an MCP server through an AgentCore gateway — covering API Gateway method conventions, authoring a rich OpenAPI schema, API-key auth wiring, the AgentCore CfnGateway/CfnGatewayTarget constructs, JWT inbound authorization, credential providers, sample/seed data, and the full set of deploy-tested gotchas. This is the focused, battle-tested companion to the broader connect-iac-cdk-author skill — reach here specifically for the "REST API to OpenAPI to AgentCore gateway/target to MCP tools" chain. Industry sample (telco) and seed-data templates live under this skill's samples/ folder. Consult the #cdk-agentcore and #cdk-iac steering catalogs and the cdk_docs MCP tools for construct lookups.
---

# MCP Gateway author (API Gateway → AgentCore → MCP tools)

You are authoring the chain that turns a backend REST API into MCP tools a
Connect AI agent can call:

```
DynamoDB ─▶ Lambda ─▶ API Gateway REST API ─▶ AgentCore Gateway (MCP) ─▶ Connect AI agent
            (handlers)   (+ OpenAPI, API key)    (CfnGateway + CfnGatewayTarget)
```

This skill is **guidance plus reference code**, not a generator. The
`reference/` folder holds deploy-tested constructs you adapt per project;
`samples/` holds an industry example (telco) and seed data. Always confirm
exact construct property names with `get_cdk_construct_doc` for the
`aws-cdk-lib` version pinned in the project — the AgentCore L1 surface evolves.

For project layout, the reuse-vs-create pattern, and the broader Connect
deployment chain (instance, Q in Connect, flows, views, AI agents), use the
sibling **`connect-iac-cdk-author`** skill. This skill zooms in on the
gateway/target/API chain.

## The two target types — pick first

An AgentCore `CfnGatewayTarget` can read the tool surface two ways:

| | Native API Gateway target | Inline OpenAPI target |
|---|---|---|
| How | `api_gateway` (rest_api_id + stage); gateway reads API GW's **auto-exported** schema | `open_api_schema.inline_payload` = a **hand-authored** OpenAPI string |
| Tool richness | Names/descriptions via `tool_overrides`; **no body schemas** with proxy integration | Full: descriptions, typed request/response schemas, examples |
| Credential provider | `GATEWAY_IAM_ROLE` works | **Required explicit provider** (IAM or API key) |
| Best for | Simple GET surfaces, fast wiring | Rich tools, POST bodies, anything the agent must reason about |

Choose inline OpenAPI when the agent needs to understand inputs/outputs
(recommended for most Connect AI use cases). Choose native when the surface is
trivial and you want zero authored schema.

## Step 1 — Backend: DynamoDB + Lambda + API Gateway

- Put all tables in one `Tables` construct (`databases/databases.py`), all
  functions in one `Lambdas` construct (`lambdas/project_lambdas.py`), the API
  in `apis/`. See `connect-iac-cdk-author` and `#cdk-iac` for the layout.
- **Seed sample data** with an `AwsCustomResource` + DynamoDB `BatchWriteItem`
  (no seeder Lambda). Keep data in `databases/data/<table>.json` in DynamoDB
  attribute-value format. Reference: `reference/databases_with_seed.py` and
  `samples/telco/data/*.json`. `BatchWriteItem` caps at 25 items/call.
- **GSIs for alternate lookups** (e.g. by phone, by email): add one GSI per
  alternate key; the handler queries the matching index. CloudFormation allows
  only **one new GSI per update** on an existing table — add them one deploy at
  a time (a brand-new table can ship with several at once).

### API Gateway method conventions (these bite at deploy)

Every method that the gateway will expose **must** declare:

- **`method_responses`** — else the exported OpenAPI has no `responses` and
  the target fails with "responses is missing".
- **`operation_name`** — exported as `operationId`, which becomes the MCP tool
  name; else "has no operationId and no override provided".

One `operationId` is allowed per path+method. To expose two lookups on the
same collection (e.g. by-phone and by-email), give one its own literal
sub-path (`/accounts/by-email`) — a literal segment also takes routing
priority over a `{param}` sibling. See `reference/telco_api.py`.

## Step 2 — Author the OpenAPI schema (inline target)

- Author a **rich** spec (`apis/openapi/openapi.yaml`): per-operation
  `summary` + `description`, typed request/response schemas, `examples`,
  reusable `components/schemas`, and an `ApiKeyAuth` security scheme. The
  agent's tool quality is only as good as this spec. Model on
  `samples/telco/openapi.yaml`.
- The `servers[0].url` is a **template**:
  `https://${ApiId}.execute-api.${AWS::Region}.amazonaws.com/${Stage}`. At
  synth, serialize the YAML to a compact JSON string (keep the markers), and
  the gateway construct wraps it in `Fn.sub` so `${ApiId}`/`${Stage}` resolve
  to the **real deployed API** at deploy time. Reference:
  `reference/openapi_spec.py`. JSON (not YAML) for the inline payload avoids
  multi-line-string quoting pitfalls.

## Step 3 — API key auth (inline target needs a credential provider)

OpenAPI-schema targets **require** an explicit credential provider. For API
key auth, wire one secret as the single source of truth feeding both ends:

```
Secret (generated apiKey)
  ├─▶ API Gateway ApiKey + UsagePlan       (the API enforces x-api-key)
  └─▶ AgentCore API Key credential provider (EXTERNAL → the secret)
         └─▶ GatewayTarget (API_KEY provider injects x-api-key per call)
```

- API side: generate the key in Secrets Manager, seed the API Gateway `ApiKey`
  from it, bind a usage plan to the stage, set `api_key_required=True` on every
  method. See `reference/telco_api.py`.
- Provider side: `reference/api_key_credential_provider.py` creates the
  AgentCore provider via custom resource. **Critical gotchas baked in:**
  - **`install_latest_aws_sdk=True`** — the default Lambda SDK is too old to
    know `apiKeySecretSource`/`apiKeySecretConfig`, drops them, and the service
    then demands a raw `apiKey` ("ApiKey is required when secret source is
    MANAGED or not specified").
  - The role needs **`bedrock-agentcore:CreateTokenVault`** (+ GetTokenVault):
    the first-ever provider lazily creates the account's default Token Vault.
  - `apiKeySecretSource="EXTERNAL"` + `apiKeySecretConfig={secretId, jsonKey}`
    so the value comes from the shared secret.

The plaintext key never appears in code or the template — only the secret ARN
and a dynamic reference.

For an IAM-auth target instead, use `credential_provider_type="GATEWAY_IAM_ROLE"`
+ `iam_credential_provider(service="execute-api")` (no API key, no secret).

## Step 4 — AgentCore gateway + target

Reference: `reference/agent_core_gateway.py` (the full construct with both
target types and the audience auto-patch). Key points:

- **`CfnGateway`**: `protocol_type="MCP"`, `authorizer_type="CUSTOM_JWT"`,
  `AuthorizerConfigurationProperty(custom_jwt_authorizer=
  CustomJWTAuthorizerConfigurationProperty(discovery_url=..., allowed_audience=[...]))`.
  Note **JWT is uppercase** in the class name.
- **Discovery URL** (identity provider) is the Connect instance OIDC endpoint:
  `https://<instance-alias>.my.connect.aws/.well-known/openid-configuration`.
- **`allowedAudience` must equal the gateway's own id** (Connect issues the JWT
  with `aud = <gateway id>`). The id only exists after creation → circular
  dependency. Two ways out, both in the reference construct:
  - **two-phase**: deploy with a placeholder audience, read `McpGatewayId`
    output, set it in config, redeploy; or
  - **`auto_audience=True`**: an `UpdateGateway` custom resource sets
    `allowedAudience=[<gateway id>]` in one deploy. `UpdateGateway` is
    **full-replace** — re-send name/roleArn/protocolType/authorizerType/the
    whole authorizerConfiguration.
  - `*` is **not** valid for allowedAudience and would defeat the authorizer.
- **Target config type is immutable** — you cannot change a target from
  `apiGateway` to `openApiSchema` in place ("Target configuration cannot be
  updated..."). Give the new target a **different logical id / name** to force
  replacement.

## Step 5 — Register the gateway as a Connect MCP integration

Once the gateway exists, register it on the Connect instance so the AI agent
can use its tools. This is **NOT** a Lex/Lambda `IntegrationAssociation`
(`CfnIntegrationAssociation` only accepts `LEX_BOT | LAMBDA_FUNCTION`). It is a
**third-party APPLICATION** integration, in two steps — both via custom
resources, since there is no native construct for an AppIntegrations
`MCP_SERVER` application. Reference: `reference/mcp_integration.py`.

```
appintegrations CreateApplication (ApplicationType=MCP_SERVER)
  AccessUrl = gateway MCP URL (.../mcp)
  Namespace = the gateway ID EXACTLY        <- hard requirement
  -> application ARN
        |
connect CreateIntegrationAssociation (IntegrationType=APPLICATION)
  IntegrationArn = application ARN
  -> associates it to the instance
```

Prereq enforced by Connect: the instance must be configured with the gateway's
Discovery URL, and a gateway maps to exactly **one** instance / one MCP server.

The hard-won specifics (each a real deploy failure):

- **`Namespace` must equal the gateway ID** — any other value fails "Namespace
  for MCP server applications must be a valid Bedrock Agent Core Gateway ID".
- **`install_latest_aws_sdk=True`** on both custom resources — `MCP_SERVER` and
  the APPLICATION association are new in the SDK.
- **`DeleteApplication` takes the ARN** — set the application custom resource's
  physical id to `from_response("Arn")`, not `Id`.
- **IAM permissions are not documented for these preview APIs**; the set that
  produced a clean deploy (found one error at a time):
  - Step 1: `app-integrations:CreateApplication`/`Delete`/`Get`/`TagResource`
    **plus `bedrock-agentcore:GetGateway`** (CreateApplication validates the
    namespace against the real gateway → "Missing permissions to access
    gateway" without it).
  - Step 2: `connect:CreateIntegrationAssociation`/`Delete` **plus
    `app-integrations:CreateApplicationAssociation`** (Connect creates an app
    association internally) **plus `iam:CreateServiceLinkedRole` /
    `PutRolePolicy` on
    `arn:aws:iam::*:role/aws-service-role/connect.amazonaws.com/*`**
    (associating an APPLICATION updates Connect's SLR → "Access denied updating
    the Amazon Connect service-linked role" without it).
- **Manual + CDK collide**: the app namespace (= gateway id) is unique, so if
  you created the app/association by hand (e.g. CLI validation), delete them
  before the stack creates them, or CloudFormation hits
  `DuplicateResourceException`.

## Deploy and verify

```bash
cdk synth    # the gate — never deploy a project that doesn't synth
cdk diff     # on request
cdk deploy
```

- **Synth-before-deploy gate.** Surface the first synthesis error and stop.
- Keep the pinned `aws-cdk-lib` and the `cdk` CLI in step; a "schema version
  mismatch" means upgrade the CLI (`npm i -g aws-cdk@latest`) or pin the lib
  down.
- After deploy, verify the target stabilized and tools appear:
  ```bash
  aws bedrock-agentcore-control get-gateway --gateway-identifier <id> \
    --region <region> --query 'authorizerConfiguration'
  ```

## Deploy-tested gotcha checklist

Run through this before deploying an MCP gateway — each item is a real failure
we hit (full detail in `#cdk-agentcore` "Hard-won deploy learnings"):

- [ ] Every API method has `method_responses` **and** `operation_name`.
- [ ] Lambda asset folders are non-empty (an empty zip → "Uploaded file must
      be a non-empty zip").
- [ ] OpenAPI target: explicit credential provider set (not bare
      GATEWAY_IAM_ROLE).
- [ ] API-key provider custom resource has `install_latest_aws_sdk=True` and
      `CreateTokenVault` permission.
- [ ] `allowedAudience` = gateway id (auto-patch or two-phase), never `*`.
- [ ] Switching target type? New logical id / target name (immutable type).
- [ ] One `operationId` per path+method; alternate lookups get literal
      sub-paths.
- [ ] Inline spec server URL templated with `${ApiId}`/`${Stage}` + `Fn.sub`.
- [ ] No secrets in any committed file; key value lives only in Secrets
      Manager.
- [ ] Connect integration: app `Namespace` = gateway id; both custom resources
      `install_latest_aws_sdk=True`; app physical id = ARN; role has
      `bedrock-agentcore:GetGateway`, `app-integrations:CreateApplicationAssociation`,
      and Connect SLR perms.

## Reference files

| File | What it is |
|---|---|
| `reference/agent_core_gateway.py` | `CfnGateway` + `CfnGatewayTarget` construct: JWT authorizer, audience auto-patch, native + inline-OpenAPI targets |
| `reference/api_key_credential_provider.py` | AgentCore API-key credential provider via custom resource (Token Vault + SDK gotchas baked in) |
| `reference/openapi_spec.py` | Loads authored YAML, renders to JSON with `${ApiId}`/`${Stage}` markers for `Fn.sub` |
| `reference/telco_api.py` | API Gateway REST API with method conventions + API-key/usage-plan wiring |
| `reference/databases_with_seed.py` | DynamoDB tables + `BatchWriteItem` sample-data seeding |
| `reference/mcp_integration.py` | Register the gateway as a Connect MCP integration (AppIntegrations MCP_SERVER app + APPLICATION association, deploy-tested IAM) |
| `samples/telco/openapi.yaml` | Industry sample: rich telco self-service OpenAPI (accounts/plans/support) |
| `samples/telco/data/*.json` | Telco seed data (accounts, plans, cases) in DynamoDB attribute-value format |

More industry samples (beyond telco) can be added under `samples/<industry>/`
as they are built.

## Do not

- Do not deploy a project that does not `cdk synth` cleanly.
- Do not change a target's config type in place — replace it with a new name.
- Do not set `allowedAudience` to `*`.
- Do not write AWS credentials/keys/tokens into any file; the API key lives
  only in Secrets Manager.
- Do not re-author flow/view/agent/prompt/KB bodies here — that's the
  artifact-authoring skills' job (see `connect-iac-cdk-author`).
