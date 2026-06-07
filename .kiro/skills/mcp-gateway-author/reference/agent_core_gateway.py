"""
REFERENCE construct (adapt per project) — Bedrock AgentCore gateway that
exposes a REST API as an MCP server.

This is a deploy-tested reference for the mcp-gateway-author skill. Copy it
into your project's agent_core/ folder and adjust names. Confirm property
names with get_cdk_construct_doc for your pinned aws-cdk-lib version.

Only two L1 resources exist in aws_cdk.aws_bedrockagentcore for this:
`CfnGateway` and `CfnGatewayTarget`. The construct supports BOTH target types
(native API Gateway and inline OpenAPI) and resolves the audience-equals-own-id
circularity (two-phase OR a single-deploy UpdateGateway custom resource).

See the skill SKILL.md and #cdk-agentcore steering for the why behind each
decision.
"""

from __future__ import annotations

from aws_cdk import Fn, Stack
from aws_cdk import aws_bedrockagentcore as bedrockagentcore
from aws_cdk import aws_iam as iam
from aws_cdk import custom_resources as cr
from constructs import Construct


class AgentCoreGateway(Construct):
    """AgentCore MCP gateway fronting a REST API."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        name: str,
        discovery_url: str,
        audience: str | None = None,
        auto_audience: bool = False,
        description: str = "",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._name = name
        self._discovery_url = discovery_url
        self._description = description
        self._auto_audience = auto_audience
        # auto-audience: create with NAME as placeholder; patch to real id.
        self._audience = name if auto_audience else (audience or name)

        self.create_gateway(name, description)
        if auto_audience:
            self._patch_audience_to_self()

    # ------------------------------------------------------------------ #
    def create_role(self) -> None:
        stk = Stack.of(self)
        self.role = iam.Role(
            self,
            "BedrockGatewayRole",
            assumed_by=iam.ServicePrincipal(
                service="bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": stk.account},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{stk.region}:{stk.account}:*"
                    },
                },
            ),  # type: ignore[arg-type]
            description="Role the AgentCore gateway assumes to invoke its targets.",
        )
        self.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:*",
                    "bedrock:*",
                    "agent-credential-provider:*",
                    "iam:PassRole",
                    "secretsmanager:GetSecretValue",
                    "execute-api:Invoke",
                ],
                resources=["*"],
            )
        )

    # ------------------------------------------------------------------ #
    def create_gateway(self, name: str, description: str = "") -> None:
        self.create_role()
        self.gateway = bedrockagentcore.CfnGateway(
            self,
            "Gateway",
            name=name,
            protocol_type="MCP",
            role_arn=self.role.role_arn,
            authorizer_type="CUSTOM_JWT",
            authorizer_configuration=bedrockagentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=bedrockagentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=self._discovery_url,
                    allowed_audience=[self._audience],
                )
            ),
            description=description,
        )
        self.gateway.node.add_dependency(self.role)

    # ------------------------------------------------------------------ #
    def _patch_audience_to_self(self) -> None:
        """Single-deploy fix for audience == own id. UpdateGateway is a
        full-replace call, so re-send the whole config."""
        gateway_id = self.gateway.attr_gateway_identifier
        update_params = {
            "gatewayIdentifier": gateway_id,
            "name": self._name,
            "roleArn": self.role.role_arn,
            "protocolType": "MCP",
            "authorizerType": "CUSTOM_JWT",
            "authorizerConfiguration": {
                "customJWTAuthorizer": {
                    "discoveryUrl": self._discovery_url,
                    "allowedAudience": [gateway_id],
                }
            },
        }
        if self._description:
            update_params["description"] = self._description

        self.audience_patch = cr.AwsCustomResource(
            self,
            "AudiencePatch",
            on_create=cr.AwsSdkCall(
                service="bedrock-agentcore-control",
                action="updateGateway",
                parameters=update_params,
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"audience-patch-{gateway_id}"
                ),
            ),
            on_update=cr.AwsSdkCall(
                service="bedrock-agentcore-control",
                action="updateGateway",
                parameters=update_params,
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"audience-patch-{gateway_id}"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["bedrock-agentcore:UpdateGateway"],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        actions=["iam:PassRole"],
                        resources=[self.role.role_arn],
                    ),
                ]
            ),
        )
        self.audience_patch.node.add_dependency(self.gateway)

    # ------------------------------------------------------------------ #
    def add_api_gateway_target(
        self,
        target_name: str,
        rest_api_id: str,
        stage: str,
        *,
        operations: list[dict],
        description: str = "",
    ) -> bedrockagentcore.CfnGatewayTarget:
        """NATIVE API Gateway target. `operations` = one dict per op
        ({path, method, name, description}) → one tool_filter + tool_override
        each, so every op is its own named, described MCP tool."""
        tool_filters = [
            bedrockagentcore.CfnGatewayTarget.ApiGatewayToolFilterProperty(
                filter_path=op["path"], methods=[op["method"]]
            )
            for op in operations
        ]
        tool_overrides = [
            bedrockagentcore.CfnGatewayTarget.ApiGatewayToolOverrideProperty(
                method=op["method"],
                path=op["path"],
                name=op["name"],
                description=op.get("description", ""),
            )
            for op in operations
        ]
        target = bedrockagentcore.CfnGatewayTarget(
            self,
            f"Target-{target_name}",
            name=target_name.replace("_", "-") + "-target",
            gateway_identifier=self.gateway.attr_gateway_identifier,
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    api_gateway=bedrockagentcore.CfnGatewayTarget.ApiGatewayTargetConfigurationProperty(
                        rest_api_id=rest_api_id,
                        stage=stage,
                        api_gateway_tool_configuration=bedrockagentcore.CfnGatewayTarget.ApiGatewayToolConfigurationProperty(
                            tool_filters=tool_filters,
                            tool_overrides=tool_overrides,
                        ),
                    )
                )
            ),
            description=description[:200],
        )
        target.node.add_dependency(self.gateway)
        return target

    # ------------------------------------------------------------------ #
    def add_openapi_inline_target(
        self,
        target_name: str,
        *,
        spec_json_template: str,
        rest_api_id: str,
        stage: str,
        api_key_provider_arn: str,
        api_key_header_name: str = "x-api-key",
        description: str = "",
    ) -> bedrockagentcore.CfnGatewayTarget:
        """INLINE OpenAPI target. `spec_json_template` is the authored spec as
        a JSON string whose server URL still has ${ApiId}/${Stage} markers;
        Fn.sub resolves them to the deployed API here. Requires an explicit
        credential provider (API key shown)."""
        rendered_payload = Fn.sub(
            spec_json_template, {"ApiId": rest_api_id, "Stage": stage}
        )
        target = bedrockagentcore.CfnGatewayTarget(
            self,
            f"Target-{target_name}",
            name=target_name.replace("_", "-") + "-target",
            gateway_identifier=self.gateway.attr_gateway_identifier,
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="API_KEY",
                    credential_provider=bedrockagentcore.CfnGatewayTarget.CredentialProviderProperty(
                        api_key_credential_provider=bedrockagentcore.CfnGatewayTarget.ApiKeyCredentialProviderProperty(
                            provider_arn=api_key_provider_arn,
                            credential_location="HEADER",
                            credential_parameter_name=api_key_header_name,
                        )
                    ),
                )
            ],
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    open_api_schema=bedrockagentcore.CfnGatewayTarget.ApiSchemaConfigurationProperty(
                        inline_payload=rendered_payload,
                    )
                )
            ),
            description=description[:200],
        )
        target.node.add_dependency(self.gateway)
        return target

    # ------------------------------------------------------------------ #
    @property
    def gateway_id(self) -> str:
        return self.gateway.attr_gateway_identifier

    @property
    def gateway_url(self) -> str:
        return self.gateway.attr_gateway_url
