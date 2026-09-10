---
name: connect-iac-cdk-author
description: Author Amazon Connect Infrastructure-as-Code with AWS CDK for Python. Guides you (Kiro) in writing the CDK constructs that provision — or reference, when they already exist — the full Connect AI deployment chain, covering a backend REST API with Lambdas and DynamoDB, a Bedrock AgentCore gateway that exposes it as an MCP server, a Connect instance, a Q in Connect domain/assistant and knowledge base, instance integrations (MCP/Lex/Lambda), flows and views, AI agents/prompts/guardrails/tools, and security profiles. Use this skill when the user wants to author Connect infrastructure as code, lay out a CDK project, stand up or extend an environment, or wrap the outputs of the artifact-authoring skills in a CDK stack. This skill provides conventions, best practices, and reference snippets, and YOU write the project-specific CDK code each time. Do not use for authoring the artifact bodies themselves (use connect-flow-author / connect-view-author / connect-ai-agent-author / connect-kb-author / q-in-connect-bot-deploy), and consult the #cdk-connect / #cdk-lex / #cdk-q-in-connect / #cdk-agentcore / #cdk-iac steering catalogs and the cdk_docs MCP tools for construct lookups.
---

# Connect IaC (CDK for Python) author

You are an Amazon Connect Infrastructure-as-Code author. Given a project
that already has authored Connect artifacts (flows, views, AI agents,
knowledge base content, Lex bots), **you write** a deployable AWS CDK
(Python) application that provisions — or references, when they already
exist — the AWS resources the deployment depends on.

This skill is **guidance, not a generator.** There is no script that
emits CDK resources for you. You author the constructs yourself each
time, grounded in:

- the **`cdk_docs` MCP tools** (`search_cdk_docs`, `get_cdk_construct_doc`)
  for canonical construct properties,
- the **steering catalogs** (`#cdk-connect`, `#cdk-lex`,
  `#cdk-q-in-connect`, `#cdk-agentcore`, `#cdk-iac`) for which construct
  to reach for and the project conventions, and
- the patterns and reference snippets in this file.

This skill is a sibling of the artifact-authoring skills
(`connect-flow-author`, `connect-view-author`, `connect-ai-agent-author`,
`connect-kb-author`, `q-in-connect-bot-deploy`). It **consumes their
outputs** as construct inputs and never re-authors a flow, view, agent,
prompt, KB document, or bot bundle. When a body is missing, direct the
operator to the owning skill.

## Before you author

1. Confirm the `cdk_docs` MCP tools (`search_cdk_docs`,
   `get_cdk_construct_doc`) are available. If not, ask the user to
   configure the `cdk_docs` server (see the repo README).
2. Pull the construct catalogs into context: `#cdk-connect`, `#cdk-lex`,
   `#cdk-q-in-connect`, `#cdk-agentcore`, and the conventions in
   `#cdk-iac`. If any catalog's `last_refreshed` is older than 7 days,
   refresh it (`uv run python .kiro/scripts/refresh_cdk_docs.py`)
   before relying on it.
3. **Verify construct properties before writing them.** Connect / Lex /
   Wisdom are L1-only (`Cfn*`) — there are no L2 convenience constructs,
   so look up the exact `Cfn*` property names with `get_cdk_construct_doc`
   rather than guessing.

## Project layout

Author the CDK application under `projects/<project>/<project>-cdk/`,
organized into per-resource-type subfolders. This is the canonical
layout (see `#cdk-iac` for the authoritative copy):

```
projects/<project>/<project>-cdk/
├── app.py                      # CDK app entry
├── cdk.json                    # app command + reuse-vs-create context keys
├── requirements.txt            # PINNED deps (aws-cdk-lib, constructs)
├── requirements-dev.txt        # optional dev/test deps
├── README.md                   # bootstrap / synth / diff / deploy notes
├── stacks/<project>_stack.py   # composition root
├── lambda/                     # Lambda constructs + handler code
├── databases/                  # DynamoDB constructs
├── apis/
│   ├── openapi/<domain>.json   # OpenAPI schema artifact
│   └── agentcore/              # AgentCore gateway + target
├── connect/                    # instance, q, integrations, experience, ai, security
└── schemas/                    # shared schema artifacts
```

