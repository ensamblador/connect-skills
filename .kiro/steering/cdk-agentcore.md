---
inclusion: manual
last_refreshed: 2026-09-10
construct_count: 26
source_urls:
  - https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore.html
content_checksum: sha256:983396a263655855
---

# CDK construct catalog — Bedrock AgentCore (`aws_cdk.aws_bedrockagentcore`)

Quick lookup table for the L1 `Cfn*` constructs in the
`aws_cdk.aws_bedrockagentcore` module. For Connect IaC the two that matter
most are **`CfnGateway`** and **`CfnGatewayTarget`**: together they expose a
REST API (described by an OpenAPI schema read from S3) as an MCP server that
a Connect AI agent consumes as an MCP integration.

**Activation:** this file is opt-in. Reference it from chat with
`#cdk-agentcore` when you're choosing CDK constructs to provision Bedrock AgentCore
resources in a `CDK_Project`.

**Freshness rule (for the agent):** before relying on this catalog,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 7 days, run
``uv run python .kiro/scripts/refresh_cdk_docs.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.
A regenerated file with no diff is fine — `last_refreshed` is the only
thing that needs updating, and the script handles that automatically.

**L1 baseline:** this module also ships hand-written L2 constructs (`Gateway`, `GatewayTarget`, `Runtime`, `Memory`, …) in `aws-cdk-lib`, but this catalog lists the automatically generated `Cfn*` (CloudFormation) constructs that are the stable provisioning baseline for the IaC skill. An L2-only `aws-bedrock-agentcore-alpha` package also exists but is not a hard dependency here.

For depth on any construct (full property list, examples), follow the
construct name link. For the per-construct deep dive from chat, call the
`get_cdk_construct_doc` MCP tool (or run ``cdk-construct-doc`` from a
terminal) with the construct name.

| Construct | Description |
| --- | --- |
| [CfnGateway](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnGateway.html) | Provisions a Bedrock AgentCore gateway that fronts backend tools as an MCP server (the MCP_Server_Backend). |
| [CfnGatewayTarget](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnGatewayTarget.html) | Defines a target hosted by a gateway (Lambda, OpenAPI/REST, Smithy, or MCP server) — the REST-API/OpenAPI target read from S3. |
| [CfnRuntime](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnRuntime.html) | Provisions an AgentCore Runtime — the containerized execution environment for an agent. |
| [CfnRuntimeEndpoint](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnRuntimeEndpoint.html) | Creates a stable endpoint that points at a specific AgentCore Runtime version. |
| [CfnMemory](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnMemory.html) | Provisions AgentCore Memory (short-term and long-term) so agents retain context. |
| [CfnBrowserCustom](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnBrowserCustom.html) | Provisions a custom AgentCore browser tool with your own configuration. |
| [CfnBrowserProfile](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnBrowserProfile.html) | Defines a reusable browser profile for AgentCore browser sessions. |
| [CfnCodeInterpreterCustom](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnCodeInterpreterCustom.html) | Provisions a custom AgentCore code-interpreter sandbox. |
| [CfnApiKeyCredentialProvider](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnApiKeyCredentialProvider.html) | Stores an API-key outbound credential provider in the AgentCore Token Vault. |
| [CfnOAuth2CredentialProvider](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnOAuth2CredentialProvider.html) | Stores an OAuth2 outbound credential provider in the AgentCore Token Vault. |
| [CfnPaymentCredentialProvider](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnPaymentCredentialProvider.html) | Stores a payment credential provider in the AgentCore Token Vault. |
| [CfnWorkloadIdentity](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnWorkloadIdentity.html) | Defines the stable workload identity of an agent in the account's identity directory. |
| [CfnPolicy](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnPolicy.html) | Defines an AgentCore authorization policy. |
| [CfnPolicyEngine](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnPolicyEngine.html) | Provisions a policy engine that evaluates AgentCore authorization policies. |
| [CfnEvaluator](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnEvaluator.html) | Defines an evaluator (LLM-as-a-judge or code-based) for assessing agent performance. |
| [CfnOnlineEvaluationConfig](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnOnlineEvaluationConfig.html) | Configures continuous online evaluation of live agent traffic. |
| [CfnDataset](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnDataset.html) | Defines a dataset used by AgentCore evaluation. |
| [CfnHarness](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnHarness.html) | Defines an AgentCore harness for agent testing and orchestration. |
| [CfnConfigurationBundle](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnConfigurationBundle.html) | _(new construct — run `get_cdk_construct_doc` and curate a description)_ |
| [CfnPaymentConnector](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnPaymentConnector.html) | _(new construct — run `get_cdk_construct_doc` and curate a description)_ |
| [CfnPaymentManager](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnPaymentManager.html) | _(new construct — run `get_cdk_construct_doc` and curate a description)_ |
| [CfnResourcePolicy](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnResourcePolicy.html) | _(new construct — run `get_cdk_construct_doc` and curate a description)_ |
| [CfnCapacityProvider](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnCapacityProvider.html) | _(new construct — run `get_cdk_construct_doc` and curate a description)_ |
| [CfnGatewayRateLimit](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnGatewayRateLimit.html) | _(new construct — run `get_cdk_construct_doc` and curate a description)_ |
| [CfnGatewayRule](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnGatewayRule.html) | _(new construct — run `get_cdk_construct_doc` and curate a description)_ |
| [CfnHarnessEndpoint](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnHarnessEndpoint.html) | _(new construct — run `get_cdk_construct_doc` and curate a description)_ |

