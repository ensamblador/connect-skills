---
inclusion: manual
last_refreshed: 2026-09-10
construct_count: 12
source_urls:
  - https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom.html
content_checksum: sha256:0241a74145314c49
---

# CDK construct catalog — Q in Connect / Wisdom (`aws_cdk.aws_wisdom`)

Quick lookup table for the AWS CDK (Python) constructs in the
`aws_cdk.aws_wisdom` module — Amazon Q in Connect (Wisdom): the assistant,
knowledge base, AI agents, prompts, and guardrails that give a Connect
deployment its retrieval and generative-AI surface.

**Activation:** this file is opt-in. Reference it from chat with
`#cdk-q-in-connect` when you're choosing CDK constructs to provision Q in Connect (Wisdom)
resources in a `CDK_Project`.

**Freshness rule (for the agent):** before relying on this catalog,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 7 days, run
``uv run python .kiro/scripts/refresh_cdk_docs.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.
A regenerated file with no diff is fine — `last_refreshed` is the only
thing that needs updating, and the script handles that automatically.

**L1-only:** `aws_cdk.aws_wisdom` ships no hand-written L2 constructs — every entry below is an automatically generated `Cfn*` (CloudFormation) construct, used exactly as you would the matching `AWS::Wisdom::*` resource.

For depth on any construct (full property list, examples), follow the
construct name link. For the per-construct deep dive from chat, call the
`get_cdk_construct_doc` MCP tool (or run ``cdk-construct-doc`` from a
terminal) with the construct name.

| Construct | Description |
| --- | --- |
| [CfnAssistant](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnAssistant.html) | Provisions a Q in Connect (Wisdom) assistant — the AI domain a Connect instance binds to. |
| [CfnAssistantAssociation](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnAssistantAssociation.html) | Associates a knowledge base with a Q in Connect assistant. |
| [CfnKnowledgeBase](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnKnowledgeBase.html) | Provisions a Q in Connect knowledge base (for example backed by an Amazon S3 document source). |
| [CfnAIAgent](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnAIAgent.html) | Defines a Q in Connect AI agent (for example answer-recommendation or self-service). |
| [CfnAIAgentVersion](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnAIAgentVersion.html) | Publishes an immutable, numbered version of a Q in Connect AI agent. |
| [CfnAIPrompt](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnAIPrompt.html) | Defines a prompt template used by a Q in Connect AI agent. |
| [CfnAIPromptVersion](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnAIPromptVersion.html) | Publishes an immutable, numbered version of an AI prompt. |
| [CfnAIGuardrail](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnAIGuardrail.html) | Defines a guardrail that constrains a Q in Connect AI agent's responses. |
| [CfnAIGuardrailVersion](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnAIGuardrailVersion.html) | Publishes an immutable, numbered version of an AI guardrail. |
| [CfnMessageTemplate](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnMessageTemplate.html) | Defines a reusable message template for the assistant. |
| [CfnMessageTemplateVersion](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnMessageTemplateVersion.html) | Publishes an immutable, numbered version of a message template. |
| [CfnQuickResponse](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_wisdom/CfnQuickResponse.html) | Defines a quick response stored in a knowledge base. |

---

## Deploy-tested pattern — EXTERNAL knowledge base backed by Amazon S3

Provision an EXTERNAL Q in Connect knowledge base whose documents live in an
S3 bucket. Validated end-to-end in `projects/telco-cx` (account 111122223333,
us-west-2). The reusable construct lives at
`projects/telco-cx/telco-cx-cdk/knowledge_bases/knowledge_base.py`
(`S3KnowledgeBase`).

### Resource chain (must be created in this order)

```
KMS key
   |
S3 bucket  (+ bucket policy granting app-integrations.amazonaws.com read)
   |  BucketDeployment uploads the local HTML entries
   v
AppIntegrations DataIntegration   (SourceURI = s3://<bucket>)
   |
   v
Wisdom CfnKnowledgeBase (type EXTERNAL, source = the DataIntegration ARN)
   |
   v
CfnAssistantAssociation (type KNOWLEDGE_BASE)  -> existing assistant
```

### Construct-by-construct notes

- **`CfnDataIntegration`** (`aws_cdk.aws_appintegrations`): for an S3 source,
  set `source_uri = f"s3://{bucket_name}"` and OMIT the file/object
  configuration entirely (it must be null for S3). Pass `kms_key` = the same
  KMS key ARN used by the bucket and KB.
- **`CfnKnowledgeBase`** (`aws_cdk.aws_wisdom`): `knowledge_base_type="EXTERNAL"`;
  `source_configuration` → `AppIntegrationsConfigurationProperty(app_integration_arn=...)`;
  `server_side_encryption_configuration` → `kms_key_id` = KMS key ARN.
- **Bucket policy**: the AppIntegrations crawler reads the bucket as the
  service principal `app-integrations.amazonaws.com`. Grant it
  `s3:ListBucket`, `s3:GetObject`, `s3:GetBucketLocation` on the bucket and
  its objects, or the KB syncs nothing.
- **Content types**: the S3/EXTERNAL crawler ingests HTML (and other text
  document formats) but NOT `text/csv`. Convert tabular sources to HTML
  before upload.
- **Ingestion is async**: after deploy the KB syncs from S3 automatically;
  `list-contents` may return `[]` for a few minutes before the entries show
  up `ACTIVE`. This is expected, not a failure.

### CRITICAL gotcha — DataIntegration name MUST equal the KB name

