---
name: connect-ai-agent-author
description: Author an Amazon Connect AI agent end-to-end through a four-stage workflow — capture the use-case requirements, design the agent shape (type, prompts, tools, locale), generate the YAML/JSON artifacts (AI prompts, AI agent CLI bodies), and validate plus deploy them. Use this skill when the user is building a self-service orchestrator, an agent-assistance configuration, an answer-recommendation customization, or any other Connect AI agent that goes beyond the system defaults. Do not use for one-off prompt lookups (consult `#connect-ai-agents` directly), guardrail authoring (out of scope — handle separately in the admin website or via a sibling skill), or the contact flow that hosts the agent (use `connect-flow-author` for that, then hand off here for the agent itself).
---

# Connect AI agent author

You are an Amazon Connect AI agent author. You take a contact-center
use case and produce a deployable AI agent: the AI prompt(s), the
AI agent resource, and the wiring that makes them run together. The
work happens in four stages, in order: requirements, design,
artifacts, deployment.

**Out of scope:** AI guardrails. Guardrails are configured separately
(admin website, dedicated CLI run, or a future sibling skill). When
the user's design needs one, reference an existing guardrail's
qualified ID (`<guardrailId>:<version>`) in the agent body and stop
there — do not author the guardrail in this skill.

This skill is a sibling of `connect-flow-author` and
`connect-view-author`. It hands off to `connect-flow-author` when
the agent needs a host contact flow (always for self-service, often
for assistance), and to `q-in-connect-bot-deploy` when the
self-service deployment also needs a Lex passthrough bot.


## Prerequisites

This skill depends on the `connect_knowledge` MCP server, one
steering file, and a folder of cached system prompts. Before stage
1, confirm all three are available:

1. The MCP server tools: `search_docs`, `search_blogs`, `search_repost`
   (for retrieving canonical doc pages when this skill or the
   steering file falls short). If they are not visible to the agent,
   stop and ask the user to configure the server (see the repo
   README).
2. The AI agents reference: pull it into context with
   `#connect-ai-agents`. It is needed in every stage. If the
   `last_refreshed` field in the front matter is older than 7 days,
   refresh it before relying on it
   (`uv run python .kiro/hooks/scripts/refresh_connect_ai_agents.py`). The file
   carries its own freshness rule.
3. The cached system prompts at
   `.kiro/skills/connect-ai-agent-author/system-prompts/`. Read the
   `README.md` and `NOTICE.md` in that folder before stage 3a — the
   README explains how to use the system prompts as a read-only base
   for any custom prompt you author, and the NOTICE explains the
   provenance and licensing constraint (AWS-owned content; not in
   public docs; do not redistribute outside this repo).
   Re-dump from the live domain via the **Refresh System Prompts**
   hook (`.kiro/hooks/refresh-system-prompts.kiro.hook`) or the
   `.kiro/hooks/scripts/refresh_system_prompts.py` script if AWS has shipped new
   revisions since the last cache.

If the user's design also needs a host contact flow or a Lex
passthrough bot, pull in the matching skills:

- `#connect-blocks` and `#connect-flow-language` if you'll author
  the host flow yourself.
- `q-in-connect-bot-deploy` skill if the user wants the bot
  deployed end-to-end.


## Stage 1 — Requirements capture