You can lay this out by hand, or start from `cdk init app --language=python`
and reshape it to match. Either way: pin `aws-cdk-lib` and `constructs`
in `requirements.txt`, install into a project-local `.venv`, and source
account/region from the environment (`CDK_DEFAULT_ACCOUNT` /
`CDK_DEFAULT_REGION`) — never hardcode them.

> Keep the pinned `aws-cdk-lib` and the operator's `cdk` CLI in step. If
> `cdk synth` reports a cloud-assembly "schema version mismatch", upgrade
> the CLI (`npm i -g aws-cdk@latest`) or pin the library down to a version
> the CLI supports.

## Core pattern — reuse before create

Authors frequently already own parts of the chain (a live Connect
instance, an existing AgentCore gateway). For **every** provisionable
dependency, apply this one decision when you author the construct:

```
force_new == True                       -> create a new Cfn* resource
existing_id supplied (not None / blank)  -> reference the existing resource
otherwise                               -> create a new Cfn* resource
```

Read the reuse-vs-create inputs from CDK context (`cdk.json` `context`
or `-c key=value`), e.g. `existing_connect_instance_id`,
`existing_agentcore_gateway_id`, `existing_q_in_connect_domain_id`,
`existing_knowledge_base_id`, `existing_lex_bot_id`, plus a `force_new`
map and `instance_alias` / `industry_domain`.

Author dependent constructs so they bind to whichever resource is in use
without caring whether it was created or referenced — publish the
resolved identifier once and thread it everywhere. A small helper in the
stack keeps this in one place:

```python
def resolve_instance_arn(self) -> str:
    """Reference an existing Connect instance, or create one. Reuse before create."""
    existing = self.node.try_get_context("existing_connect_instance_id")
    force_new = (self.node.try_get_context("force_new") or {}).get("connect_instance")
    if existing and not force_new:
        # Reference: build the ARN from the supplied id; add NO Cfn resource.
        return f"arn:aws:connect:{self.region}:{self.account}:instance/{existing}"
    instance = connect.CfnInstance(
        self, "ConnectInstance",
        identity_management_type="CONNECT_MANAGED",
        instance_alias=self.node.try_get_context("instance_alias") or "<project>",
        attributes=connect.CfnInstance.AttributesProperty(
            inbound_calls=True, outbound_calls=True,
        ),
    )
    return instance.attr_arn
```

**Unresolved-identifier safety:** if a supplied `existing_id` cannot be
resolved to a reachable resource (a pre-flight `aws connect describe-*`
or a `cdk context` lookup fails), report the unresolved identifier and
stop — do **not** silently fall through to creating a duplicate.

## Reference snippets

These are starting points to adapt, not copy-paste-and-ship. Always
confirm property names with `get_cdk_construct_doc` for the
`aws-cdk-lib` version pinned in the project.

### Backend: REST API from an OpenAPI schema

```python
from aws_cdk import aws_apigateway as apigateway

self.api = apigateway.SpecRestApi(
    self, "RestApi",
    api_definition=apigateway.ApiDefinition.from_asset("apis/openapi/<domain>.json"),
)
```

Store the OpenAPI schema under `apis/openapi/<domain>.json`. If the
project's industry-domain config is missing or invalid, emit a minimal
valid schema (a single `GET /health` operation) so the stack still
synthesizes, and report the degraded config to the operator.

### Backend: Lambda + DynamoDB

