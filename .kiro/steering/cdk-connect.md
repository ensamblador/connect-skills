---
inclusion: manual
last_refreshed: 2026-09-10
construct_count: 37
source_urls:
  - https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/README.html
content_checksum: sha256:c380b961d4186067
---

# CDK construct catalog — Amazon Connect (`aws_cdk.aws_connect`)

Quick lookup table for the AWS CDK (Python) constructs in the
`aws_cdk.aws_connect` module — the ones an IaC author uses to provision a
Connect instance and everything that associates to it (flows, views,
queues, routing profiles, users, security profiles, integrations).

**Activation:** this file is opt-in. Reference it from chat with
`#cdk-connect` when you're choosing CDK constructs to provision Amazon Connect
resources in a `CDK_Project`.

**Freshness rule (for the agent):** before relying on this catalog,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 7 days, run
``uv run python .kiro/scripts/refresh_cdk_docs.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.
A regenerated file with no diff is fine — `last_refreshed` is the only
thing that needs updating, and the script handles that automatically.

**L1-only:** `aws_cdk.aws_connect` ships no hand-written L2 constructs — every entry below is an automatically generated `Cfn*` (CloudFormation) construct, used exactly as you would the matching `AWS::Connect::*` resource.

For depth on any construct (full property list, examples), follow the
construct name link. For the per-construct deep dive from chat, call the
`get_cdk_construct_doc` MCP tool (or run ``cdk-construct-doc`` from a
terminal) with the construct name.

| Construct | Description |
| --- | --- |
| [CfnInstance](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnInstance.html) | Provisions an Amazon Connect instance (the contact center) that every other Connect resource associates to. |
| [CfnInstanceStorageConfig](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnInstanceStorageConfig.html) | Configures a storage destination (S3, Kinesis) for an instance's data such as recordings or reports. |
| [CfnIntegrationAssociation](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnIntegrationAssociation.html) | Associates an external resource (Lex bot, Lambda function, Wisdom/Q in Connect assistant, etc.) with the instance. |
| [CfnContactFlow](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnContactFlow.html) | Provisions a contact flow on the instance from its validated Flow language `Content`. |
| [CfnContactFlowVersion](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnContactFlowVersion.html) | Publishes an immutable, numbered version of a contact flow. |
| [CfnContactFlowModule](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnContactFlowModule.html) | Provisions a reusable contact flow module that other flows can invoke. |
| [CfnContactFlowModuleAlias](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnContactFlowModuleAlias.html) | Creates a named alias that points at a specific contact flow module version. |
| [CfnContactFlowModuleVersion](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnContactFlowModuleVersion.html) | Publishes an immutable, numbered version of a contact flow module. |
| [CfnView](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnView.html) | Provisions a view (UI template) used by the Show view block in step-by-step guided experiences. |
| [CfnViewVersion](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnViewVersion.html) | Publishes an immutable, numbered version of a view. |
| [CfnHoursOfOperation](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnHoursOfOperation.html) | Defines the hours of operation referenced by queues. |
| [CfnQueue](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnQueue.html) | Defines a routing queue on the instance. |
| [CfnQuickConnect](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnQuickConnect.html) | Defines a quick connect (a transfer destination for agents). |
| [CfnRoutingProfile](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnRoutingProfile.html) | Defines a routing profile that links queues to the agents who serve them. |
| [CfnUser](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnUser.html) | Provisions a Connect user (agent or admin) on the instance. |
| [CfnUserHierarchyGroup](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnUserHierarchyGroup.html) | Defines a node in the instance's agent hierarchy. |
| [CfnUserHierarchyStructure](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnUserHierarchyStructure.html) | Defines the levels (depth) of the instance's agent hierarchy. |
| [CfnSecurityProfile](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnSecurityProfile.html) | Defines a security profile (the permission set granted to agents). |
| [CfnSecurityKey](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnSecurityKey.html) | Associates a security key (public key) used for encrypting instance data. |
| [CfnApprovedOrigin](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnApprovedOrigin.html) | Allowlists an origin domain that is permitted to embed the Connect instance. |
| [CfnAgentStatus](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnAgentStatus.html) | Defines a custom agent status (for example Available or Offline) for the instance. |
| [CfnPredefinedAttribute](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnPredefinedAttribute.html) | Defines a predefined attribute used by routing criteria. |
| [CfnPrompt](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnPrompt.html) | Uploads an audio prompt that flows can play to callers. |
| [CfnPhoneNumber](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnPhoneNumber.html) | Claims a phone number for the instance or a traffic distribution group. |
| [CfnTrafficDistributionGroup](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnTrafficDistributionGroup.html) | Creates a traffic distribution group for cross-Region phone-number routing. |
| [CfnRule](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnRule.html) | Defines an automation rule triggered by contact or analytics events. |
| [CfnNotification](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnNotification.html) | Configures a notification (for example an email alert) for the instance. |
| [CfnEmailAddress](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnEmailAddress.html) | Provisions an email address for the instance's email channel. |
| [CfnEvaluationForm](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnEvaluationForm.html) | Defines a contact evaluation form used in quality management. |
| [CfnTaskTemplate](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnTaskTemplate.html) | Defines a reusable task template for the task channel. |
| [CfnDataTable](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnDataTable.html) | Creates a data table for storing key-value data that flows read and write. |
| [CfnDataTableAttribute](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnDataTableAttribute.html) | Defines an attribute (column) on a Connect data table. |
| [CfnDataTableRecord](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnDataTableRecord.html) | Writes a record (row) into a Connect data table. |
| [CfnWorkspace](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnWorkspace.html) | Provisions an agent workspace resource for the instance. |
| [CfnDataLakeAssociation](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnDataLakeAssociation.html) | _(new construct — run `get_cdk_construct_doc` and curate a description)_ |
| [CfnTestCase](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnTestCase.html) | _(new construct — run `get_cdk_construct_doc` and curate a description)_ |
| [CfnMetric](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnMetric.html) | _(new construct — run `get_cdk_construct_doc` and curate a description)_ |
