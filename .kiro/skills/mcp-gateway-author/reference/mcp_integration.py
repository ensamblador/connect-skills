"""
REFERENCE construct (adapt per project) — register an AgentCore MCP gateway as
an Amazon Connect instance integration. DEPLOY-TESTED end to end.

This is NOT a Lex/Lambda IntegrationAssociation. `connect.CfnIntegrationAssociation`
only accepts LEX_BOT | LAMBDA_FUNCTION, so the MCP server is wired as a
THIRD-PARTY APPLICATION, in two steps (both via custom resources — there is no
native CDK construct for an AppIntegrations MCP_SERVER application):

  1. appintegrations CreateApplication, ApplicationType=MCP_SERVER:
       * AccessUrl = the gateway's MCP URL (https://<id>.gateway.bedrock-
                     agentcore.<region>.amazonaws.com/mcp)
       * Namespace = the gateway ID **EXACTLY** (verified: any other value
                     fails "Namespace for MCP server applications must be a
                     valid Bedrock Agent Core Gateway ID")
     -> returns the application ARN.
  2. connect CreateIntegrationAssociation, IntegrationType=APPLICATION,
     IntegrationArn = that application ARN -> associates it to the instance.

Prereq (enforced by Connect): the instance must be configured with the
gateway's Discovery URL; a gateway maps to exactly one instance / one MCP
server. The `Application` API is in preview; shapes may change.

IAM permissions — discovered one-by-one across real deploys (these preview
APIs do not document their full IAM surface). The set below is what made a
clean deploy:
  * Step 1 needs bedrock-agentcore:GetGateway — CreateApplication validates the
    namespace (= gateway id) against the real gateway ("Missing permissions to
    access gateway" otherwise).
  * Step 2 needs app-integrations:CreateApplicationAssociation — Connect's
    CreateIntegrationAssociation internally creates an application association
    on the AppIntegrations app.
  * Step 2 needs iam:CreateServiceLinkedRole/PutRolePolicy on the Connect SLR —
    associating an APPLICATION updates Connect's service-linked role ("Access
    denied updating the Amazon Connect service-linked role" otherwise).

Also note: DeleteApplication takes the ARN, so the application custom
resource's physical id is set to the ARN (from_response("Arn")), not the Id.
"""

from __future__ import annotations

from aws_cdk import aws_iam as iam
from aws_cdk import custom_resources as cr
from constructs import Construct


class McpServerIntegration(Construct):
    """Registers an AgentCore MCP gateway as a Connect APPLICATION integration."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        instance_id: str,
        gateway_id: str,
        gateway_mcp_url: str,
        application_name: str,
        description: str = "",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---- Step 1: AppIntegrations MCP_SERVER application ----
        create_app_params = {
            "Name": application_name,
            "Namespace": gateway_id,  # MUST be the gateway id
            "ApplicationType": "MCP_SERVER",
            "ApplicationSourceConfig": {
                "ExternalUrlConfig": {"AccessUrl": gateway_mcp_url}
            },
        }
        if description:
            create_app_params["Description"] = description

        self.application = cr.AwsCustomResource(
            self,
            "Application",
            install_latest_aws_sdk=True,  # MCP_SERVER type is new in the SDK
            on_create=cr.AwsSdkCall(
                service="appintegrations",
                action="createApplication",
                parameters=create_app_params,
                # physical id = ARN, because DeleteApplication takes the ARN.
                physical_resource_id=cr.PhysicalResourceId.from_response("Arn"),
            ),
            on_update=cr.AwsSdkCall(
                service="appintegrations",
                action="createApplication",
                parameters=create_app_params,
                physical_resource_id=cr.PhysicalResourceId.from_response("Arn"),
            ),
            on_delete=cr.AwsSdkCall(
                service="appintegrations",
                action="deleteApplication",
                parameters={"Arn": cr.PhysicalResourceIdReference()},
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=[
                            "app-integrations:CreateApplication",
                            "app-integrations:DeleteApplication",
                            "app-integrations:GetApplication",
                            "app-integrations:TagResource",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "bedrock-agentcore:GetGateway",
                            "bedrock-agentcore:ListGateways",
                        ],
                        resources=["*"],
                    ),
                ]
            ),
        )
        self.application_arn = self.application.get_response_field("Arn")

        # ---- Step 2: associate the application to the Connect instance ----
        self.association = cr.AwsCustomResource(
            self,
            "Association",
            install_latest_aws_sdk=True,
            on_create=cr.AwsSdkCall(
                service="connect",
                action="createIntegrationAssociation",
                parameters={
                    "InstanceId": instance_id,
                    "IntegrationType": "APPLICATION",
                    "IntegrationArn": self.application_arn,
                },
                physical_resource_id=cr.PhysicalResourceId.from_response(
                    "IntegrationAssociationId"
                ),
            ),
            on_delete=cr.AwsSdkCall(
                service="connect",
                action="deleteIntegrationAssociation",
                parameters={
                    "InstanceId": instance_id,
                    "IntegrationAssociationId": cr.PhysicalResourceIdReference(),
                },
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=[
                            "connect:CreateIntegrationAssociation",
                            "connect:DeleteIntegrationAssociation",
                            "app-integrations:GetApplication",
                            "app-integrations:CreateApplicationAssociation",
                            "app-integrations:DeleteApplicationAssociation",
                            "app-integrations:ListApplicationAssociations",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "iam:CreateServiceLinkedRole",
                            "iam:PutRolePolicy",
                            "iam:AttachRolePolicy",
                            "iam:GetRole",
                        ],
                        resources=[
                            "arn:aws:iam::*:role/aws-service-role/connect.amazonaws.com/*"
                        ],
                    ),
                ]
            ),
        )
        self.association.node.add_dependency(self.application)

    @property
    def integration_association_id(self) -> str:
        return self.association.get_response_field("IntegrationAssociationId")