```python
from aws_cdk import aws_lambda as _lambda, aws_dynamodb as dynamodb, Duration, RemovalPolicy

fn = _lambda.Function(
    self, "GetHotel",
    runtime=_lambda.Runtime.PYTHON_3_12,
    handler="handler.lambda_handler",
    code=_lambda.Code.from_asset("lambda/get_hotel"),
    timeout=Duration.seconds(30),
)

table = dynamodb.Table(
    self, "ReservationsTable",
    partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    removal_policy=RemovalPolicy.DESTROY,   # use RETAIN for data you cannot lose
)
table.grant_read_write_data(fn)
```

### AgentCore gateway as an MCP server (KEY pattern)

Built on the L1 `CfnGateway` + `CfnGatewayTarget` (the only constructs
`aws_cdk.aws_bedrockagentcore` exposes). Two requirement-driven specifics:
a **JWT inbound authorizer** whose discovery URL is derived from the
Connect instance OIDC endpoint, and a **REST-API/OpenAPI target read from
S3**.

The OIDC discovery URL is a pure derivation from the instance alias:

```python
def oidc_discovery_url(instance_alias: str) -> str:
    return f"https://{instance_alias}.my.connect.aws/.well-known/openid-configuration"

# allowed audience for the JWT authorizer == the gateway identifier
```

```python
from aws_cdk import aws_bedrockagentcore as agentcore

gateway = agentcore.CfnGateway(
    self, "McpGateway",
    protocol_type="MCP",
    authorizer_type="CUSTOM_JWT",
    authorizer_configuration={
        "customJwt": {
            "discoveryUrl": oidc_discovery_url(instance_alias),
            "allowedAudience": [gateway_identifier],   # audience == gateway id
        }
    },
    role_arn=gateway_role.role_arn,
)

agentcore.CfnGatewayTarget(
    self, "McpGatewayTarget",
    gateway_identifier=gateway.attr_gateway_identifier,
    target_configuration={
        "mcp": {"openApiSchema": {"s3": {"uri": "s3://<bucket>/<key>"}}}
    },
    credential_provider_configurations=[...],
)
```

Route this through the reuse-before-create pattern (skip both constructs
and use the supplied id when an existing gateway is given). Publish the
resulting MCP backend (gateway id / URL) as a stack output so the AI-agent
config can wire it as an MCP integration tool. Note the
`allowedAudience == gateway id` creates a dependency ordering constraint —
the gateway must own its id before the authorizer audience is finalized
(use `add_dependency` where needed).

### Connect instance, Q in Connect, integrations, experience, AI, security

These are all L1 `Cfn*` — look up exact props with `get_cdk_construct_doc`:

| Resource | Construct(s) | Subfolder |
|---|---|---|
| Connect instance | `connect.CfnInstance` (or referenced) | `connect/` |
| Q in Connect | `wisdom.CfnAssistant` + `CfnAssistantAssociation`; `wisdom.CfnKnowledgeBase` over S3 | `connect/q/` |

