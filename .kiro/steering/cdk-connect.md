---
inclusion: manual
last_refreshed: 2026-10-29
construct_count: 39
source_urls:
  - https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect-readme.html
content_checksum: sha256:36117e4d14391a9e
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
| [CfnInstance](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnInstance.html?lang=python) | Provisions an Amazon Connect instance (the contact center) that every other Connect resource associates to. |
| [CfnInstanceStorageConfig](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnInstanceStorageConfig.html?lang=python) | Configures a storage destination (S3, Kinesis) for an instance's data such as recordings or reports. |
| [CfnIntegrationAssociation](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnIntegrationAssociation.html?lang=python) | Associates an external resource (Lex bot, Lambda function, Wisdom/Q in Connect assistant, etc.) with the instance. |
| [CfnContactFlow](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnContactFlow.html?lang=python) | Provisions a contact flow on the instance from its validated Flow language `Content`. |
| [CfnContactFlowVersion](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnContactFlowVersion.html?lang=python) | Publishes an immutable, numbered version of a contact flow. |
| [CfnContactFlowModule](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnContactFlowModule.html?lang=python) | Provisions a reusable contact flow module that other flows can invoke. |
| [CfnContactFlowModuleAlias](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnContactFlowModuleAlias.html?lang=python) | Creates a named alias that points at a specific contact flow module version. |
| [CfnContactFlowModuleVersion](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnContactFlowModuleVersion.html?lang=python) | Publishes an immutable, numbered version of a contact flow module. |
| [CfnView](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnView.html?lang=python) | Provisions a view (UI template) used by the Show view block in step-by-step guided experiences. |
| [CfnViewVersion](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnViewVersion.html?lang=python) | Publishes an immutable, numbered version of a view. |
| [CfnHoursOfOperation](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnHoursOfOperation.html?lang=python) | Defines the hours of operation referenced by queues. |
| [CfnQueue](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnQueue.html?lang=python) | Defines a routing queue on the instance. |
| [CfnQuickConnect](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnQuickConnect.html?lang=python) | Defines a quick connect (a transfer destination for agents). |
| [CfnRoutingProfile](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnRoutingProfile.html?lang=python) | Defines a routing profile that links queues to the agents who serve them. |
| [CfnUser](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnUser.html?lang=python) | Provisions a Connect user (agent or admin) on the instance. |
| [CfnUserHierarchyGroup](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnUserHierarchyGroup.html?lang=python) | Defines a node in the instance's agent hierarchy. |
| [CfnUserHierarchyStructure](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnUserHierarchyStructure.html?lang=python) | Defines the levels (depth) of the instance's agent hierarchy. |
| [CfnSecurityProfile](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnSecurityProfile.html?lang=python) | Defines a security profile (the permission set granted to agents). |
| [CfnSecurityKey](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnSecurityKey.html?lang=python) | Associates a security key (public key) used for encrypting instance data. |
| [CfnApprovedOrigin](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnApprovedOrigin.html?lang=python) | Allowlists an origin domain that is permitted to embed the Connect instance. |
| [CfnAgentStatus](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnAgentStatus.html?lang=python) | Defines a custom agent status (for example Available or Offline) for the instance. |
| [CfnPredefinedAttribute](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnPredefinedAttribute.html?lang=python) | Defines a predefined attribute used by routing criteria. |
| [CfnPrompt](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnPrompt.html?lang=python) | Uploads an audio prompt that flows can play to callers. |
| [CfnPhoneNumber](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnPhoneNumber.html?lang=python) | Claims a phone number for the instance or a traffic distribution group. |
| [CfnTrafficDistributionGroup](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnTrafficDistributionGroup.html?lang=python) | Creates a traffic distribution group for cross-Region phone-number routing. |
| [CfnRule](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnRule.html?lang=python) | Defines an automation rule triggered by contact or analytics events. |
| [CfnNotification](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnNotification.html?lang=python) | Configures a notification (for example an email alert) for the instance. |
| [CfnEmailAddress](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnEmailAddress.html?lang=python) | Provisions an email address for the instance's email channel. |
| [CfnEvaluationForm](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnEvaluationForm.html?lang=python) | Defines a contact evaluation form used in quality management. |
| [CfnTaskTemplate](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnTaskTemplate.html?lang=python) | Defines a reusable task template for the task channel. |
| [CfnDataTable](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnDataTable.html?lang=python) | Creates a data table for storing key-value data that flows read and write. |
| [CfnDataTableAttribute](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnDataTableAttribute.html?lang=python) | Defines an attribute (column) on a Connect data table. |
| [CfnDataTableRecord](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnDataTableRecord.html?lang=python) | Writes a record (row) into a Connect data table. |
| [CfnWorkspace](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnWorkspace.html?lang=python) | Provisions an agent workspace resource for the instance. |
| [CfnDataLakeAssociation](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnDataLakeAssociation.html?lang=python) | Associates one analytics data lake dataset of the instance with a target account, by default the instance's own. Cross-account sharing goes through AWS RAM. |
| [CfnTestCase](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnTestCase.html?lang=python) | Creates a flow test case on the instance: its JSON content, entry point, initialization data and `SAVED` or `PUBLISHED` status. |
| [CfnMetric](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnMetric.html?lang=python) | Creates a custom metric on the instance: its calculation, display unit, trend direction and `PUBLISHED` or `SAVED` status. |
| [CfnUseCase](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnUseCase.html?lang=python) | Creates a use case for an integration association, `RULES_EVALUATION` or `CONNECT_CAMPAIGNS`. Each association takes at most one use case of each type. |
| [CfnVocabulary](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect.CfnVocabulary.html?lang=python) | Creates a custom vocabulary for one language on the instance. Contact Lens uses the language's default vocabulary in post-call and real-time analysis. |
