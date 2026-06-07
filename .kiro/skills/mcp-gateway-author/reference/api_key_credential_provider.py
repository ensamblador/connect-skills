"""
REFERENCE construct (adapt per project) — AgentCore API Key credential
provider, created via a custom resource.

OpenAPI-schema gateway targets require an explicit credential provider. For
API-key auth the provider is an AgentCore *API Key credential provider*, stored
in the Token Vault and exposed by ARN. There is an L1
`CfnApiKeyCredentialProvider`; this reference uses an AwsCustomResource so the
EXTERNAL-secret source and Token-Vault bootstrap are explicit.

Single source of truth: one Secrets Manager secret holds the key and feeds
BOTH the API Gateway ApiKey value AND this provider (apiKeySecretSource=EXTERNAL),
so AgentCore sends exactly the key the API expects. Plaintext never appears in
code or the template.

Three deploy-tested gotchas baked in (see SKILL.md / #cdk-agentcore):
  * install_latest_aws_sdk=True — old runtime SDK drops apiKeySecretSource/
    apiKeySecretConfig and the service then demands a raw apiKey.
  * CreateTokenVault permission — first-ever provider lazily creates the
    account default Token Vault.
  * Secrets Manager + KMS perms — the provider stores the key in a vault secret.
"""

from __future__ import annotations

from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as sm
from aws_cdk import custom_resources as cr
from constructs import Construct


class ApiKeyCredentialProvider(Construct):
    """Creates an AgentCore API Key credential provider from a secret."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        provider_name: str,
        secret: sm.ISecret,
        secret_json_key: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        create_params = {
            "name": provider_name,
            "apiKeySecretSource": "EXTERNAL",
            "apiKeySecretConfig": {
                "secretId": secret.secret_arn,
                "jsonKey": secret_json_key,
            },
        }

        self.resource = cr.AwsCustomResource(
            self,
            "Resource",
            install_latest_aws_sdk=True,  # else apiKeySecretSource is dropped
            on_create=cr.AwsSdkCall(
                service="bedrock-agentcore-control",
                action="createApiKeyCredentialProvider",
                parameters=create_params,
                physical_resource_id=cr.PhysicalResourceId.from_response(
                    "credentialProviderArn"
                ),
            ),
            on_update=cr.AwsSdkCall(
                service="bedrock-agentcore-control",
                action="createApiKeyCredentialProvider",
                parameters=create_params,
                physical_resource_id=cr.PhysicalResourceId.from_response(
                    "credentialProviderArn"
                ),
            ),
            on_delete=cr.AwsSdkCall(
                service="bedrock-agentcore-control",
                action="deleteApiKeyCredentialProvider",
                parameters={"name": provider_name},
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=[
                            "bedrock-agentcore:CreateApiKeyCredentialProvider",
                            "bedrock-agentcore:DeleteApiKeyCredentialProvider",
                            "bedrock-agentcore:GetApiKeyCredentialProvider",
                            "bedrock-agentcore:CreateTokenVault",
                            "bedrock-agentcore:GetTokenVault",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        actions=["secretsmanager:GetSecretValue"],
                        resources=[secret.secret_arn],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "secretsmanager:CreateSecret",
                            "secretsmanager:TagResource",
                            "secretsmanager:DescribeSecret",
                            "secretsmanager:PutSecretValue",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "kms:CreateKey",
                            "kms:Decrypt",
                            "kms:GenerateDataKey",
                        ],
                        resources=["*"],
                    ),
                ]
            ),
        )
        self.resource.node.add_dependency(secret)

    @property
    def credential_provider_arn(self) -> str:
        return self.resource.get_response_field("credentialProviderArn")