> **EXTERNAL S3-backed knowledge base (deploy-tested).** A working,
> reusable `S3KnowledgeBase` construct and the full chain (KMS → S3 bucket
> + `app-integrations.amazonaws.com` read policy → `BucketDeployment` →
> AppIntegrations `CfnDataIntegration` with `source_uri=s3://<bucket>` →
> `wisdom.CfnKnowledgeBase` type `EXTERNAL` → `CfnAssistantAssociation`)
> are documented in `#cdk-q-in-connect` under "Deploy-tested pattern —
> EXTERNAL knowledge base backed by Amazon S3". Two gotchas it captures and
> you MUST respect: (1) the **DataIntegration name must equal the KB name**
> exactly, or the Q-in-Connect console throws "Could not find
> DataIntegration with identifier: <kb name>"; (2) `AWS::Wisdom::KnowledgeBase`
> has **no update path** and the name is unique per account, so a
> replacement collides on the name — rebuild via a two-step deploy (toggle
> the KB off → deploy → on → deploy), not a logical-id rename; (3) **ANY
> in-place update to the KB fails**, including indirect ones — changing the
> KMS key or its policy propagates an UPDATE to the KB ("Update operation is
> not supported") and can leave the stack in `UPDATE_ROLLBACK_FAILED`. Give the
> KB a dedicated KMS key nothing else mutates, and treat the whole chain as
> immutable. Reference
> implementation: `projects/telco-cx/telco-cx-cdk/knowledge_bases/knowledge_base.py`.
> For multiple domains, create one `S3KnowledgeBase` (and one dedicated bucket)
> per KB and point each AI agent / Retrieve tool at the KB id it needs — an
> assistant takes only one KB association, so several KBs surface as several
> Retrieve tools, not several associations.

| Integrations | `connect.CfnIntegrationAssociation` (MCP / Lambda); `lex.CfnBot` + Connect bot association | `connect/integrations/` |
| Experience | `connect.CfnContactFlow` (Content = validated `flow.json`); `connect.CfnView` (from `view.json`) | `connect/experience/` |
| AI config | AI agent, AI prompts, guardrail, AI agent tools (incl. MCP integration tools) | `connect/ai/` |
| Security | `connect.CfnSecurityProfile` | `connect/security/` |

Thread the resolved Connect instance ARN/id into every dependent
association so the whole chain binds to one instance.

### AI agent security profile + assignment (deploy-tested)

A Connect AI agent's tool access is governed by a **security profile** whose
permissions mirror the agent's tools (admin guide: "Assigning security profile
permissions to AI agents"):

| AI agent tool | Permission (API name) |
|---|---|
| Knowledge Base (Retrieve) | `Wisdom.View` |
| Cases (Create/Update/Search) | `Cases.View` / `Cases.Edit` |
| Customer Profiles | `CustomerProfiles.View` |
| Tasks (StartTaskContact) | `Tasks.Create` |

A least-privilege self-service agent whose only data tool is the KB Retrieve
tool needs exactly **`Wisdom.View`**. Reference construct:
`projects/telco-cx/telco-cx-cdk/connect/security_profile.py` (`AiAgentSecurityProfile`).

The profile itself is the L1 `connect.CfnSecurityProfile`. **Assigning** it to
an AI agent has **no CloudFormation property** — it's done via the Connect
`Associate`/`DisassociateSecurityProfiles` APIs, so wrap it in an
`AwsCustomResource` (same pattern as the MCP integration): `on_create`/`on_update`
→ `associateSecurityProfiles`, `on_delete` → `disassociateSecurityProfiles`,
`EntityType="AI_AGENT"`, `EntityArn=<agent arn>`.

Deploy-tested gotchas (each a real failure, fixed in the reference):

- **`CfnSecurityProfile` requires the full instance ARN**, not the bare id
  (`#/InstanceArn: ... does not match pattern arn:aws:connect:...`). Build it
  from `Stack.of(self).region/account` when only an id is supplied.
- **`CfnSecurityProfile.ref` (and the SDK response) is the full profile ARN**,
  but `AssociateSecurityProfiles` wants the **bare profile id**. Extract it
  with `Fn.select(1, Fn.split("/security-profile/", arn))` — passing the ARN
  fails with "Invalid SecurityProfileId".
- **`AssociateSecurityProfiles` validates the AI agent ARN against Wisdom**, so
  the custom-resource role needs **`wisdom:GetAIAgent`** in addition to
  `connect:AssociateSecurityProfiles` / `connect:DisassociateSecurityProfiles`
  ("Missing wisdom:GetAiAgent permissions" otherwise). Use
  `install_latest_aws_sdk=True` — the `AI_AGENT` entity type is new.
- **IAM-propagation vs. auto-rollback deadlock.** The freshly-created CR policy
  may not have propagated to the (shared, possibly warm) custom-resource Lambda
  role at first call → `AccessDenied` on `AssociateSecurityProfiles` even though
  the synthesized policy is correct. With default rollback, each failure
  **deletes the new policy**, so every retry restarts the propagation clock and
  never converges. Deploy once with **`cdk deploy --no-rollback`** so the policy
  persists; the next deploy finds it propagated and succeeds. (General rule: any
  SDK custom resource whose IAM is brand-new can need a `--no-rollback` first
  pass.)

**Security profile names are unique per instance.** To replace a manual profile
with a CDK-managed one without downtime, create the CDK profile under a
*distinct* name, associate it to the agent, then disassociate + delete the old
one. Deleting a profile fails with `ResourceInUseException` while it's assigned
to **any** AI agent version — disassociate the base **and** the
version-qualified ARNs (`:$LATEST`, `:$SAVED`) before deleting.

## Consuming existing artifact bodies (do not re-author)

| Owning skill | Output | Bound into |
|---|---|---|
| `connect-flow-author` | `flow.json` | `CfnContactFlow.content` |
| `connect-view-author` | `view.json` | `CfnView` content |
| `connect-ai-agent-author` | agent + prompt JSON | AI agent / prompt construct bodies |
| `connect-kb-author` | KB source documents | S3 source for `CfnKnowledgeBase` |
| `q-in-connect-bot-deploy` | Lex import bundle | `CfnBot` definition + Connect bot association |

Read these files as construct **inputs**. If a body is missing, direct
the operator to the owning skill rather than re-authoring it.

## Security baseline

- **No secrets in any generated file.** No AWS access keys, secret keys,
  session tokens, or live-account-bound secrets in CDK code, `cdk.json`,
  OpenAPI schemas, or anywhere else. Account/region come from
  `CDK_DEFAULT_ACCOUNT` / `CDK_DEFAULT_REGION` and the operator's AWS
  profile at deploy time.
- After authoring, you can sanity-check generated artifacts with the
  no-secrets scanner helper:

  ```bash
  python .kiro/skills/connect-iac-cdk-author/scripts/secrets_scan.py projects/<project>/<project>-cdk
  ```

  It flags AWS access key ids, secret keys, and session tokens (exit 1
  on any finding). Use it as a guardrail before committing.
- **Credentials come from the operator** at deploy time (`AWS_PROFILE` /
  `aws sso login`). If credentials are missing, report it and write no
  credential material — never embed credentials to "make it work".

## Deploy and verify

Document and run these from the project root with the project `.venv`
active:

```bash
cdk bootstrap   # one-time per account+region
cdk synth       # ALWAYS first — the gate before any deploy
cdk diff        # preview against the deployed stack (on request)
cdk deploy      # provision
```

- **Synth-before-deploy gate:** never deploy a project that does not
  `cdk synth` cleanly. Run `cdk synth`, surface the first synthesis error,
  and do not proceed to `cdk deploy` until it exits 0.
- **`--no-rollback` for brand-new SDK custom-resource IAM.** When a deploy adds
  an `AwsCustomResource` together with the IAM policy that grants its calls, the
  first run can fail with `AccessDenied` due to IAM propagation lag — and
  default rollback then deletes the new policy, so retries never converge. Run
  the first deploy with `cdk deploy --no-rollback` so the policy persists; the
  next deploy finds it propagated and succeeds.
- **On-request `cdk diff`:** don't run it automatically. When the operator
  asks to preview, run `cdk diff` and present the adds/changes/destroys
  (and IAM/security statement changes) before provisioning live Connect
  resources.

## Do not

- Do not write CDK resources from a script — **you** author them per
  project, guided by this skill, the catalogs, and the `cdk_docs` tools.
- Do not re-author flow, view, AI agent, prompt, KB, or Lex bot bodies —
  consume the owning skill's output.
- Do not write AWS credentials, secret keys, or session tokens into any
  file.
- Do not create a duplicate when a supplied existing-resource identifier
  fails to resolve — report it and stop that binding.
- Do not present a project as ready before `cdk synth` succeeds.
