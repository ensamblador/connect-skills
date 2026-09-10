---
inclusion: manual
last_refreshed: 2026-09-10
source_urls:
  - https://docs.aws.amazon.com/connect/latest/adminguide/connect-ai-agent.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/ai-agent-initial-setup.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/customize-connect-ai-agents.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/default-ai-system.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/create-ai-agents.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/ai-agent-configure-language-support.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/use-orchestration-ai-agent.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/create-ai-prompts.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/agentic-self-service-prompt-best-practices.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/ai-agent-mcp-tools.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/agentic-self-service.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/agentic-assistance.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/ai-agent-security-profile-permissions.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/integrate-guides-with-ai-agents.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/multiple-knowledge-base-setup-and-content-segmentation.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/access-connect-assistant-in-workspace.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/use-generative-ai-case-summarization.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/ai-generated-note-taking.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/monitor-ai-agents.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/ts-ai-agents-self-service.html
source_checksums:
  https://docs.aws.amazon.com/connect/latest/adminguide/connect-ai-agent.html: sha256:0ec7ff94d9e5167c
  https://docs.aws.amazon.com/connect/latest/adminguide/ai-agent-initial-setup.html: sha256:cccd20611369ab16
  https://docs.aws.amazon.com/connect/latest/adminguide/customize-connect-ai-agents.html: sha256:103b423cead63b8e
  https://docs.aws.amazon.com/connect/latest/adminguide/default-ai-system.html: sha256:6d7bd982bf3f4541
  https://docs.aws.amazon.com/connect/latest/adminguide/create-ai-agents.html: sha256:377309a8616ef453
  https://docs.aws.amazon.com/connect/latest/adminguide/ai-agent-configure-language-support.html: sha256:1145f8800026d2ae
  https://docs.aws.amazon.com/connect/latest/adminguide/use-orchestration-ai-agent.html: sha256:d621b9a5d5091844
  https://docs.aws.amazon.com/connect/latest/adminguide/create-ai-prompts.html: sha256:1f4f269412b01e5f
  https://docs.aws.amazon.com/connect/latest/adminguide/agentic-self-service-prompt-best-practices.html: sha256:4a343878af482275
  https://docs.aws.amazon.com/connect/latest/adminguide/ai-agent-mcp-tools.html: sha256:b81a569dba392935
  https://docs.aws.amazon.com/connect/latest/adminguide/agentic-self-service.html: sha256:a769fd5c3d499b11
  https://docs.aws.amazon.com/connect/latest/adminguide/agentic-assistance.html: sha256:e63315394bd25bea
  https://docs.aws.amazon.com/connect/latest/adminguide/ai-agent-security-profile-permissions.html: sha256:2eb84a4f3af64d3c
  https://docs.aws.amazon.com/connect/latest/adminguide/integrate-guides-with-ai-agents.html: sha256:07ff5438151fb6e4
  https://docs.aws.amazon.com/connect/latest/adminguide/multiple-knowledge-base-setup-and-content-segmentation.html: sha256:08a32979f94e98c3
  https://docs.aws.amazon.com/connect/latest/adminguide/access-connect-assistant-in-workspace.html: sha256:87ec7db461062fdd
  https://docs.aws.amazon.com/connect/latest/adminguide/use-generative-ai-case-summarization.html: sha256:757a19f7b3de562c
  https://docs.aws.amazon.com/connect/latest/adminguide/ai-generated-note-taking.html: sha256:14a05554bafd4b93
  https://docs.aws.amazon.com/connect/latest/adminguide/monitor-ai-agents.html: sha256:af3dddc666f643bc
  https://docs.aws.amazon.com/connect/latest/adminguide/ts-ai-agents-self-service.html: sha256:6199f5572154e4a3
---

# Connect AI agents reference

Distilled reference for designing, configuring, and troubleshooting
Connect AI agents (the Bedrock-backed agentic feature, formerly
"Q in Connect"). Use this when you're picking an agent type, wiring
tools, drafting prompts, debugging behavior, or aligning language
across the IVR.

**Activation:** opt-in. Reference from chat with `#connect-ai-agents`
when scoping a self-service or agent-assistance use case, choosing
between agent types, writing or copying prompts, configuring tools
and security profiles, or reading orchestration logs.

**Freshness rule (for the agent):** before relying on this reference,
compare the `last_refreshed` date in the front matter with today's
date. If the file is older than 7 days, run
``uv run python .kiro/scripts/refresh_connect_ai_agents.py`` to refresh it
before answering. Always refresh when the user explicitly asks for it.
Unlike the other steering catalogs, this file is hand-curated prose —
the refresh script bumps `last_refreshed` and reports any source-page
drift, but it does not rewrite the body. When drift is reported, re-read
the changed pages and update the prose by hand before re-running the
script.

**Pair with:**
- `#connect-blocks` for the flow blocks that wire AI agents in
  (`Connect assistant`, `Get customer input`, `Set voice`,
  `Set contact attributes`).
- `#connect-flow-language` for the matching Action types
  (`CreateWisdomSession`, `MessageParticipant`,
  `UpdateContactTextToSpeechVoice`, `CheckAttribute`).
- `#connect-views` when integrating step-by-step guides with knowledge
  base content for human-agent assistance.