## Hard-won deploy learnings (CfnGateway / CfnGatewayTarget)

These are verified, deploy-tested gotchas from wiring an AgentCore MCP
gateway over an API Gateway REST API. Each maps to a real `UPDATE_FAILED` /
`CREATE_FAILED` we hit; following them avoids the same loop.

### Gateway authorizer (CfnGateway)

- **JWT class name is `CustomJWTAuthorizerConfigurationProperty`** (JWT
  uppercase) under `AuthorizerConfigurationProperty(custom_jwt_authorizer=...)`,
  with `authorizer_type="CUSTOM_JWT"` and `protocol_type="MCP"`.
- **`allowedAudience` must equal the gateway's own generated id** when the
  token issuer is Amazon Connect (verified against the reference gateway:
  its allowedAudience is its own full id, e.g.
  `anycompany-hotels-mcp-server-y52jleukt3`). The id only exists after
  creation → it cannot be its own input in one deploy (circular dependency).
  Two ways out:
  - **Two-phase:** deploy once with a placeholder audience (the gateway
    name), read the real id from the `McpGatewayId` output, set it in config,
    redeploy.
  - **Single deploy:** after the gateway exists, an `AwsCustomResource` calls
    `bedrock-agentcore-control:UpdateGateway` with
    `allowedAudience=[<gateway id via Fn::GetAtt GatewayIdentifier>]`.
    `UpdateGateway` is a **full-replace** call — re-send `name`, `roleArn`,
    `protocolType`, `authorizerType`, and the complete
    `authorizerConfiguration`, not just the changed field.
- **`*` is not a valid `allowedAudience`** and would defeat the authorizer;
  the audience is set by the token issuer (Connect), not chosen freely.
- Discovery URL is the Connect instance OIDC endpoint:
  `https://<instance-alias>.my.connect.aws/.well-known/openid-configuration`.

### Gateway target (CfnGatewayTarget) — two ways to feed the schema

- **Native API Gateway target** (`McpTargetConfigurationProperty(api_gateway=
  ApiGatewayTargetConfigurationProperty(rest_api_id, stage, ...))`): the
  gateway reads API Gateway's **auto-exported** OpenAPI. Requirements that
  bite on deploy:
  - `api_gateway_tool_configuration` is **required**, and its `tool_filters`
    list is **required** (each filter needs `filter_path` + `methods`).
  - A single `filter_path="/*"` collapses every operation into **one
    catch-all tool**. Use **one filter per operation** (exact path) so each
    becomes its own MCP tool.
  - The exported schema only carries what API Gateway exports: a proxy
    integration yields **no request/response body schemas** and `content: {}`.
    Every method must declare `method_responses` (else the export has no
    `responses` → "responses is missing") and an `operation_name` (exported
    as `operationId` → else "has no operationId and no override provided").
  - Tool **descriptions** come from `tool_overrides`
    (`ApiGatewayToolOverrideProperty(method, path, name, description)`) — the
    native export has none.
- **Inline OpenAPI target** (`McpTargetConfigurationProperty(open_api_schema=
  ApiSchemaConfigurationProperty(inline_payload="<spec string>"))`): embed a
  rich, hand-authored OpenAPI document (descriptions, typed request/response
  schemas, examples). `inline_payload` is a **single string** (serialize the
  authored YAML to JSON). Render the server URL with `Fn.sub` so
  `${ApiId}`/`${Stage}` resolve to the real deployed API at deploy time.

