"""
REFERENCE construct (adapt per project) — DynamoDB tables + sample-data
seeding via AwsCustomResource + BatchWriteItem.

The technique (from aws-samples generative-ai-ml-latam-samples): keep sample
data in databases/data/<table>.json in DynamoDB attribute-value format
({"S": "..."}, {"N": "..."}, {"BOOL": true}); a custom resource BatchWriteItem
loads it at deploy time. No seeder Lambda to maintain.

Notes carried from real deploys:
  * BatchWriteItem caps at 25 items per call — batch if you have more.
  * Add a dependency on the table so the write never runs before it exists.
  * Numeric values are strings in attribute-value format ({"N": "42.5"});
    Lambda handlers should convert DynamoDB Decimal back to int/float on read.
  * GSIs for alternate lookups (phone, email, customerId). CloudFormation
    allows only ONE new GSI per update on an EXISTING table — add them one
    deploy at a time; a brand-new table can ship with several at once.
"""

from __future__ import annotations

import json
import os

from aws_cdk import RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import custom_resources as cr
from constructs import Construct

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

_TABLE_CONFIG = dict(
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    removal_policy=RemovalPolicy.DESTROY,  # RETAIN for production data
)


class Tables(Construct):
    """All DynamoDB tables for the project (+ sample data). Telco example."""

    PHONE_INDEX_NAME = "phoneNumber-index"
    EMAIL_INDEX_NAME = "email-index"
    CUSTOMER_INDEX_NAME = "customerId-index"

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        accounts_table_name: str,
        plans_table_name: str,
        cases_table_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # accounts — PK accountId; GSIs for phone and email lookups.
        self.accounts = dynamodb.Table(
            self,
            "AccountsTable",
            table_name=accounts_table_name,
            partition_key=dynamodb.Attribute(
                name="accountId", type=dynamodb.AttributeType.STRING
            ),
            **_TABLE_CONFIG,
        )
        self.accounts.add_global_secondary_index(
            index_name=self.PHONE_INDEX_NAME,
            partition_key=dynamodb.Attribute(
                name="phoneNumber", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        self.accounts.add_global_secondary_index(
            index_name=self.EMAIL_INDEX_NAME,
            partition_key=dynamodb.Attribute(
                name="email", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # plans — PK planId; small catalog.
        self.plans = dynamodb.Table(
            self,
            "PlansTable",
            table_name=plans_table_name,
            partition_key=dynamodb.Attribute(
                name="planId", type=dynamodb.AttributeType.STRING
            ),
            **_TABLE_CONFIG,
        )

        # cases — PK caseId; GSI to list a customer's cases.
        self.cases = dynamodb.Table(
            self,
            "CasesTable",
            table_name=cases_table_name,
            partition_key=dynamodb.Attribute(
                name="caseId", type=dynamodb.AttributeType.STRING
            ),
            **_TABLE_CONFIG,
        )
        self.cases.add_global_secondary_index(
            index_name=self.CUSTOMER_INDEX_NAME,
            partition_key=dynamodb.Attribute(
                name="customerId", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        self._load_sample_data("accounts", self.accounts)
        self._load_sample_data("plans", self.plans)
        self._load_sample_data("cases", self.cases)

    # ------------------------------------------------------------------ #
    def _load_sample_data(self, name: str, table: dynamodb.Table) -> None:
        path = os.path.join(_DATA_DIR, f"{name}.json")
        with open(path, encoding="utf-8") as fh:
            sample = json.load(fh)
        items = sample.get("Items", [])
        if not items:
            return

        parameters = {
            "RequestItems": {
                table.table_name: [{"PutRequest": {"Item": it}} for it in items]
            }
        }
        seeder = cr.AwsCustomResource(
            self,
            f"Seed{name.capitalize()}",
            on_update=cr.AwsSdkCall(
                service="dynamodb",
                action="BatchWriteItem",
                parameters=parameters,
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"seed-{table.table_name}-{len(items)}"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=[table.table_arn]
            ),
        )
        seeder.node.add_dependency(table)

    # ------------------------------------------------------------------ #
    def get_all_tables(self) -> list[dynamodb.Table]:
        return [self.accounts, self.plans, self.cases]
