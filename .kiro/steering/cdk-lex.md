---
inclusion: manual
last_refreshed: 2026-06-04
construct_count: 4
source_urls:
  - https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lex.html
content_checksum: sha256:371caec2d5fbd262
---

# CDK construct catalog — Amazon Lex V2 (`aws_cdk.aws_lex`)

Quick lookup table for the AWS CDK (Python) constructs in the
`aws_cdk.aws_lex` module — used to provision the Lex bot that a Connect
instance associates as a Lex integration.

**Activation:** this file is opt-in. Reference it from chat with
`#cdk-lex` when you're choosing CDK constructs to provision Amazon Lex V2
resources in a `CDK_Project`.

**Freshness rule (for the agent):** before relying on this catalog,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 7 days, run
``uv run python .kiro/hooks/scripts/refresh_cdk_docs.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.
A regenerated file with no diff is fine — `last_refreshed` is the only
thing that needs updating, and the script handles that automatically.

**L1-only:** `aws_cdk.aws_lex` ships no hand-written L2 constructs — every entry below is an automatically generated `Cfn*` (CloudFormation) construct, used exactly as you would the matching `AWS::Lex::*` resource.

For depth on any construct (full property list, examples), follow the
construct name link. For the per-construct deep dive from chat, call the
`get_cdk_construct_doc` MCP tool (or run ``cdk-construct-doc`` from a
terminal) with the construct name.

| Construct | Description |
| --- | --- |
| [CfnBot](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lex/CfnBot.html) | Provisions an Amazon Lex V2 bot, including its locales, intents, and slot types. |
| [CfnBotAlias](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lex/CfnBotAlias.html) | Creates an alias that points at a Lex bot version for stable deployment and Connect association. |
| [CfnBotVersion](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lex/CfnBotVersion.html) | Publishes an immutable, numbered version of a Lex bot. |
| [CfnResourcePolicy](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lex/CfnResourcePolicy.html) | Attaches a resource-based IAM policy to a Lex bot or bot alias. |