### Target type and credential gotchas

- **Target config type is immutable.** You cannot update a target's config
  from `apiGateway` to `openApiSchema` in place
  ("Target configuration cannot be updated from apiGateway to openApiSchema").
  Give the new target a **different logical id / name** to force a
  create-new + delete-old replacement.
- **OpenAPI-schema targets require an explicit credential provider** — a bare
  `credential_provider_type="GATEWAY_IAM_ROLE"` fails with
  "IamCredentialProvider is required for openApiSchema targets...". Provide a
  real provider:
  - **IAM:** `GATEWAY_IAM_ROLE` + `iam_credential_provider(service="execute-api")`.
  - **API key:** `credential_provider_type="API_KEY"` +
    `api_key_credential_provider(provider_arn=..., credential_location="HEADER",
    credential_parameter_name="x-api-key")`.

### API Key credential provider (when using API_KEY)

- There is an L1 `CfnApiKeyCredentialProvider`, but creating it via an
  `AwsCustomResource` calling `createApiKeyCredentialProvider` was used here.
  Lessons:
  - **First-ever provider lazily creates the account's default Token Vault**,
    so the caller needs `bedrock-agentcore:CreateTokenVault` (+ `GetTokenVault`)
    on top of the credential-provider actions — else
    "not authorized to perform: bedrock-agentcore:CreateTokenVault".
  - Set **`install_latest_aws_sdk=True`** on the custom resource. The default
    Lambda runtime SDK is too old to know `apiKeySecretSource` /
    `apiKeySecretConfig`, drops them silently, and the service then demands a
    raw `apiKey` ("ApiKey is required when secret source is MANAGED or not
    specified").
  - Use `apiKeySecretSource="EXTERNAL"` with `apiKeySecretConfig={secretId,
    jsonKey}` so the key value comes from one Secrets Manager secret — the
    SAME secret that seeds the API Gateway ApiKey value, so both ends agree.

## Registering the gateway as a Connect MCP integration

Connecting a gateway to Amazon Connect as an MCP server is **not** a Lex/Lambda
`CfnIntegrationAssociation` (that L1 only accepts `LEX_BOT | LAMBDA_FUNCTION`).
It is a **third-party APPLICATION** integration done in two API calls — no
native construct exists, so both go through `AwsCustomResource`:

1. `appintegrations:CreateApplication` with `ApplicationType=MCP_SERVER`,
   `ApplicationSourceConfig.ExternalUrlConfig.AccessUrl` = the gateway MCP URL
   (`https://<id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp`), and
   **`Namespace` = the gateway ID exactly** (any other value →
   "Namespace for MCP server applications must be a valid Bedrock Agent Core
   Gateway ID"). Returns the application ARN.
2. `connect:CreateIntegrationAssociation` with `IntegrationType=APPLICATION`
   and `IntegrationArn` = that application ARN.

Prereq enforced by Connect: the instance must be configured with the gateway's
Discovery URL, and a gateway maps to exactly one instance / one MCP server.

Deploy-tested gotchas (each a real failure):

- **`install_latest_aws_sdk=True`** on both custom resources — `MCP_SERVER` and
  the APPLICATION association are too new for the default Lambda runtime SDK.
- **`DeleteApplication` takes the ARN**, so set the application custom
  resource's physical id to `from_response("Arn")` (not `Id`), or teardown
  fails.
- **IAM (undocumented for these preview APIs) — the set that worked:**
  - Step 1 also needs **`bedrock-agentcore:GetGateway`** — CreateApplication
    validates the namespace against the real gateway ("Missing permissions to
    access gateway" otherwise).
  - Step 2 also needs **`app-integrations:CreateApplicationAssociation`** —
    Connect creates an application association on the app internally
    ("not authorized to perform: app-integrations:CreateApplicationAssociation"
    otherwise).
  - Step 2 also needs **`iam:CreateServiceLinkedRole` / `PutRolePolicy`** on
    `arn:aws:iam::*:role/aws-service-role/connect.amazonaws.com/*` — associating
    an APPLICATION updates Connect's service-linked role ("Access denied
    updating the Amazon Connect service-linked role" otherwise).
- **Manual + CDK collide**: the app namespace (= gateway id) is unique. If you
  created the app/association by hand (e.g. CLI validation), delete them before
  the stack creates them, or you hit `DuplicateResourceException`.

The `Application` API is in preview; shapes may change. See the
`mcp-gateway-author` skill (`reference/mcp_integration.py`) for the full
deploy-tested construct.
