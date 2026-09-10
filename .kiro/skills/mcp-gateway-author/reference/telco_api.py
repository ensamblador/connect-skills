"""
REFERENCE construct (adapt per project) — API Gateway REST API with the method
conventions the AgentCore gateway requires, plus API-key/usage-plan wiring.

This is the telco example. The conventions that MATTER (carry these to any
project), each one a deploy-tested requirement:

  * Every method declares `method_responses` (else exported OpenAPI has no
    `responses` → target fails "responses is missing").
  * Every method declares `operation_name` (exported as `operationId`, becomes
    the MCP tool name → else "has no operationId and no override provided").
  * One operationId per path+method. Two lookups on the same collection need
    distinct paths: here `/accounts?phoneNumber=` (getAccountByPhone) and
    `/accounts/by-email?email=` (getAccountByEmail). A literal segment
    (`by-email`) also takes routing priority over a `{param}` sibling.
  * API key: the key VALUE comes from one Secrets Manager secret (the single
    source of truth), so the SAME value feeds the AgentCore credential
    provider. Plaintext never lands in code or the template.
"""

from __future__ import annotations

from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_lambda as aws_lambda
from aws_cdk import aws_secretsmanager as sm
from constructs import Construct

_DEFAULT_METHOD_RESPONSES = [
    apigw.MethodResponse(status_code="200"),
    apigw.MethodResponse(status_code="201"),
    apigw.MethodResponse(status_code="400"),
    apigw.MethodResponse(status_code="404"),
]

# JSON field name inside the Secrets Manager secret that holds the
# generated API key. This is a field name, not a credential.
API_KEY_JSON_FIELD = "apiKey"

# Empty JSON object the generator merges the generated key into.
_EMPTY_JSON_TEMPLATE = "{}"


class TelcoApi(Construct):
    """REST API for the telco self-service backend (example)."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        api_name: str,
        stage_name: str,
        accounts_fn: aws_lambda.IFunction,
        plans_fn: aws_lambda.IFunction,
        cases_fn: aws_lambda.IFunction,
        require_api_key: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._require_api_key = require_api_key

        self.api = apigw.RestApi(
            self,
            "RestApi",
            rest_api_name=api_name,
            description="Telco self-service backend (accounts, plans, support).",
            deploy_options=apigw.StageOptions(stage_name=stage_name),
            endpoint_types=[apigw.EndpointType.REGIONAL],
        )

        accounts_i = apigw.LambdaIntegration(accounts_fn)
        plans_i = apigw.LambdaIntegration(plans_fn)
        cases_i = apigw.LambdaIntegration(cases_fn)

        # ---- /accounts ----
        accounts = self.api.root.add_resource("accounts")
        self._add_method(
            accounts, "GET", accounts_i,
            operation_name="getAccountByPhone",
            request_parameters={"method.request.querystring.phoneNumber": False},
        )
        account = accounts.add_resource("{accountId}")
        self._add_method(account, "GET", accounts_i, operation_name="getAccount")
        self._add_method(
            account.add_resource("balance"), "GET", accounts_i,
            operation_name="getAccountBalance",
        )
        # literal segment beats {accountId} for routing
        self._add_method(
            accounts.add_resource("by-email"), "GET", accounts_i,
            operation_name="getAccountByEmail",
            request_parameters={"method.request.querystring.email": False},
        )

        # ---- /plans ----
        plans = self.api.root.add_resource("plans")
        self._add_method(
            plans, "GET", plans_i,
            operation_name="listPlans",
            request_parameters={"method.request.querystring.minGb": False},
        )
        self._add_method(
            plans.add_resource("{planId}"), "GET", plans_i, operation_name="getPlan"
        )

        # ---- /support ----
        support = self.api.root.add_resource("support")
        self._add_method(support, "POST", cases_i, operation_name="openCase")
        self._add_method(
            support, "GET", cases_i,
            operation_name="listCustomerCases",
            request_parameters={"method.request.querystring.customerId": False},
        )
        self._add_method(
            support.add_resource("{caseId}"), "GET", cases_i, operation_name="getCase"
        )

        self.api_key_secret: sm.Secret | None = None
        if require_api_key:
            self._set_up_api_key()

    # ------------------------------------------------------------------ #
    def _add_method(
        self,
        resource: apigw.IResource,
        http_method: str,
        integration: apigw.Integration,
        *,
        operation_name: str,
        request_parameters: dict[str, bool] | None = None,
    ) -> apigw.Method:
        return resource.add_method(
            http_method,
            integration,
            operation_name=operation_name,
            request_parameters=request_parameters,
            method_responses=_DEFAULT_METHOD_RESPONSES,
            api_key_required=self._require_api_key,
        )

    # ------------------------------------------------------------------ #
    def _set_up_api_key(self) -> None:
        self.api_key_secret = sm.Secret(
            self,
            "ApiKeySecret",
            description="API key (API Gateway + AgentCore).",
            generate_secret_string=sm.SecretStringGenerator(
                secret_string_template=_EMPTY_JSON_TEMPLATE,
                generate_string_key=API_KEY_JSON_FIELD,
                exclude_punctuation=True,
                password_length=40,
            ),
        )
        key_value = self.api_key_secret.secret_value_from_json(
            API_KEY_JSON_FIELD
        ).unsafe_unwrap()

        self.api_key = self.api.add_api_key(
            "ApiKey", api_key_name="telco-selfservice-api-key", value=key_value
        )
        self.usage_plan = self.api.add_usage_plan(
            "UsagePlan", name="telco-selfservice-usage-plan"
        )
        self.usage_plan.add_api_key(self.api_key)
        self.usage_plan.add_api_stage(stage=self.api.deployment_stage)

    # ------------------------------------------------------------------ #
    @property
    def rest_api_id(self) -> str:
        return self.api.rest_api_id

    @property
    def stage_name(self) -> str:
        return self.api.deployment_stage.stage_name