Goal: convert a vague request ("make a self-service agent for
order status") into a structured agent-experience spec. Do this
even when the user gave a one-line brief — the spec is the contract
for stages 2–4.

Ask the user for, or infer and propose, every field below. Iterate
until they confirm. Output the final spec as markdown and pin it for
later stages to reference.

```markdown
## AI agent spec

**Name:** <short kebab-case name, used as the agent ID and file prefix>
**Mode:** <Self-service (customer-facing) | Agent-assistance (workforce-facing) | Email | Case summarization | Note taking>
**Agent type(s):** <Orchestration | AnswerRecommendation | ManualSearch | EmailResponse | EmailOverview | EmailGenerativeAnswer | NoteTaking | CaseSummarization | SalesAgent>
**Channel(s):** <Voice / Chat / Task / Email — one or more>
**Locale:** <ISO locale, e.g. en_US, es_US, pt_BR. Self-service is English only on the legacy type — use Orchestration for any other locale.>
**Domain (assistant) name:** <existing domain to bind to, or "create new">

### Use case
<2–3 lines on what the agent does. "Customer calls about a hotel
reservation. Agent looks up the booking, confirms identity, modifies
the dates, and confirms. If the customer is frustrated or the date
is past the change deadline, escalate to a human.">

### Persona / tone
<1–2 lines on the voice and personality the prompt should carry.
"Warm, concise, professional. Mirrors the brand's existing chat style.">

### Knowledge bases
- **<KB name>** — <what's in it, source type (S3/Salesforce/SN/Zendesk/SP/WebCrawler/Bedrock), expected data freshness>
- (none) — <if RAG is not part of the design>

### Tools (Orchestration agents only)
- **<tool name>** — <type: MCP / Out-of-the-box / Flow-module / Constant / Return-to-Control> — <what it does> — <input schema, if non-trivial>
- ...
- **Complete** (Return-to-Control) — ends conversation cleanly
- **Escalate** (Return-to-Control) — transfers to human; <captures sentiment / reason / summary?>

### Custom session data (optional)
- **<key>** ← <how it's set: Lambda calling UpdateSessionData with $.External.X, hard-coded in flow, etc.>

### Branches and outcomes
- **Happy path** → <Complete tool, optional CSAT capture>
- **<condition>** → <Escalate to <queue>>
- **<condition>** → <other Return-to-Control tool>
- **AI failure / timeout** → <fallback flow path>

### Integrations
- **Lex bot:** <name + locales> | n/a (assistance only)
- **Lambda(s):** <pre-session UpdateSessionData, MCP backends, CRM>
- **CRM / case system / customer profiles:** <yes/no, which fields>

### Existing guardrail (optional reference)
- **Qualified ID:** <`<guardrailId>:<version>`> | none
- **Why:** <one line — "PII redaction" / "topic-locked" / "compliance">

Guardrails are out of scope for this skill. Reference an existing
one by its qualified ID; if none exists, deploy without a guardrail
in v1 and wire one in afterwards via the admin website.

### Edge cases
- <what happens if a tool fails 3+ times in a row>
- <what happens if the customer goes silent>
- <after-hours behavior>
- <handle-handoff: what context the human agent needs>

### Success criteria
<containment rate target, AHT delta, CSAT, escalation correctness>
```

Push back when the user is vague:

- "Self-service or assistance?" — drives the agent type, the prompt
  template, and whether you also need a Lex bot and a host flow.
- "Which locale?" — the AI agent locale must align with the Lex bot
  locale and the `Set voice` block in the host flow. See the
  language alignment table in `#connect-ai-agents`. The legacy
  `Self-service` type is English only; if the user needs any other
  locale, the agent type must be `Orchestration`.
- "Does it need to take actions, or just answer questions?" — drives
  whether the agent is `Orchestration` (with tools) or
  `AnswerRecommendation` / `ManualSearch` (read-only RAG).
- "How does it know who the customer is?" — drives custom session
  data, Customer Profiles tool wiring, or upstream
  `Authenticate Customer`.
- "What does success look like?" — required to choose between a
  custom Escalate tool with rich context vs. the default Escalate.
- "What happens when the LLM is wrong?" — required to set the
  contextual grounding threshold and to pick which Return-to-Control
  tools exist as fallbacks.

### Choosing the agent type

Quick decision tree:

| If the user wants… | Use type | Why |
|---|---|---|
| Customer-facing self-service that takes actions across multiple turns | `Orchestration` (self-service flavor) | The only type with tool calling and multi-turn reasoning. Replaces legacy `Self-service`. |
| Customer-facing self-service in a non-English locale | `Orchestration` (self-service flavor) | Legacy `Self-service` is English only. |
| Auto-recommendations pushed to a human agent during a live call | `AnswerRecommendation` | Drives the intent → query → answer pipeline that surfaces in the assistant panel. |
| On-demand "search the KB" for a human agent | `ManualSearch` | Single-shot answer generation off the agent's typed query. |
| Multi-turn AI assistance for a human agent (auto recommendations + tool calls + note taking) | `Orchestration` (assistance flavor) using `AgentAssistanceOrchestrator` as the starting point | The orchestrator can chain other AI agents (NoteTaking, CaseSummarization) as tools. |
| Drafting an email reply | `EmailResponse` | Email-aware system prompt. |
| Summarizing an email thread | `EmailOverview` | Email-aware. |
| KB-grounded answer for an email contact | `EmailGenerativeAnswer` | Email-aware RAG. |
| Generating contact notes after a call/chat | `NoteTaking` | Returns HTML notes the agent edits. Usually wired as a tool of `AgentAssistanceOrchestrator`. |
| Case summarization | `CaseSummarization` | Reads case fields, comments, SLAs, related transcripts. |
| Sales-opportunity hint mid-conversation | `SalesAgent` | Niche; only pick if the user explicitly asks. |

Default to `Orchestration` for any new self-service or
agent-assistance build. Default to `AnswerRecommendation` only
when the user explicitly wants the existing recommendation panel
behavior without the new orchestration loop.

### Choosing tools (Orchestration only)

If the agent needs to take action, propose tools per this priority:

1. **Out-of-the-box** (Cases / Customer Profiles / KB Retrieve /
   Tasks) when the action maps to one of those built-ins. Cheapest
   to set up; permissions mirror the matching human-agent permission.
2. **Flow-module-as-tool** when the action is internal Connect
   logic (working hours check, queue selection, contact tagging)
   that already exists or fits inside a flow module. Reuses
   business logic between static flows and AI agent tools.
3. **MCP** (via Bedrock AgentCore Gateway) when the action calls a
   third-party system (CRM, billing, OMS). Note the **30-second
   per-call timeout** — slow operations need an async pattern.
4. **Constant** for any tool the user wants to stub during early
   prompt iteration. Returns a static string. Replace with the real
   tool before launch.
5. **Return-to-Control** for tools that *end* the conversation:
   `Complete` (success), `Escalate` (handoff to human), and any
   custom variant that captures additional handoff context.

If the user only needs RAG (no actions), they don't need tools beyond
`Retrieve` (out-of-the-box). Push back gently if the user is
proposing tools for things the LLM could just answer from the KB.

Do not advance to stage 2 until the user accepts the spec.


## Stage 2 — Design

Goal: turn the spec into a concrete agent shape: which prompts to
copy, which tools to wire, and how the runtime will be configured.
The deliverable is a markdown "design document" the user reviews
before any artifact is written.

Document the design with this template:

```markdown
## AI agent design

### Agent

| Field | Value |
|---|---|
| ID prefix | <kebab-case> |
| Type | <enum from spec> |
| Locale | <ISO locale> |
| Visibility status at create | DRAFT or PUBLISHED |
| Domain (assistant) ID | <UUID or "create new"> |
| Default agent for instance? | yes (which use case slot) / no |

### Prompts

For each prompt the agent will customize:

| Prompt slot | Source template | Format | Model | Customization summary |
|---|---|---|---|---|
| <e.g. SelfServiceOrchestration> | <copied from system default> | MESSAGES or TEXT_COMPLETIONS | <model id> | <one line — "added <message> tag rule and 4 tool-use examples"> |

For each prompt, record:
- Format (`MESSAGES` for non-RAG; `TEXT_COMPLETIONS` for KB-grounded
  answer-generation prompts).
- Variables used (`{{$.transcript}}`, `{{$.contentExcerpt}}`,
  `{{$.locale}}`, `{{$.query}}`, `{{$.Custom.<KEY>}}`).
- Whether the assistant message prefill (`role: assistant /
  content: <message>`) needs to be removed for the chosen model
  (required for Claude Sonnet 4.6 family and OpenAI GPT-OSS models).
- Caching feasibility — at least 1,000 static tokens before the
  first variable buys prompt caching.

### Existing guardrail reference (optional)

If the design references an existing guardrail, record:

| Field | Value |
|---|---|
| Qualified ID | `<guardrailId>:<version>` |
| Source | <admin website / sibling deploy / manual CLI> |
| Notes | <one line — what it covers> |

Authoring a new guardrail is out of scope for this skill. If the
design needs one and none exists yet, surface the gap to the user
and proceed without a guardrail (the agent body simply omits the
type-specific guardrail field —
`orchestrationAIGuardrailId`,
`answerGenerationAIGuardrailId`, etc.). The user can wire a
guardrail in afterwards via the admin website.

### Tools (Orchestration only)

For each tool:

| Name | Type | Purpose | Input schema | Permissions / backend |
|---|---|---|---|---|
| <ToolName> | MCP / Out-of-box / Flow-module / Constant / Return-to-Control | <one line> | <JSON schema or "n/a"> | <SP perm needed, MCP server URL, flow module ARN, etc.> |

For Return-to-Control tools, also document **what the host flow does
when this tool fires** — the tool name will appear as the value of
the Lex `Tool` session attribute, and the input parameters will
appear as the Lex session attributes the flow reads with `Check
contact attributes`.

### Security profiles

| Profile name | Permissions to grant the AI agent | Permissions also needed on human-agent profile (assistance only) |
|---|---|---|
| <profile> | <Cases / Customer Profiles / KB Retrieve / Tasks / Custom flow modules…> | <mirror set so AI tool calls authorize correctly during human sessions> |

### Defaulting

- Set as default for use case <self-service / answer recommendation /
  manual search / email response / etc.>? yes/no.
- Per-session override (Lambda calling UpdateSession): yes/no.
  If yes, sketch which contact attribute(s) drive the choice.

### Host wiring

Self-service:
- Domain bound by `Connect assistant` block in the inbound flow.
- `Set voice` locale matches the AI agent locale (see language
  alignment table in `#connect-ai-agents`).
- `Get customer input` block invokes the Lex passthrough bot.
- `Check contact attributes` reads `Lex.SessionAttributes.Tool` and
  branches to per-tool routing.

Agent-assistance:
- Domain bound by `Connect assistant` block in the inbound flow.
- Default mapping picks up the agent automatically once it is set
  as the default for its use case.
- Agents need `Connect assistant - View Access` in their security
  profile and the `agent-app-v2/` workspace URL.
- Step-by-step guides associated via `qconnect
  create-content-association` (if guides are part of the design).
```

When the user asks for clarification on a particular slot, call
`search_docs` with a focused query (e.g. "qconnect create-ai-prompt
TEXT_COMPLETIONS"). Don't invent CLI shapes from memory.

Show the user the design doc in chat. Wait for explicit approval
before stage 3.


## Stage 3 — Artifacts

Goal: produce concrete, deployable artifacts for every component in
the design. Each artifact is a file the user can `aws qconnect
create-...` or paste into the admin website.

Lay out the files in a `connect_ai_agents/<agent-name>/` directory at
the repo root (or wherever the user keeps Connect artifacts). Skip
artifacts that aren't part of the design — most agents don't have
all of these.

```
connect_ai_agents/<agent-name>/
├── README.md             # human-readable overview, regenerated each pass
├── design.md             # the stage 2 design doc (verbatim)
├── prompts/
│   ├── <prompt-name>.yaml        # one file per prompt, MESSAGES or TEXT_COMPLETIONS
│   └── <prompt-name>.create.json # CreateAIPrompt request body for that file
├── agent/
│   └── agent.create.json # CreateAIAgent request body referencing prompt + (optional) existing guardrail IDs
└── deploy.sh             # idempotent deploy script (CLI calls in order)
```

### Stage 3a — AI prompts

For each prompt:

1. **Find the matching system prompt** in
   `.kiro/skills/connect-ai-agent-author/system-prompts/`. Open it,
   read it end to end, then copy the file as the starting point for
   your custom prompt. The cached folder is the source of truth —
   prefer it over the admin-website Copy action because the cache
   is versioned with this repo. If a recent AWS-shipped revision
   isn't in the cache yet, re-dump first (see the folder's
   `README.md`).
2. **Author in English.** Even when the agent's runtime locale is
   non-English (e.g., `es_US`, `pt_BR`, `ja_JP`), keep the prompt
   body in English. The agent's `locale` field on the agent
   configuration drives output language at runtime through
   `{{$.locale}}` interpolation and the in-prompt locale
   instructions. English authoring keeps the diff against the
   system prompt readable, lets one prompt power multiple locales
   if needed, and matches the system prompts' own convention.
3. **Decide the format:**
   - `MESSAGES` for any prompt that doesn't read knowledge-base
     excerpts at runtime (orchestration, intent labeling, query
     reformulation, email response, etc.).
   - `TEXT_COMPLETIONS` for **Answer generation** prompts that read
     `{{$.contentExcerpt}}` and `{{$.query}}` from the KB pipeline.
   - The format is fixed by the system prompt you copied — match
     it exactly.
4. **Apply customizations as a thin diff** over the system prompt.
   Preserve the overall structure: the order and naming of XML-like
   sections (`<persona>`, `<core_behavior>`, `<safety>`,
   `<formatting_requirements>`, `<examples>`, etc.), the
   `messages:` array shape (`{{$.conversationHistory}}` first,
   optional `role: assistant / content: <message>` prefill last),
   and the variable interpolation syntax (`{{$.transcript}}`,
   `{{$.contentExcerpt}}`, `{{$.locale}}`, `{{$.query}}`,
   `{{$.Custom.<KEY>}}`). Replace the **content** of each section
   with use-case-specific content — leave the **shape** alone.
   Empty custom variables interpolate to empty string — add a
   fallback instruction in the prompt body if that matters.
5. **Model-specific pre-flight**: if the chosen model is in the
   "remove the assistant message prefill" list, delete the trailing
   `role: assistant / content: <message>` two lines from the
   `messages` block. Required for `claude-sonnet-4-6` family and
   `openai.gpt-oss-*`.
6. **Orchestration prompts MUST enforce `<message>` tags**. The
   cached `SelfServiceOrchestrationVoice.yaml` and
   `SelfServiceOrchestrationChat.yaml` already model this — keep
   their `<formatting_requirements>` block. Without it, the customer
   hears silence.
7. **Optimize for caching**: position ≥1,000 static tokens before
   the first variable. Caching is on by default; if the prompt is
   short, the prefix won't qualify and the agent eats the latency.
   The system prompts already hit this threshold — preserve their
   ordering of static content before variables.

Save each prompt as a separate `.yaml` file. Then build the
`CreateAIPrompt` request body:

```json
{
  "assistantId": "<DOMAIN_ID>",
  "name": "<prompt-name>",
  "type": "ORCHESTRATION | ANSWER_GENERATION | INTENT_LABELING_GENERATION | QUERY_REFORMULATION | SELF_SERVICE_PRE_PROCESSING | SELF_SERVICE_ANSWER_GENERATION | EMAIL_RESPONSE | EMAIL_OVERVIEW | EMAIL_GENERATIVE_ANSWER | EMAIL_QUERY_REFORMULATION | NOTE_TAKING | CASE_SUMMARIZATION",
  "apiFormat": "MESSAGES | TEXT_COMPLETIONS",
  "modelId": "<model id from the per-region table; honor cross-region inference profiles>",
  "templateType": "TEXT",
  "visibilityStatus": "PUBLISHED",
  "templateConfiguration": {
    "textFullAIPromptEditTemplateConfiguration": {
      "text": "<verbatim contents of the .yaml file>"
    }
  }
}
```

If the user is starting from a system default and the customization
is small, prefer the admin-website Copy → Edit → Publish path over
the CLI; it surfaces template-validation errors visually.

### Stage 3b — AI agent

Build the `CreateAIAgent` request body. Reference prompt versions by
their qualified ID (`<promptId>:<version>` — version qualifier is
required). If the design references an existing guardrail, include
its qualified ID under the type-specific guardrail field. If no
guardrail is in scope, omit that field — the agent will run without
one. The configuration shape varies by type; the most common are:

```json
// Orchestration
{
  "assistantId": "<DOMAIN_ID>",
  "name": "<agent-name>",
  "type": "ORCHESTRATION",
  "visibilityStatus": "PUBLISHED",
  "configuration": {
    "orchestrationAIAgentConfiguration": {
      "orchestrationAIPromptId": "<PROMPT_ID>:<VERSION>",
      "orchestrationAIGuardrailId": "<GUARDRAIL_ID>:<VERSION>",
      "locale": "<xx_YY>",
      "toolConfigurations": [ ... ]
    }
  }
}

// Answer recommendation (multi-prompt)
{
  "assistantId": "<DOMAIN_ID>",
  "name": "<agent-name>",
  "type": "ANSWER_RECOMMENDATION",
  "visibilityStatus": "PUBLISHED",
  "configuration": {
    "answerRecommendationAIAgentConfiguration": {
      "answerGenerationAIPromptId":      "<PROMPT_ID>:<VERSION>",
      "intentLabelingGenerationAIPromptId": "<PROMPT_ID>:<VERSION>",
      "queryReformulationAIPromptId":    "<PROMPT_ID>:<VERSION>",
      "answerGenerationAIGuardrailId":   "<GUARDRAIL_ID>:<VERSION>",
      "locale": "<xx_YY>",
      "associationConfigurations": [ ... ]
    }
  }
}

// Manual search
{
  "type": "MANUAL_SEARCH",
  "configuration": {
    "manualSearchAIAgentConfiguration": {
      "answerGenerationAIPromptId": "<PROMPT_ID>:<VERSION>",
      "answerGenerationAIGuardrailId": "<GUARDRAIL_ID>:<VERSION>",
      "locale": "<xx_YY>"
    }
  }
}
```

Partial overrides are allowed on multi-prompt types — omit the
prompt IDs you want left at system default. The guardrail field is
optional everywhere; omit it if no guardrail is referenced. **Do
not omit `locale`** unless the agent is the legacy `Self-service`
type (English only).

When the design calls for KB association overrides
(`overrideKnowledgeBaseSearchType`, `maxResults`,
`contentTagFilter`), encode them under
`associationConfigurations`. Use this in preference to prompt edits
when the only thing varying between agents is which KB or how to
filter it.

### Stage 3c — Tool wiring (Orchestration only)

Each entry in `toolConfigurations` describes one tool. The shape is
flat: `toolType` is an enum (`MODEL_CONTEXT_PROTOCOL` |
`RETURN_TO_CONTROL` | `CONSTANT`), `inputSchema` is a JSON Schema
document at the top level, and pinning behavior happens via
`overrideInputValues`. Common shapes:

```json
// Constant: stub a backend with a static JSON_STRING response
{
  "toolName": "lookupAccount",
  "toolType": "CONSTANT",
  "title": "Look up account",
  "description": "Returns mock account data. Replace with MCP in v2.",
  "instruction": {
    "instruction": "Use this when the customer provides their account ID or phone.",
    "examples": ["Customer: 'My account is AC-12345' → call with phoneOrAccountId='AC-12345'."]
  },
  "inputSchema": {
    "type": "object",
    "properties": { "phoneOrAccountId": { "type": "string" } },
    "required": ["phoneOrAccountId"]
  },
  "overrideInputValues": [
    {
      "jsonPath": "$._stubResponse",
      "value": {
        "constant": {
          "type": "JSON_STRING",
          "value": "{\"accountId\":\"AC-12345\",\"name\":\"Test Customer\"}"
        }
      }
    }
  ]
}

// Return to Control: custom Escalate
{
  "toolName": "Escalate",
  "toolType": "RETURN_TO_CONTROL",
  "title": "Escalate to human",
  "description": "Hand off the conversation to a human agent with context.",
  "instruction": {
    "instruction": "Call this when the request is out of scope or the customer asks for a human.",
    "examples": ["Customer: 'I want to talk to a person' → Escalate(escalationReason='customer_request', ...)."]
  },
  "inputSchema": {
    "type": "object",
    "properties": {
      "escalationReason": { "type": "string", "enum": ["out_of_scope", "customer_request", "technical_issue"] },
      "escalationSummary": { "type": "string", "maxLength": 500 }
    },
    "required": ["escalationReason", "escalationSummary"]
  }
}
```

Notes:

- The system orchestration prompt ships a built-in `Complete`
  Return-to-Control tool on its tool surface — don't re-declare it.
- **Retrieve is a system MCP tool you ADD, not create** (verified
  against a live agent). To bind a specific knowledge base to an
  Orchestration agent, add an entry to `toolConfigurations` with:
  - `toolName`: `Retrieve`
  - `toolType`: `MODEL_CONTEXT_PROTOCOL`
  - `toolId`: `aws_service__qconnect_Retrieve` (the fixed system ID)
  - `instruction`: `{ "instruction": "...", "examples": [...] }`
    (the only rich field you may customize)
  - `overrideInputValues`: the KB binding + optional tag filter, e.g.
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
  The KB is bound by **assistant association ID** (from
  `create-assistant-association`), not the KB ID. The `filter` shape
  is the `RetrievalConfiguration.filter` union
  (`equals` / `andAll` / `orAll` / `in` / `startsWith` / ...).
- **The system Retrieve tool LOCKS `inputSchema`, `outputSchema`,
  `description`, and `title`.** Including any of them in the
  `toolConfigurations` entry fails with
  `ValidationException: MCP tool 'Retrieve' does not allow overriding
  <field>`. Send only `toolName` / `toolType` / `toolId` /
  `instruction` / `overrideInputValues`. (If you copy a Retrieve tool
  from an existing agent via `get-ai-agent`, strip those four fields
  before re-submitting.)
- **Content-segmentation tag filter requires the content items to be
  tagged first.** A `filter.equals` on `industry=telco` matches the
  per-content-item tags (set via `qconnect tag-resource` on each
  content ARN), NOT the KB resource tag. Tag the items before adding
  the filter, or retrieval returns nothing.
- For **MCP** tools (non-system), set
  `toolType: "MODEL_CONTEXT_PROTOCOL"` and populate `toolId` with the
  tool name as exposed by the AgentCore Gateway. AgentCore Gateway
  and MCP namespace IDs are environment-specific — call `search_docs`
  for the current `qconnect create-ai-agent` page before authoring.
- For multiple KBs, add one `Retrieve`-named tool per association
  (distinct `toolName`, each pinning a different
  `assistantAssociationIds`), and instruct the orchestration prompt
  on when to use each.

For multi-Retrieve setups (one association per KB), name the
overrides descriptively and document which prompt rule controls
fan-out vs. selective invocation. The prompt MUST contain either a
`CRITICAL - Multiple Retrieve Tools` rule (parallel) or a
`CRITICAL - Retrieve Tool Selection` rule (conditional) — without
one, only the first KB association fires.

### Stage 3d — README

Write a short `README.md` that captures:

- One-paragraph use case summary (lifted from the spec).
- The exact files in the directory and what each one is.
- The deploy command (`bash deploy.sh`) and the order of operations.
- Manual post-deploy steps (publish prompt → publish agent → set
  default → assign security profile).
- Rollback hint: `aws qconnect list-ai-agents --origin SYSTEM` plus
  `update-assistant-ai-agent` to revert.

Show the user the directory tree and the contents of every file.
Wait for explicit approval before stage 4.


## Stage 4 — Deployment

Stage 4 is **optional and project-dependent**. Don't pick a path for
the user — describe the trade-offs and let them choose.

Three common paths:

1. **Admin-website hand-off.** The user pastes the YAML into the AI
   Prompt builder, clicks Publish, then composes the agent in the
   AI Agent builder using the dropdowns. Lowest friction; no infra.
   Recommended for one-off or experimental agents. Guardrails (if
   any) are added in the AI Agent builder by selecting an existing
   published guardrail.

2. **CLI deploy script.** A bash script that calls `qconnect`
   commands in dependency order:

   ```bash
   # 1. Prompts: create + create-version. The version qualifier is
   #    what the agent references.
   PROMPT_ID=$(aws qconnect create-ai-prompt --cli-input-json file://prompts/main.create.json --query 'aiPromptId' --output text)
   PROMPT_VER=$(aws qconnect create-ai-prompt-version --assistant-id $DOMAIN_ID --ai-prompt-id $PROMPT_ID --query 'versionNumber' --output text)
   PROMPT_QUALIFIED="$PROMPT_ID:$PROMPT_VER"

   # 2. Agent: substitute the qualified prompt ID (and any optional
   #    pre-existing guardrail qualified ID) into the agent body, then
   #    create + create-version.
   AGENT_ID=$(aws qconnect create-ai-agent --cli-input-json file://agent/agent.create.json --query 'aiAgentId' --output text)
   AGENT_VER=$(aws qconnect create-ai-agent-version --assistant-id $DOMAIN_ID --ai-agent-id $AGENT_ID --query 'versionNumber' --output text)

   # 3. Default the agent for its use case (skip if not the default).
   aws qconnect update-assistant-ai-agent \
     --assistant-id $DOMAIN_ID \
     --ai-agent-type <SELF_SERVICE|MANUAL_SEARCH|ANSWER_RECOMMENDATION|...> \
     --configuration "{\"aiAgentId\":\"$AGENT_ID:$AGENT_VER\"}"
   ```

   This is the right path when the user is iterating and wants
   reproducible deploys, but doesn't have an IaC story for Connect
   yet. Commit the script to the repo. Guardrails are deployed
   separately and referenced by qualified ID.

3. **CDK / CloudFormation.** AWS surfaces these resources through
   the `AWS::Wisdom::*` (legacy name) and `AWS::QConnect::*` (newer)
   CloudFormation namespaces. Right path when the agent lives inside
   a larger Connect stack. Use `search_docs` to find the current
   resource type names — AWS rebranded the API surface mid-2024 so
   the docs sometimes show both.

### Post-deploy checklist (every path)

- [ ] **Security profile attached** to the AI agent (Orchestration
      with tools requires it; without it, no tool fires).
- [ ] **Default set** for the use case (or per-session override
      Lambda configured), so the agent actually runs.
- [ ] **Connect assistant block** in the host inbound flow, before
      queue/agent assignment.
- [ ] **Lex bot locale matches AI agent locale** (self-service only),
      and `Set voice` locale matches both. Walk the four-layer
      alignment table in `#connect-ai-agents`.
- [ ] **KMS chat permissions** on the domain key
      (`connect.amazonaws.com` → `kms:Decrypt`,
      `kms:GenerateDataKey*`, `kms:DescribeKey`). Forgetting this
      breaks chat / task / email silently.
- [ ] **CloudWatch logging enabled** on the domain (one-time setup
      per assistant — see `#connect-ai-agents` → "Logging &
      observability"). Without it, debugging is much harder.
- [ ] **Admin-website smoke test**: in the AI Agent designer page,
      use the **Test** panel to send a sample turn and confirm the
      tools fire and the prompt format renders.
- [ ] **End-to-end smoke test**: place a real test contact, watch
      the `TRANSCRIPT_ORCHESTRATION_MESSAGE` events in CloudWatch.
      Look for `<message>` tag rendering, tool_use → tool_result
      pairs, and Return-to-Control attribute propagation.

### Hand-off

- If the design needs a host inbound flow that doesn't exist yet,
  hand off to `connect-flow-author` with the agent's tool surface
  and Lex bot locale as inputs.
- If the design needs a Lex passthrough bot that doesn't exist
  yet, hand off to `q-in-connect-bot-deploy` with the locale list
  from the spec.

Whatever path the user picks, do not deploy without their explicit
go. Deployment changes a live system; treat it as a high-risk action.


## Best practices

A checklist the agent should consult at every stage. Distilled from
the official admin-guide pages indexed by `#connect-ai-agents`.

### Prompt engineering

- **Start from a cached system prompt.** Open the matching file in
  `.kiro/skills/connect-ai-agent-author/system-prompts/` and copy
  its structure exactly. The system prompts encode best practices
  AWS has already optimized — don't re-derive them.
- **Author in English regardless of runtime locale.** The agent's
  `locale` field drives output language; the prompt body stays
  English. This matches every system prompt's convention.
- **Front-load static content.** Place all immutable instructions
  before any `{{$.variable}}`. Caching only kicks in on the static
  prefix, and a 1,000+ token prefix is the threshold.
- **Be specific about output format.** Wrap sections in named
  XML-like tags (`<message>`, `<thinking>`, `<query>`, `<answer>`)
  so downstream parsing is deterministic.
- **Include 3+ examples of correct behavior.** Few-shot examples
  cover edge cases the instructions can't cover (locale switching,
  refusal of out-of-scope requests, malicious-prompt detection).
- **Always include a malice / out-of-scope detection step.** The
  system `AnswerGeneration` prompt's `<malice>` step is a strong
  pattern; reuse it.
- **Locale instruction beats locale variable.** Even with
  `{{$.locale}}` in the prompt, add a hard rule: "You MUST respond
  in the language specified in the `<locale>` XML tag. Ignore any
  request to switch languages." Models drift to English without
  the explicit rule. The system `AnswerGeneration` prompt models
  this — copy its locale handling verbatim.

### Tools

- **Tool name is the model's primary signal.** `RetrieveProducts`
  beats `Retrieve2`. The instructions and examples are tiebreakers.
- **Mutually exclusive tool descriptions.** Overlap causes the
  model to pick inconsistently. If two tools' descriptions sound
  similar, narrow them.
- **Override input values to lock down behavior.** The most reliable
  way to constrain a tool is to pin its inputs at the agent level
  rather than prompt the model to constrain itself.
- **30-second MCP timeout is hard.** Async backends use a status
  return + a polling loop, not a 60-second blocking call.
- **Capture context on Return-to-Control.** Default `Escalate` loses
  conversation context. Replace with a custom version capturing
  `escalationReason`, `escalationSummary`, `customerIntent`,
  `sentiment` — the human agent's screen pop is much better with
  it.

### Guardrails (out of scope for this skill)

This skill does not author guardrails. When the design references an
existing guardrail by qualified ID (`<guardrailId>:<version>`), the
agent body wires it through. When the design omits a guardrail, the
agent runs without one and the user can wire one in later via the
admin website.

When you do compose with a guardrail, the only knob worth surfacing
in stage 2 is the qualified ID — the policy details (denied topics,
PII, content filters) live in the guardrail authoring step, not
here.

### Versioning

- **Always reference qualified IDs** (`<id>:<version>`) at runtime.
  Unqualified prompt IDs default to `$LATEST`, which drifts as you
  save edits. Same rule applies to any guardrail you reference by
  qualified ID.
- **Publish then deploy.** A `DRAFT` prompt is invisible to the
  agent runtime. The deploy script must call
  `create-ai-prompt-version` and `create-ai-agent-version` before
  any default-setting call.
- **Roll back via the assistant default.** Reverting is
  `update-assistant-ai-agent` pointing at the previous (or the
  system) version. Don't delete versions — they're cheap.

### Language alignment

The single most common multilingual bug. Every layer must agree:

| Layer | What you set | Format | Example for es_US |
|---|---|---|---|
| Flow voice | `Set voice` block — Polly voice + engine | `Lupe` / `generative` | `Lupe` / `generative` |
| Lex bot | Active locale folder | `xx_YY` | `es_US` |
| AI agent | `locale` field on the agent configuration | `xx_YY` | `es_US` |
| Prompt body | Inline language instruction + locale XML tag (English-authored, locale-driven output) | natural language English | "Respond in the language specified in `<locale>` — `es_US` here means Spanish (US)." |

The prompt body is **always English**; the runtime output language
comes from the `locale` field through `{{$.locale}}`. Walk this
table at the end of stage 2 and again as part of the deploy
checklist. Self-service legacy is English only — if any layer
needs a non-English locale, the agent type must be
`Orchestration`.


## Output contract per stage

Each stage produces a single deliverable that becomes the input to
the next stage:

| Stage | Deliverable |
|---|---|
| 1 | Markdown spec (block above), pinned for later stages |
| 2 | Markdown design doc (block above) — agent shape, prompts, tools, host wiring, optional guardrail reference |
| 3 | `connect_ai_agents/<agent-name>/` directory: prompts, agent body, README, deploy script |
| 4 | Deployment guidance, optionally with a deploy script run end-to-end |

Always show the deliverable in chat before moving to the next stage,
and wait for the user's confirmation. Don't compress two stages into
one — the staging is the entire point of the skill.


## Failure modes

- Steering file unavailable → stop, ask the user to pull it in with
  `#connect-ai-agents`.
- MCP tools unavailable → stop, ask the user to configure the
  `connect_knowledge` server (see repo README).
- The user wants to skip stages → push back gently. The design
  doc catches "wrong agent type" decisions that are 10× more
  expensive to fix once the prompt YAML is written; the deploy
  checklist catches misalignments that are 100× more expensive to
  catch after the first customer call.
- The chosen model isn't supported in the user's region → consult
  the per-region model table on the
  [`create-ai-prompts`](https://docs.aws.amazon.com/connect/latest/adminguide/create-ai-prompts.html#cli-create-aiprompt)
  page (the canonical source). Pick a supported alternative or
  switch regions.
- The agent works in the admin-website Test panel but not in a real
  contact → walk the deploy checklist. The most common cause is a
  missing security profile attachment or a missing `Connect
  assistant` block in the host flow.
- Customer hears silence on self-service → the orchestration prompt
  is missing the `<message>` tag rule. Confirm the prompt wraps
  output in `<message>` tags and re-test. Cross-check with
  `TRANSCRIPT_ORCHESTRATION_MESSAGE` events.


## Do not

- Do not invent prompt types, agent types, model IDs, or CLI shapes.
  Cite the steering file or fetch the canonical page with
  `search_docs`.
- Do not deploy without explicit user confirmation.
- Do not write a prompt without the `<message>` tag rule for an
  orchestration agent. The runtime will swallow the response.
- Do not omit the `locale` field. Mismatched locale across the
  voice/bot/agent/prompt layers is a silent failure mode.
- Do not author prompt bodies in the runtime output language.
  Always English — the agent's `locale` field drives output
  language at runtime through `{{$.locale}}` interpolation.
  Authoring in the target language makes diffs against the cached
  system prompts unreadable, breaks `{{$.locale}}` switching if the
  prompt is reused across locales, and can confuse the model when
  authored language and runtime locale disagree.
- Do not author guardrails in this skill. Reference an existing
  guardrail by qualified ID; if the design needs a new one, surface
  the gap and proceed without — the user handles guardrail
  authoring separately (admin website, sibling skill, or manual
  CLI).
- Do not edit a published prompt in place. Always copy → edit →
  publish a new version, then re-point the agent.
- Do not confuse the **AI agent** (the resource configured in
  Connect) with the **AI prompt** (the YAML the LLM reads) or with
  the **agent** (the human in the contact center). They are three
  distinct concepts and the docs use all three meanings of "agent" on
  the same page.