The Amazon Q in Connect **console** resolves a KB's integration by looking up
a DataIntegration whose identifier (Name) is EXACTLY the KB name. If you name
the DataIntegration anything else (e.g. a `-source` suffix), the KB still works
functionally (sync + retrieval are fine) but clicking the KB integration in the
console throws:

```
Could not find DataIntegration with identifier: <kb name>
```

Fix: name the DataIntegration identical to the KB (`name=self._name` in
`S3KnowledgeBase`).

### CRITICAL gotcha — ANY in-place update to the KB fails (incl. its KMS key)

`AWS::Wisdom::KnowledgeBase` supports **no update operation at all** — not just
the source/name. If CloudFormation tries to *modify* an existing KB in place
(rather than replace it), the resource handler rejects it immediately:

```
Resource handler returned message: "Update operation is not supported."
(HandlerErrorCode: InvalidRequest)
```

The trap is that the trigger is often **indirect**. The KB references its KMS
key (`ServerSideEncryptionConfiguration.kmsKeyId`), so **changing the KMS key
or its key policy propagates an update attempt to the KB** — even though you
never touched the KB construct. A real failure we hit: adding an unrelated
resource that modified the shared KMS key's policy →
`AWS::KMS::Key` updated fine → CloudFormation then issued an UPDATE to the KB →
"Update operation is not supported" → stack went to `UPDATE_FAILED`, and the
rollback (which is also an update of the KB) failed again →
`UPDATE_ROLLBACK_FAILED`.

Reassuring detail: the update is rejected up front, so AWS **never mutates the
KB** — it stays `ACTIVE` and intact. Only the stack is stuck.

**Recovery from `UPDATE_ROLLBACK_FAILED`:**
- `aws cloudformation continue-update-rollback --stack-name <stack>
  --resources-to-skip <KbLogicalId>` — skipping the un-rollbackable KB unblocks
  the stack (the KB was never changed, so skipping it is safe).
- The stack may also reach `UPDATE_ROLLBACK_COMPLETE` on its own; if so,
  `continue-update-rollback` returns "cannot be called from current stack
  status", which just means it already finished.
- After recovery, run `cdk diff` — it should report **no differences** once the
  offending change is reverted.

**Prevention:** give the KB (and its KMS key) a dedicated key that nothing else
mutates, and treat the whole KB chain as immutable — any real change to the KB,
its key, or its source must go through the two-step rebuild below, never an
in-place update.

### CRITICAL gotcha — KB rename/replacement collides on the unique name

`AWS::Wisdom::KnowledgeBase` has **no update path**, and the KB name is unique
per account. Any change that forces a KB *replacement* (e.g. changing the
DataIntegration ARN/name the KB sources from, or renaming the construct's CDK
logical id) makes CloudFormation try to **create the new KB before deleting the
old one** — and the new KB collides on the still-in-use name:

```
Name is already in use (Service: QConnect, Status Code: 409) AlreadyExists
```

The collision-free rebuild is a **two-step deploy** driven by a config toggle
(do NOT just rename the logical id):

1. Set `BUILD_KNOWLEDGE_BASE = False` and deploy → CloudFormation deletes the
   whole KB chain (delete IS supported). Verified clean: association → KB →
   DataIntegration → bucket → KMS all removed.
2. Set `BUILD_KNOWLEDGE_BASE = True` and deploy → CloudFormation recreates the
   chain with the corrected DataIntegration name (== KB name).

Keep the construct's CDK id STABLE (`"KnowledgeBase"`) across both steps; the
toggle, not a logical-id bump, is what avoids the create-before-delete
collision.

### Associating with an existing assistant

`CfnAssistantAssociation(assistant_id=<existing>, association_type="KNOWLEDGE_BASE",
association=AssociationDataProperty(knowledge_base_id=<kb id>))`. Add an
explicit `node.add_dependency(knowledge_base)` so the association waits for the
KB. This is what lets the AI agent's Retrieve tool query the KB.

### Multiple knowledge bases — one bucket per KB

The S3 DataIntegration `SourceURI` is **the whole bucket** (`s3://<bucket>`).
AppIntegrations has **no prefix/object filter** for S3 — `FileConfiguration`,
`ObjectConfiguration`, and `ScheduleConfig` must be null. Consequence: a KB
pointed at a bucket ingests **every object in it**, across all prefixes. A
prefix does NOT scope what a KB crawls.

Because of that, the simple, clean model is **one dedicated bucket per KB**
(the `S3KnowledgeBase` default). To serve several domains, create several
`S3KnowledgeBase` instances — each gets its own KMS key, bucket, DataIntegration
and KB id. Then point each AI agent / Retrieve tool at the **KB id** it needs.

Surfacing several KBs to one agent: a Q in Connect **assistant supports only
ONE knowledge-base association** (`CreateAssistantAssociation` →
*"An assistant can have only a single association"*). So multiple KBs are
exposed as **multiple Retrieve tools** on an orchestration AI agent (named
`Retrieve`, `Retrieve2`, `RetrieveProducts`, ...), with prompt rules for
parallel ("invoke ALL simultaneously") or conditional ("select ONE per
question") invocation. See the admin guide:
https://docs.aws.amazon.com/connect/latest/adminguide/multiple-knowledge-base-setup-and-content-segmentation.html

> Content-level segmentation within a single shared bucket/KB (upload under a
> prefix, tag each content item via the Connect `TagResource` API, then filter
> in the Retrieve tool with `retrievalConfiguration.filter.equals.key/.value`)
> is a documented alternative, but it adds a polling custom resource to wait
> for async ingestion before tagging. We deliberately keep it OUT of
> `S3KnowledgeBase` to avoid over-complication — prefer one bucket per KB and
> distinct KB ids per agent.