- `.kiro/skills/q-in-connect-bot-deploy/lex_skills/q_in_connect_passthrough/`
  for the Lex bot template whose locales must align with the AI agent
  locale (see [Language alignment](#language-alignment-critical) below).

For depth on any topic, follow the source link. The
`mcp_connect_knowledge` `search_docs` tool is the best way to pull
live admin-guide pages when this file falls short.


## Mental model

Connect AI agents is a single feature with two distinct modes:

1. **Agentic self-service** — AI agent talks directly to the end
   customer over voice/chat in a `Get customer input` block. Replaces
   the legacy "self-service" mode where the agent would return control
   to the flow on every tool call.
2. **Agentic assistance** — AI agent helps the human agent during
   live contacts (auto-recommendations, manual search, note taking,
   case summarization, email response). Surfaces in the **Connect
   assistant** panel inside the agent workspace.

Both modes share the same building blocks:

| Block | What it is |
|---|---|
| **Domain (Assistant)** | A container that owns one knowledge base plus the AI agents that operate against it. One Connect instance maps to exactly one domain. |
| **Knowledge base** | A data integration (S3, Salesforce, ServiceNow, ZenDesk, SharePoint Online, Web Crawler, or Bedrock KB). One per domain via the console; multiple via API/Retrieve tools. HTML/DOCX/PDF/UTF-8 text, ≤1 MB each. |
| **AI prompt** | YAML-ish task description for the LLM. System defaults are read-only — copy them to customize. |
| **AI guardrail** | Bedrock guardrail filtering harmful content, redacting PII, and limiting hallucination. |
| **AI agent** | The runtime resource. Binds an agent **type** (use case) to one or more **prompt versions**, an optional **guardrail**, a **locale**, an optional **knowledge base association** override, and (for orchestration types) **tools** and a **security profile**. |
| **Tools** | Callable capabilities. Three flavors: out-of-the-box (Cases, Customer Profiles, Tasks, Knowledge Base Retrieve), Flow-module-as-tool, and MCP (via Bedrock AgentCore Gateway). |


## Agent types

Pick one type per agent. Each type drives a different set of prompts.
The `Self-service` legacy type is being superseded by `Orchestration`
with a self-service prompt — prefer `Orchestration` for new builds.

| Type | Purpose | Prompts it drives | Locale configurable |
|---|---|---|---|
| `Orchestration` | Multi-step agentic loop. Used for both self-service and agent-assistance orchestration. Can chain tool calls and reason across turns. | `AgentAssistanceOrchestration` or `SelfServiceOrchestration` | yes |
| `AnswerRecommendation` | Auto intent-based recommendations pushed to a human agent. | `IntentLabelingGeneration`, `QueryReformulation`, `AnswerGeneration` | yes |
| `ManualSearch` | Human agent types a query into the assistant panel. | `AnswerGeneration` | yes |
| `Self-service` (legacy) | Customer-facing Q&A that returns to the flow on each tool call. | `SelfServicePreProcessing`, `SelfServiceAnswerGeneration` | English only |
| `EmailResponse` | Drafts agent reply for an email contact. | `EmailResponse` | yes |
| `EmailOverview` | Summarizes an email thread. | `EmailOverview` | yes |
| `EmailGenerativeAnswer` | KB-grounded answer for an email contact. | `EmailGenerativeAnswer` | yes |
| `NoteTaking` | Generates structured contact notes. Invoked as a tool by `AgentAssistanceOrchestrator`. | `NoteTaking` | yes |
| `CaseSummarization` | Summarizes a Case (fields, comments, SLAs, related transcripts). | `CaseSummarization` | yes |
| `SalesAgent` | Identifies sales opportunities mid-conversation. | `SalesAgent` | yes |

**Defaulting & precedence:**
- System defaults exist for every type and ship with an Connect instance
  the first time a domain is created.
- A custom AI agent **version** (immutable, like AI prompts) overrides
  the default once you call `update-assistant-ai-agent` or set it via
  the **AI Agents** page **Default AI Agent Configurations** panel.
- A session-scoped override (`update-session --ai-agent-configuration`)
  beats the assistant-level default. Use a Lambda block to set this
  per-queue / per-segment.
- `--origin SYSTEM` on `list-ai-agents` lists the system defaults, so
  you can revert by re-pointing at them.


## Default AI prompts catalog

System prompts you can copy from but not edit in place. Names line up
with the prompt-type values in CloudWatch logs.

| Prompt | Used by | Notes |
|---|---|---|
| `AgentAssistanceOrchestration` | `Orchestration` (assistance) | Multi-turn loop. Must enforce `<message>` tags. |
| `SelfServiceOrchestration` | `Orchestration` (self-service) | `<message>` tags + `core_behavior` section. |
| `AnswerGeneration` | `AnswerRecommendation`, `ManualSearch` | Reads `$.query` and `$.contentExcerpt`. |
| `IntentLabelingGeneration` | `AnswerRecommendation` | Generates the intent list shown to the agent. |
| `QueryReformulation` | `AnswerRecommendation` | Builds the KB query from the live transcript. |
| `SelfServicePreProcessing` | `Self-service` (legacy) | Routes between conversation / task / answer. |
| `SelfServiceAnswerGeneration` | `Self-service` (legacy) | English only. |
| `EmailResponse`, `EmailOverview`, `EmailGenerativeAnswer`, `EmailQueryReformulation` | Email-* types | Email-aware, locale-aware. |
| `NoteTaking` | `NoteTaking` agent | Returns HTML notes. Driven by the `GenerateNotes` tool. |
| `CaseSummarization` | `CaseSummarization` | Reads case fields + activity feed + 30-day transcripts. |
| `SalesAgent` | `SalesAgent` | Sales-opportunity heuristic. |


## Initial setup (Console + IAM)

Order matters — agents can't bind to a knowledge base that doesn't
exist yet.

1. **Create the domain.** Connect Customer console → instance →
   **AI Agents** → **Add domain**. One domain per Connect instance.
2. **Encrypt the domain.** Default AWS-owned key, an existing CMK, or
   a new symmetric KMS key. **Chat / task / email require** the
   `connect.amazonaws.com` service principal to have
   `kms:Decrypt`, `kms:GenerateDataKey*`, and `kms:DescribeKey` on the
   key. Forgetting this is the most common chat-broken symptom.
3. **Add an integration (knowledge base).** S3, Salesforce, ServiceNow
   (versioning required), ZenDesk, SharePoint Online (AUTHORIZATION_CODE
   only), Web Crawler (respects robots.txt; 1-hour default timeout;
   1-300 URLs/host/min). Sync frequency defaults to 1 hour. Quotas at
   `connect-ai-agents-quotas`.
4. **Wire the flow.** Add a **Connect assistant** block early in the
   inbound flow, before the contact reaches the agent. The block
   creates the AI session and pins the domain. Without it, neither
   self-service nor assistance can run for that contact.
5. **Assign permissions.** See [Security profiles](#security-profiles)
   below.

**Cross-region inference:** Connect AI agents uses Bedrock
cross-region inference profiles (e.g., `us.anthropic.claude-...`) so
calls fan out across the region's geo. No customer-facing toggle —
just be aware when reading model_id in logs.


## Customizing an agent

Recommended path:

1. Copy a system AI prompt → tweak the YAML → publish a **version**.
2. Copy a system AI agent of the right type → swap in your prompt
   versions, set the **locale**, attach an **AI guardrail** if needed,
   and (for `Orchestration`) attach **tools** and a **security
   profile** → publish a version.
3. Set the new agent version as the default for its use case (or
   override per-session via Lambda).

**Important publishing rules:**
- AI prompts and AI agents are versioned. Runtime always uses a
  published `<id>:<version>` qualifier.
- Default system prompts cannot be edited — copying is the only path.
- Partial overrides are supported on multi-prompt types
  (`AnswerRecommendation`, `Self-service`, `EmailResponse`,
  `EmailGenerativeAnswer`): override one prompt and the others fall
  back to system defaults.

**Knowledge-base override on the agent (CLI):**
`associationConfigurations[].knowledgeBaseAssociationConfigurationData`
lets you pin `overrideKnowledgeBaseSearchType` (`SEMANTIC` or
`HYBRID`), `maxResults`, and a `contentTagFilter`. Use this instead of
prompt edits when the only thing that varies between agents is which
KB or how to filter it.


## Tools (Orchestration agents only)

Tools turn an agent from "answers questions" into "takes actions".
Three types in two execution modes:

**Tools the agent calls during the conversation (no flow exit):**
- **MCP tools** — third-party tools surfaced through Bedrock AgentCore
  Gateway. **30-second per-call timeout.** Use for order lookups,
  refund processing, CRM updates.
- **Out-of-the-box** — Cases (Create / Update / Search), Customer
  Profiles, Knowledge Base (`Retrieve`), Tasks (`StartTaskContact`).
  Permissions mirror the matching human-agent permissions.
- **Flow-module-as-tool** — wrap an existing flow module in a tool
  shell. Reuses business logic across static and generative flows.
- **Constant** — returns a static string. Stub tool for prompt
  iteration before the real backend exists.

**Tools that exit the loop and hand control back to the flow:**
- **Return to Control** — ends the AI conversation, stores the tool
  name in Lex `Tool` session attribute and the input parameters as
  Lex session attributes. The `SelfServiceOrchestrator` ships with
  `Complete` (end the call) and `Escalate` (transfer to human). You
  can replace either with a custom version that captures additional
  context (sentiment, escalation reason, summary, etc.) — see source
  doc for the canonical schema example.

**Tool configuration knobs (per tool, per agent):**
- **Instructions** — natural-language guidance on when and how to use
  this tool. Add example invocations.
- **Override input values** — force-set parameter values at invoke
  time. Common pattern for `Retrieve` tools to pin a tag filter:
  `retrievalConfiguration.filter.equals.key` /
  `retrievalConfiguration.filter.equals.value`.
- **Filter output values** — narrow what the LLM sees in the response,
  boosting accuracy on noisy tool outputs.

**Multiple knowledge bases:**
- One `Retrieve` tool per KB.
- Name them descriptively (`RetrieveProducts`, `RetrievePolicies`).
  The model uses the name + instructions + examples to pick.
- For **parallel** invocation, copy the orchestration prompt and add a
  `CRITICAL - Multiple Retrieve Tools` rule instructing it to fan out.
- For **conditional** invocation, give each tool mutually exclusive
  instructions and add a `CRITICAL - Retrieve Tool Selection` rule.


## Orchestration message format (`<message>` tags)

This trips everyone up exactly once. Orchestration agents only display
text to the customer when wrapped in `<message>` tags. Without the
tags, the customer hears silence and the LLM output gets logged but
never spoken/shown.

Required prompt formatting block:

```
<formatting_requirements>
MUST format all responses with this structure:

<message>
Your response to the customer goes here. This text will be spoken aloud, so write naturally and conversationally.
</message>

<thinking>
Your reasoning process can go here if needed for complex decisions.
</thinking>

MUST NEVER put thinking content inside message tags.
MUST always start with <message> tags, even when using tools, to let the customer know you are working to resolve their issue.
</formatting_requirements>
```

Multiple `<message>` blocks in one response are allowed and useful —
emit a quick "let me look that up" before a slow tool call, then a
second `<message>` with the result.


## Self-service flow wiring

The canonical contact-flow shape for an orchestrator self-service
deployment over **voice** (the shape validated end-to-end in
`projects/telco-cx/flows/telco-selfservice-es-inbound/`):

```
Set logging behavior
  └── Set recording and analytics behavior   (Contact Lens RealTime — required for Connect assistant on voice)
        └── Connect assistant                (CreateWisdomSession — binds the AI agents domain)
              └── Set voice                  (Polly voice + engine — see Nova Sonic rule below)
                    └── (language attribute)  (UpdateContactData LanguageCode — keep Lex + TTS aligned)
                          └── Get customer input   (Lex bot with Q-in-Connect intent; needs an opening prompt)
                                ├── Default / NoMatchingCondition  → Check contact attributes  (THE bot-turn exit — see below)
                                │       Namespace = Lex, Key = Session attributes, Session Attribute Key = "Tool"
                                │       ├── Equals "Escalate" → Set contact attributes (copy esc.* from Lex) → Set working queue → Transfer to queue
                                │       ├── Equals "Complete" → Disconnect
                                │       └── No match → Set working queue → Transfer to queue   (fail safe to a human)
                                └── Error  → Set working queue → Transfer to queue              (don't strand the caller)
```

### CRITICAL: the bot turn exits via Default, not Success

This is the single most common wiring mistake in the pattern. A
Q-in-Connect passthrough bot (the `AmazonQinConnect` /
`AMAZON.QInConnectIntent` intent) returns an intent name that matches
**no intent condition** you set on the **Get customer input** block.
So when the AI agent finishes its turn (via a Return-to-Control tool
like `Escalate` / `Complete`), the block exits through its **Default**
branch — in Flow language, the `ConnectParticipantWithLexBot` Action's
`NoMatchingCondition` error. It does **not** exit via Success.

Therefore the `Check contact attributes` (Compare on
`$.Lex.SessionAttributes.Tool`) must hang off the **Default /
`NoMatchingCondition`** branch:

```json
"get-input": {
  "Type": "ConnectParticipantWithLexBot",
  "Transitions": {
    "NextAction": "set-queue",
    "Errors": [
      { "NextAction": "check-tool", "ErrorType": "NoMatchingCondition" },
      { "NextAction": "set-queue",  "ErrorType": "NoMatchingError" }
    ]
  }
}
```

Wiring `check-tool` off Success (the intuitive choice) means the
escalation logic never runs and every contained call falls straight
through to the queue. If escalation "does nothing," check this first.

### Return-to-Control session-attribute contract

When a Return-to-Control tool fires, agentic self-service writes the
tool name to `$.Lex.SessionAttributes.Tool` and **every input
parameter** of the tool to `$.Lex.SessionAttributes.<paramName>`. A
custom `Escalate` tool with `escalationReason` / `escalationSummary` /
`customerIntent` / `sentiment` surfaces each as
`$.Lex.SessionAttributes.escalationReason`, etc. Copy them to contact
attributes with **Set contact attributes** (`UpdateContactAttributes`,
`TargetContact: Current`) so they outlive the bot session and reach
the human agent's screen pop.

### Pin the agent: "Enable AI Agent" toggle / `ai-agent-arn`

By default the Lex / Q-in-Connect path runs the assistant's **default**
SELF_SERVICE agent. To run a *specific* agent + version instead, the
**Get customer input** block has an **Enable AI Agent** toggle. When
checked, it lets you choose the domain and a named orchestration agent
on the block, and it expands the block into a three-Action fragment in
the flow JSON:

```
CreateWisdomSession            (binds the AI agents domain)
  └── UpdateContactData        (writes $.Wisdom.SessionArn)
        └── ConnectParticipantWithLexBot   (the Lex invocation)
```

The agent is pinned via a session attribute on the Lex call:

```json
"LexSessionAttributes": {
  "x-amz-lex:q-in-connect:ai-agent-arn":
    "arn:aws:wisdom:<region>:<acct>:ai-agent/<assistantId>/<agentId>:$LATEST"
}
```

Consequences:

- If you author the flow JSON by hand and omit this attribute, the
  flow is valid and runs, but it uses the **default** SELF_SERVICE
  agent — not your custom one. Symptom: "the agent does nothing" /
  "wrong behavior" even though the bot is wired correctly. Either set
  this attribute (mirror what the toggle produces) or make your agent
  the instance default (checklist step 5).
- The `validate_flow_json` MCP tool warns when a
  `ConnectParticipantWithLexBot` Action lacks this attribute, and also
  warns when it lacks a `NoMatchingCondition` error branch (the branch
  the bot turn actually exits through — see above).
- With the toggle enabled, the standalone **Connect assistant** block
  becomes redundant for self-service (the fragment's
  `CreateWisdomSession` already binds the domain). Keep a standalone
  Connect assistant block only if you also need agent-assistance
  recommendations for the human agent after transfer.



- **Engine must be `Generative`** (capital G) on the `Set voice`
  block when the Lex bot uses Speech-to-Speech (Nova Sonic). Use a
  Nova Sonic-compatible voice: **Matthew** (en-US), **Amy** (en-GB),
  **Olivia** (en-AU), **Lupe** (es-US).
- **Follow `Set voice` with a language attribute set**
  (`UpdateContactData` `LanguageCode`, the designer's "override
  language attribute" toggle) so Lex and TTS resolve the same locale.
- **Get customer input needs an opening prompt.**
  `ConnectParticipantWithLexBot` requires at least one of `PromptId` /
  `Text` / `SSML` / `Media` / `LexInitializationData`. Connect's
  server-side validator (not the structural one) rejects the flow
  without it.
- **`TransferContactToQueue` needs a success `NextAction`.** Connect
  rejects the flow if only `Errors` are wired. Point the success
  transition at a `Disconnect` (the contact ends at queue anyway).
- **Contact Lens RealTime is required** for the `Connect assistant`
  block on the voice channel — add a `Set recording and analytics
  behavior` block with `VoiceAnalyticsBehavior.AnalyticsModes:
  ["RealTime"]` anywhere before the bot. (Not required for chat.)

### Lex bot tag: `AmazonConnectEnabled=True` is case-sensitive

The Lex bot must carry the tag `AmazonConnectEnabled`. Two gotchas:

- The **flow dropdown / runtime** accepts `true` or `True`.
- The Connect admin **bot-management page**
  (`/bots/details/<botId>`) does a **case-sensitive** check and
  returns **403 — "The Conversational AI bot does not have the
  required tag set"** for anything other than `True` (capital T).
  This is unrelated to the user's security profile or tag-based
  access control; it is purely the tag value casing. Bots created
  through the Connect console get `True` automatically; bots imported
  via the Lex API (e.g. the `q_in_connect_passthrough` template) must
  be tagged explicitly. The repo deploy script
  (`.kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py`)
  now stamps `AmazonConnectEnabled=True`
  on the bot and alias after creation.

Also remember: a bot imported via the Lex API can still only be
*edited* in the Lex V2 console, not the Connect bot-building UI —
the tag fixes page access, not full Connect-native management.

Setup checklist (Connect Customer console):
1. Create an **Orchestration** AI agent, copy from
   `SelfServiceOrchestrator`.
2. Create a security profile granting tool access; assign to the AI
   agent in **Security Profiles** → **Select Security Profiles**.
3. Add tools (MCP + Return to Control + Constant for stubs).
4. Customize prompt or use the default `SelfServiceOrchestration`.
   Confirm `<message>` tag rule is present.
5. **Default AI Agent Configurations** → **Self Service** = your
   agent. (Without this, the Connect-assistant + Lex path runs the
   assistant's *default* self-service agent, not your custom one —
   the flow binds the domain, not a specific agent version.)
6. Create a Lex bot with a `Connect AI agents` intent
   (a.k.a. `AmazonQinConnect` intent — see
   `.kiro/skills/q-in-connect-bot-deploy/lex_skills/q_in_connect_passthrough/`
   for the template). Confirm
   the bot carries `AmazonConnectEnabled=True`.
7. Build the flow above, putting the **Connect assistant** block in
   the inbound flow before the customer hits the bot, and hang the
   `Check contact attributes` tool-routing off the bot block's
   **Default** branch.

Custom Return to Control tools store their input parameters as Lex
session attributes — copy them to contact attributes with **Set
contact attributes** if you want them to outlive the bot session
(e.g., for screen-pop on the human agent).

A fully worked, validated, and deployed example of this entire
pattern (flow JSON + mermaid + spec + the Lex passthrough bot) lives
in `projects/telco-cx/flows/telco-selfservice-es-inbound/`.


## Agent-assistance setup

For human-agent assistance, you don't need a Lex bot or `Get customer
input`. Instead:

1. Create / customize an `AgentAssistanceOrchestrator` (Orchestration
   type with the assistance prompt) plus any of `AnswerRecommendation`,
   `ManualSearch`, `NoteTaking`, `EmailResponse`, `CaseSummarization`.
2. Add the **Connect assistant** block to the inbound flow before
   routing the contact to a queue.
3. Grant **Connect assistant - Access** in **Agent Applications** to
   every agent's security profile so they can see the panel.
4. Direct CCP users to
   `https://<instance>.my.connect.aws/agent-app-v2/` (or the
   `awsapps.com` equivalent) so the assistant panel renders next to
   the CCP.

**Step-by-step guide integration** (deepens recommendations):
1. `aws qconnect list-knowledge-bases` → get `knowledgeBaseId`.
2. `aws qconnect list-contents --knowledge-base-id <id>` → get
   `contentId`.
3. Get the guide flow's ARN from the admin website or CLI.
4. `aws qconnect create-content-association` with
   `--association-type AMAZON_CONNECT_GUIDE` and
   `--association '{"amazonConnectGuideAssociation":{"flowId":"<arn>"}}'`.
5. Grant agents **Custom views - Access** so the guide actually
   renders in the workspace panel.

One content → one guide. One guide → many contents.

**AI-generated note taking** is the `NoteTaking` agent invoked as a
tool by `AgentAssistanceOrchestrator`. Returns HTML the agent can edit
before save. Requires contact transcription enabled on the channel.

**Case summarization** runs against case fields, comments, SLAs,
tasks, and related contact transcripts (30-day retention). Available
to unlimited-AI customers; uses the `QinConnectCaseSummarizationPrompt`
prompt by default.


## Security profiles

Security profiles do double duty: they gate **what the human user can
do in the console / workspace** and **what tools the AI agent can
invoke**. Both are enforced together when an AI agent acts inside a
human's session — the call must pass both checks.

**Administrator permissions** (under `AI agent designer` and
`Channels and Flows`):

| Permission | Required for |
|---|---|
| `AI Agents - All Access` | Create/edit/manage AI agents |
| `AI Prompts - All Access` | Create/edit/manage AI prompts |
| `AI Guardrails - All Access` | Create/edit/manage AI guardrails |
| `Conversational AI - All Access` | View/edit/create Lex bots |
| `Flows - All Access` | Build flows |
| `Flow Modules - All Access` | Wrap flow modules as tools |

**Agent-workspace permission** (under `Agent Applications`):

- `Connect assistant - View Access` (also called `Connect assistant -
  Access` in some pages — same permission) — required for the
  assistant panel and recommendation feed.
- `Custom views - Access` — required for step-by-step guides.

**AI-agent tool permission mapping** (mirrors the human equivalent):

| AI tool | Human-agent permission to mirror | API permission name |
|---|---|---|
| Cases (Create / Update / Search) | `Cases - View/Edit` (Agent Applications) | `Cases.*` |
| Customer Profiles | `Customer Profiles - View` (Agent Applications) | `CustomerProfiles.View` |
| Knowledge Base (Retrieve) | `Connect assistant - View Access` | **`Wisdom.View`** |
| Tasks (StartTaskContact) | `Tasks - Create` (Agent Applications) | `Tasks.Create` |

Attach security profile(s) to an AI agent on its edit page →
**Security Profiles** dropdown → **Save**. Multiple profiles are
union'd.

### Security profile for a self-service Retrieve agent (verified)

For an **Orchestration self-service** agent whose only data tool is
`Retrieve` (queries a knowledge base), the one permission that matters
is **`Connect assistant - View Access`** — API name **`Wisdom.View`**,
under **Agent Applications**. Without it the Retrieve tool calls fail
and the agent returns nothing from the KB. Symptom: "security profile
missing" / the agent answers no KB content even though the KB is
associated and synced.

Two attachment models, depending on mode:

- **Self-service** (customer ↔ bot, no human yet): attach a profile
  carrying `Wisdom.View` to the **AI agent** via the AI Agent designer
  → your agent → **Security Profiles** dropdown → Save. Best practice
  is a dedicated least-privilege profile with just
  `Connect assistant - View Access`, rather than reusing the Admin
  profile.
- **Agent-assistance** (AI helps a human in the workspace): the
  **human agent's** profile must *also* carry the same permissions —
  tool calls authorize against the **intersection** of the AI agent's
  and the human agent's profiles. So an escalation target who works
  the contact through the Connect assistant panel also needs
  `Wisdom.View`.

**Attachment via CLI or console.** Binding a security profile to an AI
agent is done with the **`connect`** API (not `qconnect`):

```bash
aws connect associate-security-profiles \
  --instance-id <instanceId> \
  --security-profiles Id=<securityProfileId> \
  --entity-type AI_AGENT \
  --entity-arn arn:aws:wisdom:<region>:<acct>:ai-agent/<assistantId>/<agentId> \
  --region <region>
```

`--entity-type` only supports `AI_AGENT` (and `USER`). Use the
**unqualified** agent ARN (no `:$LATEST`). Returns empty on success;
`disassociate-security-profiles` removes it. The console path (AI Agent
designer → agent → Security Profiles dropdown → Save) does the same
thing.

**Verify with `list-entity-security-profiles`** — NOT `get-ai-agent`
(which never surfaces attached profiles):

```bash
aws connect list-entity-security-profiles \
  --instance-id <instanceId> --entity-type AI_AGENT \
  --entity-arn arn:aws:wisdom:<region>:<acct>:ai-agent/<assistantId>/<agentId> \
  --region <region>
# -> { "SecurityProfiles": [ { "Id": "<profileId>" } ] }
```

Note: the console "Select Security Profiles" **dropdown** shows
profiles available to *add* and may stay on its placeholder even when
a profile is already attached; the attached profile renders as a
chip/row near the dropdown. The API (`list-entity-security-profiles`)
is the source of truth — if it lists the profile, the binding is live
regardless of the dropdown's placeholder text. Refresh the console
page if a freshly CLI-attached profile doesn't appear.

### Knowledge base association + Retrieve tool wiring (verified)

How an Orchestration agent actually retrieves from a specific KB —
confirmed against a live agent, not inferred:

1. **Associate the KB with the assistant (domain)** —
   `qconnect create-assistant-association --association-type
   KNOWLEDGE_BASE --association '{"knowledgeBaseId":"<kbId>"}'`.
   This returns an **`assistantAssociationId`** — that is the handle
   the Retrieve tool binds to, **not** the KB ID.
2. **Add the Retrieve system tool to the agent.** It is *added*, not
   created — it is the system MCP tool, not a bespoke tool:
   - `toolName`: `Retrieve`
   - `toolType`: `MODEL_CONTEXT_PROTOCOL`
   - `toolId`: `aws_service__qconnect_Retrieve`
   - `instruction`: `{ "instruction": "...", "examples": [...] }`
     — the only rich field you can customize (write the guidance and
     few-shot query examples here, in the agent's locale).
   - `overrideInputValues`: the KB binding + optional tag filter:
     ```json
     [
       { "jsonPath": "$.retrievalConfiguration.knowledgeSource.assistantAssociationIds",
         "value": {"constant": {"type": "JSON_STRING", "value": "[\"<assistantAssociationId>\"]"}}},
       { "jsonPath": "$.retrievalConfiguration.filter",
         "value": {"constant": {"type": "JSON_STRING", "value": "{\"equals\":{\"key\":\"industry\",\"value\":\"telco\"}}"}}},
       { "jsonPath": "$.assistantId",
         "value": {"constant": {"type": "STRING", "value": "{{$.assistantId}}"}}}
     ]
     ```
3. **The system Retrieve tool LOCKS `inputSchema`, `outputSchema`,
   `description`, `title`.** Sending any of them →
   `ValidationException: MCP tool 'Retrieve' does not allow overriding
   <field>`. If copying a Retrieve tool from another agent via
   `get-ai-agent`, strip those four before re-submitting.
4. **Content-segmentation `filter` matches per-content-item tags**,
   set with `qconnect tag-resource` on each content ARN — **not** the
   KB resource tag. Tag the items first or the filter returns nothing.
   The `filter` shape is the `RetrievalConfiguration.filter` union
   (`equals` / `andAll` / `orAll` / `in` / `startsWith` / ...).
5. **Security profile** with `Wisdom.View` must be attached to the
   agent (see above) or the Retrieve calls are unauthorized.
6. Add the tool via `update-ai-agent` (working copy) →
   `create-ai-agent-version` (immutable publish). A host flow that
   pins the agent by ARN with `:$LATEST` picks up the new version
   automatically.

A fully worked example lives in
`projects/telco-cx/connect_ai_agents/telco-selfservice-es-us/agent/agent.with-retrieve.json`
(Retrieve bound to `telco-kb-es`, filtered to `industry=telco`).


## Language alignment (CRITICAL)

A multilingual deployment fails silently when one of these layers
disagrees with the others. **Pick one ISO locale per call leg and
propagate it consistently across all four points** below. The
underlying value is the same (e.g., `es_US`); the format differs:

| Layer | How language is set | Format | Example for US Spanish |
|---|---|---|---|
| **Flow voice** | `Set voice` block (Action `UpdateContactTextToSpeechVoice`) — `TextToSpeechVoice` + `TextToSpeechEngine` | Polly voice ID + `standard` / `neural` / `generative` | `Lupe` / `generative` (a Spanish-US voice) |
| **Lex bot locale** | Per-locale folder under `BotLocales/<locale>/` in the bot definition | `xx_YY` (underscore) | `es_US` |
| **AI agent locale** | `Locale` dropdown on the AI agent builder, or `locale` field in the type-specific config | `xx_YY` (underscore) | `es_US` |
| **Prompt instructions** | Inline language guidance ("Respond in Spanish.") inside the AI prompt body | natural language | "Responde siempre en español." |

**Rules of thumb:**

1. **One locale per call leg.** A flow that runs `Set voice → Lupe / es-US`
   must invoke a Lex bot whose **active** locale is `es_US`, hand off to
   an AI agent whose `Locale` is `es_US`, and use a prompt that doesn't
   contradict that (no English-only example dialogues).
2. **Polly voice IDs ≠ locale codes.** `Lupe` is the voice; `es-US` is
   the locale tag Polly uses; `es_US` is what Lex and AI agents use.
   The voice you pick must be available for that locale in the Polly
   engine you select (`generative` has the smallest voice set —
   double-check it covers your locale before committing).
3. **Self-service legacy is English-only.** If you need any other
   locale for self-service, you must use the `Orchestration` type.
4. **Switch language mid-flow** by stacking `Set voice` again before a
   `Get customer input` block bound to a bot with that locale active.
   Don't forget the AI agent — either use a different agent per
   language or set the `Locale` per-session via Lambda.
5. **Repo template alignment.** The
   `.kiro/skills/q-in-connect-bot-deploy/lex_skills/q_in_connect_passthrough/`
   template ships with
   `en_US`, `es_US`, and `pt_BR` locale folders. The flow's
   `Set voice` choice and the AI agent's `Locale` setting must match
   one of those three values exactly. If the bot has only `en_US`
   and `es_US` activated and the flow says `Set voice → ja-JP`, the
   bot will fall back to its primary locale and the AI agent will
   answer in Japanese — a mismatch you'll only catch at runtime.
6. **CLI shape** (Manual search example, applies to all configurable
   types):
   ```json
   "configuration": {
     "manualSearchAIAgentConfiguration": {
       "locale": "es_ES"
     }
   }
   ```

**Supported AI agent locales** (one per agent version): `af_ZA`, `ar`,
`ar_AE`, `hy_AM`, `bg_BG`, `ca_ES`, `zh_CN`, `zh_HK`, `cs_CZ`, `da_DK`,
`nl_BE`, `nl_NL`, `en_AU`, `en_IN`, `en_IE`, `en_NZ`, `en_SG`, `en_ZA`,
`en_GB`, `en_US`, `en_CY`, `et_EE`, `fa_IR`, `fi_FI`, `fr_BE`, `fr_CA`,
`fr_FR`, `ga_IE`, `de_AT`, `de_DE`, `de_CH`, `he_IL`, `hi_IN`, `hmn`,
`hu_HU`, `is_IS`, `id_ID`, `it_IT`, `ja_JP`, `km_KH`, `ko_KR`, `lo_LA`,
`lv_LV`, `lt_LT`, `ms_MY`, `no_NO`, `pl_PL`, `pt_BR`, `pt_PT`, `ro_RO`,
`ru_RU`, `sr_RS`, `sk_SK`, `sl_SI`, `es_MX`, `es_ES`, `es_US`, `sv_SE`,
`tl_PH`, `th_TH`, `tr_TR`, `vi_VN`, `cy_GB`, `xh_ZA`, `zu_ZA`. Lex bot
locales are a subset of these — confirm the bot supports the locale
before committing the AI agent to it.


## Logging & observability

Logging goes to CloudWatch via the vended-logs delivery API, not via
the Connect logging behavior block. Setup is one-time per domain.

Three calls to enable logging:
1. `cloudwatch-logs put-delivery-source` — `logType: EVENT_LOGS`,
   `resourceArn: arn:aws:wisdom:<region>:<acct>:assistant/<id>`.
   IAM needs `wisdom:AllowVendedLogDeliveryForResource`.
2. `cloudwatch-logs put-delivery-destination` — point at a log group
   (or S3 / Firehose). Pick `outputFormat: json` for query-friendly
   logs.
3. `cloudwatch-logs create-delivery` — link source to destination.

**Event types** you'll see (most common in bold):

| Event | What it means |
|---|---|
| `TRANSCRIPT_CREATE_SESSION` | New AI session started. Marks `session_id`. |
| `TRANSCRIPT_UTTERANCE` | A message from any participant. |
| `TRANSCRIPT_TRIGGER_DETECTION_MODEL_INVOCATION` | Model decided whether the conversation has an intent (`is_valid_trigger`). |
| `TRANSCRIPT_INTENT_TRIGGERING_REFERENCE` | Intent surfaced. |
| **`TRANSCRIPT_LARGE_LANGUAGE_MODEL_INVOCATION`** | Raw prompt → completion record. The single most useful event for debugging "why did it say that". `prompt_type` reveals which step (e.g., `BEDROCK_KB_QUERY_REFORMULATION`, `GENERATIVE_INTENT_DETECTION`, `BEDROCK_KB_GENERATIVE_ANSWER`, `SELF_SERVICE_ANSWER_GENERATION`). |
| `TRANSCRIPT_QUERY_ASSISTANT` | Agent invoked one of the AI agents. |
| `TRANSCRIPT_RECOMMENDATION` | Recommendation surfaced to the human agent. |
| `TRANSCRIPT_RESULT_FEEDBACK` | Thumbs up/down on a recommendation. |
| `TRANSCRIPT_SELF_SERVICE_MESSAGE` | Customer ↔ legacy self-service exchange. |
| `TRANSCRIPT_SESSION_POLLED` | Human agent connected to the session. |
| **`TRANSCRIPT_ORCHESTRATION_MESSAGE`** | One step inside an orchestration loop — `participant: CUSTOMER` or `BOT`, `values` is JSON of `text` / `tool_use` / `tool_result` / `reasoning` parts. `orchestration_iteration` numbers the loop. |
| **`TRANSCRIPT_ORCHESTRATION_ERROR`** | Orchestration blew up — too many iterations, capacity throttle, etc. `orchestration_error` carries the message. |

**Common debug queries:**
```
filter session_id = "<session-id>"
filter session_name = "<contact-id>"
filter event_type = "TRANSCRIPT_ORCHESTRATION_MESSAGE" and ai_agent_orchestration_use_case = "CONNECT_SELF_SERVICE"
filter event_type = "TRANSCRIPT_ORCHESTRATION_ERROR"
filter prompt_type = "BEDROCK_KB_GENERATIVE_ANSWER"
```

`session_name` typically equals the contact ID.


## Troubleshooting checklist

When something looks off, walk this list before going deep:

1. **No AI session at all.** Confirm the **Connect assistant** block
   is in the inbound flow and runs before queue/agent assignment. The
   block creates the AI session — without it, neither
   self-service nor assistance can run.
2. **AI agent works on voice but not chat/email.** The KMS key on the
   domain is missing the `connect.amazonaws.com` service principal
   permissions (`kms:Decrypt`, `kms:GenerateDataKey*`,
   `kms:DescribeKey`). This is by far the most common chat outage.
3. **Customer hears silence in self-service.** The orchestration
   prompt is missing the `<message>` tag rule. Confirm the prompt
   wraps responses in `<message>` and that the model is following the
   format (check `TRANSCRIPT_ORCHESTRATION_MESSAGE` `values` for
   `type:"text"` parts).
4. **Tool never gets called.** Check (a) the AI agent's **Security
   Profile** dropdown — without one, no tool fires; (b) the tool's
   **Instructions** clearly describe when to use it; (c) for KB tools,
   the `Retrieve` tool is associated with the right
   `assistantAssociationId`.
5. **Tool call times out.** MCP tool execution has a hard 30-second
   ceiling. Move slow operations behind an async pattern (kick off a
   task, return a status string).
6. **Orchestration loop won't stop.** Hits `TRANSCRIPT_ORCHESTRATION_ERROR`
   with "exceeded maximum iterations". Reduce tool fan-out, tighten
   prompt instructions, or add a Return-to-Control fallback.
7. **Wrong language.** Walk the four-layer alignment table in
   [Language alignment](#language-alignment-critical). The most common
   miss is forgetting to set the AI agent `Locale` while remembering
   the Lex bot locale and the `Set voice` block.
8. **Wrong knowledge base hits.** If you use multiple KBs, confirm
   each `Retrieve` tool has distinct instructions. Add tag filters
   via override input values
   (`retrievalConfiguration.filter.equals.key/value`) to narrow.
9. **Permission denials when AI agent acts.** Both the AI agent's
   security profile and the human agent's security profile must grant
   the equivalent permission. The action is authorized against the
   intersection during agent-assistance flows.
10. **No recommendations in the assistant panel.** The user is on the
    legacy CCP URL. Send them to
    `https://<instance>.my.connect.aws/agent-app-v2/` and grant
    `Connect assistant - View Access`.

For deeper digging, the admin guide topic
`ts-ai-agents-self-service` indexes the rest of the troubleshooting
tree (legacy self-service, agentic self-service, common issues).


## Quick links

- Admin guide root:
  [Use Connect AI agents for real-time assistance](https://docs.aws.amazon.com/connect/latest/adminguide/connect-ai-agent.html)
- API reference:
  [Connect AI agents API](https://docs.aws.amazon.com/connect/latest/APIReference/API_Operations_Amazon_Connect_AI_Agents.html)
- MCP API reference:
  [Connect Model Context Protocol API](https://docs.aws.amazon.com/connect/latest/APIReference/Welcome.html)
- AgentCore Gateway (third-party MCP backend):
  [Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
