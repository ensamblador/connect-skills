---
inclusion: manual
last_refreshed: 2026-06-12
source_urls:
  - https://docs.aws.amazon.com/connect/latest/adminguide/viewing-logs-for-connect-ai-agents-self-service.html
  - https://docs.aws.amazon.com/connect/latest/APIReference/API_amazon-q-connect_ListSpans.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/monitor-ai-agents.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/ai-agent-traces.html
  - https://docs.aws.amazon.com/connect/latest/adminguide/monitor-automated-interaction-logs.html
  - https://docs.aws.amazon.com/connect/latest/APIReference/API_amazon-q-connect_CreateAIAgent.html
  - https://docs.aws.amazon.com/connect/latest/APIReference/API_amazon-q-connect_OrchestrationAIAgentConfiguration.html
---

# Troubleshooting Q in Connect AI agents (orchestration self-service)

A field-tested playbook for debugging Connect AI agents that greet but then
**never respond**, fail silently, or behave differently from a console-built
agent. Written from a real multi-day investigation; the methodology matters
as much as the specific findings.

## Golden rules (learned the hard way)

1. **Verify empirically; never assert a root cause from a plausible theory.**
   Every confident hypothesis below (model access, locale, tool shape, gateway
   tools, security profile, prompt scaffolding, "corrupt resource") looked
   right and was wrong. Change ONE variable at a time and confirm against
   spans/logs before concluding.
2. **Re-fetch current state before concluding.** Agents/prompts get edited in
   the console between tests; stale `get-ai-agent` output will mislead you.
3. **The runtime truth is in `ListSpans`**, not in the agent config. Two
   config-identical agents can behave differently — read the spans.
4. **Hold one thing constant to isolate.** The breakthrough came from keeping
   the *prompt* constant across a working and a failing agent, which ruled out
   everything except the agent resource itself.
5. **A config-identical console agent that works while your IaC agent fails is
   a giant clue** — the difference is in the *creation path*, not the config.
6. Credentials for the demo account expire often. Always start with
   `aws sts get-caller-identity --profile <profile> --region <region>`.
7. Terminal output truncates on multi-line / heredoc commands — write to a
   temp file then `cat`, or use single `--query` calls.

## Symptom → first moves

Classic symptom: the flow plays its static greeting, then the agent **never
replies**. Chat transcripts show `lex.event.response.failed`; flow logs show
`GetUserInput => Error (NoMatchingError)`.

1. **Confirm which agent + version actually ran.** The flow may reference
   `:$LATEST`, a pinned `:N`, or you may have swapped agents between tests.
2. **Enable AI-agent event logs** (one-time) so you get
   `TRANSCRIPT_AI_AGENT_TRACE` spans and orchestration messages/errors in
   CloudWatch — see `monitor-ai-agents.html`
   (`PutDeliverySource` → `PutDeliveryDestination` → `CreateDelivery`,
   logType `EVENT_LOGS`).
3. **Use `ListSpans`** (below) — the recommended first-line tool for
   orchestrator agents. No extra enablement needed; it is NOT CloudWatch
   Transaction Search.

## Tool 1 — `ListSpans` (the workhorse)

`ListSpans` returns the agent's execution traces for a **session** (not a
contact): orchestration flow, the LLM `inference` span, and `execute_tool`
spans. No enablement required beyond IAM (`wisdom:`/`qconnect:` ListSpans).

```bash
aws qconnect list-spans \
  --assistant-id <assistantId> \
  --session-id <sessionId> \
  --max-results 100 --profile <profile> --region <region> --output json
```

Map a contact → session first (event logs carry both `contact_id` and
`session_id`; span attributes include `contactId`/`initialContactId`).

What to read per span:
- `status` / `statusDescription` (`ERROR` + "There was an orchestration error
  for this nextMessageToken" = failed at model inference).
- `usageInputTokens`/`usageOutputTokens` — **0 tokens means it failed before
  the model generated anything** (config/tool/prompt problem, not the model).
- `requestModel`, `promptId:promptVersion`, `aiAgentVersion` — confirm exactly
  what ran.
- `inputMessages` / `systemInstructions` — the actual rendered prompt + history.
- On `execute_tool`: `inputMessages[].toolUse` (the call) and
  `outputMessages[].toolResult` (the backend response / error).

### Finding sessions from the event-log group

```bash
aws logs filter-log-events \
  --log-group-name "/aws/connect/qic-ai-agent/<instance-alias>" \
  --start-time $(( ($(date +%s) - 3600) * 1000 )) \
  --profile <profile> --region <region> --output json > /tmp/ev.json
```

Then group by `session_id`, collect `ai_agent_id`, and tally `event_type`.
Useful event types:
- `TRANSCRIPT_ORCHESTRATION_ERROR` → failed turn (carries `orchestration_error`).
- `TRANSCRIPT_LARGE_LANGUAGE_MODEL_INVOCATION` / `TRANSCRIPT_AGENTIC_MESSAGE`
  → present only on **successful** agentic turns.
- A session with `ORCHESTRATION_ERROR` and **no** `LLM_INVOCATION`/
  `AGENTIC_MESSAGE` = inference died at 0 tokens.

## Tool 2 — config diff (working vs failing)

When a console-built agent works and an IaC one doesn't, diff the full
configs and prompts:

```bash
aws qconnect get-ai-agent  --assistant-id <A> --ai-agent-id <id|id:ver> ...
aws qconnect get-ai-prompt --assistant-id <A> --ai-prompt-id <id> ...
```

Compare **every** field, not just tools: `orchestrationAIPromptId`, `locale`,
`modelId` (on the prompt), `origin`, `type`, and each tool's
`toolName`/`toolId`/`userInteractionConfiguration`/`overrideInputValues`/
`outputFilters`. Published versions (`:N`) are immutable snapshots — the
running version may differ from the draft (`$LATEST`).

## Tool 3 — CloudTrail diff of the actual `CreateAIAgent` body

The decisive tool when configs *look* identical. Compare the request bodies a
console call and a CloudFormation deploy actually sent:

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=CreateAIAgent \
  --start-time <date> --profile <profile> --region <region> --output json
```

Inspect `requestParameters.configuration` and `userIdentity` per event.

## Tool 4 — the boto3 clone test (creation-path isolation)

If a config-identical console agent works and the CFN/CDK one fails, clone the
working agent via a **direct boto3 `create_ai_agent`** call (a new name, same
config), publish a version, and point the flow at it. If the clone works, the
problem is the **CloudFormation resource provider's request body**, not your
config. (This is exactly how the root cause below was confirmed.)

## KNOWN ROOT CAUSE — `AWS::Wisdom::AIAgent` empty-array tool bug

**Symptom:** an orchestration agent created with `AWS::Wisdom::AIAgent`
(CfnAIAgent) greets, then every turn fails at inference with 0 tokens and
"There was an orchestration error for this nextMessageToken". The
byte-identical agent created by the console or boto3 works.

**Cause:** the managed `AWS::Wisdom::AIAgent` resource provider serializes
**empty `outputFilters: []` and `overrideInputValues: []` arrays on every
tool** when it calls `CreateAIAgent`. The orchestration runtime treats an empty
`outputFilters: []` as different from *absent* and fails model inference. A
direct boto3 `CreateAIAgent` (and the console) omit those keys. Confirmed two
ways:
- a boto3 clone with tools but no empty arrays → works;
- the same CFN agent works only with **zero tools** (no tool to carry the
  empty arrays); add even one tool → fails.

Note: the **synthesized CloudFormation template does not contain** these empty
arrays — the provider injects them when calling the API. You cannot suppress
them from the L1 construct.

**Fix:** create the agent via a boto3-backed **custom resource** instead of
`CfnAIAgent`. Build `toolConfigurations` as plain dicts and **only set
`overrideInputValues` when actually populated; never emit an empty
`outputFilters`/`overrideInputValues`**. In this repo see
`connect/ai_agent_cr.py` (+ `connect/ai_agent_cr_lambda/index.py`) and
`SelfServiceAIAgent(use_boto3_creation=True)` in `connect/ai_agents.py`.

CreateAIAgent validates referenced resources across services, so the provider
Lambda's role needs more than `wisdom:`/`qconnect:` — it also returned a
generic "Insufficient permissions to perform this action" until granted
`connect:*`, `app-integrations:*`, `bedrock-agentcore:*`, `bedrock:*`
(tighten later once the minimal set is known). The IAM action prefix is the
legacy **`wisdom:`**, even though the boto3 client is `qconnect`.

Migration gotchas:
- AI agent (and prompt) **names are unique per assistant** — a same-name
  replacement collides 409 during create-before-delete. Decouple the agent
  name from the prompt name so you can give the new agent a free name while
  keeping the shared prompt resource untouched.
- A prompt referenced by other agents must NOT be replaced (renaming or
  changing its construct id deletes it and breaks them).

## Hypotheses that LOOKED right but were NOT (don't re-chase)

- **Bedrock model access** — direct `converse` to `us.`/`global.` Haiku worked;
  the orchestration role had access too.
- **Model variant `us.` vs `global.`** — both failed/worked depending only on
  the agent resource, not the variant.
- **Locale `es_US`** — the working agent also used `es_US`.
- **Prompt scaffolding** (`{{$.toolConfigurationList}}` / `<system_variables>`)
  — necessary for a good prompt, but the failing agent failed even with the
  exact working prompt.
- **Tool shape** (`userInteractionConfiguration` present, `title` on RTC tools)
  — the working agent had inconsistent/mixed shapes and still worked.
- **MCP gateway tool id format** — ours matched the console agent's; the
  underscore string seen first was the tool *name*, not the *id*.
- **Security profile assignment** — removing it changed nothing; the working
  agent worked with one attached.
- **"Corrupt agent resource"** — a freshly recreated CFN resource failed too;
  it was the creation path, not the individual resource.

## Backend / MCP tool execution failures (a different class)

If `inference` is OK but an `execute_tool` span is `ERROR` with
`errorType: tool_execution` and a result like
`"MCP tool execution failed: An internal error occurred. Please retry later."`:

- This is **downstream of the agent** (AgentCore gateway → API Gateway →
  Lambda → data store). Check the backing Lambda's logs and last-invocation
  time; a clean Lambda run means the failure is in mapping or status.
- **AgentCore gateways treat any non-2xx as a tool failure** and wrap it in the
  opaque "internal error" message. A backend `404 not found` therefore reaches
  the agent as an internal error, and the agent escalates instead of saying
  "no account found". For lookup endpoints behind an MCP gateway, prefer
  returning **HTTP 200 with a structured not-found payload**
  (`{"found": false, "message": "..."}`) over a 404.
- Downstream tools that need an id from a prior lookup (e.g. a guided form that
  needs `customerId`) will silently not fire if the lookup failed — fix the
  lookup first.

## The CDK version "no re-mint" trap (why your fix looks deployed but isn't)

This one will waste a whole afternoon: you change the prompt or the agent
config, `cdk deploy` succeeds, you re-test — and the **stale behavior
persists**. The agent keeps running the old version even though deploy
reported no errors.

Cause: `CfnAIPromptVersion` / `CfnAIAgentVersion` have **fixed logical IDs**.
A plain deploy updates the prompt/agent **draft** (`$LATEST`) but does NOT
create (publish) a new immutable `:N` version, because the version resource
already exists and its properties didn't change. The flow runs a pinned `:N`
(or `$LATEST` resolving to the last published snapshot), so your draft edit
never reaches the runtime.

Fix (used in this repo, `connect/ai_agents.py`): **embed a content hash in the
version construct id** so any change to the prompt/config mints a brand-new
version resource:

```python
self.prompt_version = wisdom.CfnAIPromptVersion(
    self, f"PromptVersion{_content_hash(prompt_text, model_id)}", ...)
# and for the legacy CfnAIAgent path:
self.agent_version = wisdom.CfnAIAgentVersion(
    self, f"AgentVersion{_content_hash(prompt_text, model_id, locale, ...)}", ...)
```

**Always confirm the live `promptVersion` / `aiAgentVersion` from a span AFTER
deploy** — do not trust that "deploy succeeded" means "new version running."
A span's `promptId:promptVersion` and `aiAgentVersion` are the only proof.

## Where each signal actually lives (stop looking in the wrong place)

- **X-Ray / CloudWatch Transaction Search is a dead end here.** Q in Connect
  orchestration does NOT emit spans to X-Ray — we enabled Transaction Search
  and only saw unrelated traces. Use `ListSpans` + EVENT_LOGS instead. (Don't
  burn time on `put-resource-policy` / Transaction Search enablement for this.)
- **Bedrock model-invocation logging won't capture it either** — the
  orchestration call is service-managed and does not appear in your account's
  Bedrock invocation logs. Rule out model access with a *direct* `converse`
  call, not by trawling Bedrock logs.
- **`lex.event.response.failed` is NOT in the real-time analysis API.**
  `list-realtime-contact-analysis-segments-v2` shows only customer/bot
  *messages*. The per-turn `application/vnd.amazonaws.lex.event.response.failed`
  EVENT entries live in the **S3 ChatTranscripts JSON** (the bucket from the
  instance's CHAT_TRANSCRIPTS / CALL_RECORDINGS storage config). Pull the
  transcript object from S3 to see the failed events.

## The two distinct "logging" paths (don't conflate them)

There are two separate enablement flows and they surface different things:

1. **AI-agent EVENT_LOGS** (`monitor-ai-agents.html`) →
   `PutDeliverySource`/`PutDeliveryDestination`/`CreateDelivery` with logType
   `EVENT_LOGS` to `/aws/connect/qic-ai-agent/<alias>`. This is what feeds the
   session/`ListSpans` workflow above. **This is the one you want for the
   silent-agent bug.**
2. **AI agent traces in the Contact-details UI** (`ai-agent-traces.html`,
   the `ai-agent-traces.html` panel) requires a different combination:
   `AUTOMATED_INTERACTION_LOG` = true, Bot Analytics & Transcripts enabled,
   AND call-recordings/transcripts S3 storage. If Bot Analytics was enabled
   **before 2026-06-05** you must disable and re-enable it (a re-cycle) for
   traces to start flowing. Enabling "automated interaction logs" alone does
   NOT make traces appear — this is why the UI stayed empty in our run.

## Deploy-time validation gotchas (adjacent, but they bit us)

These are surfaced at `cdk deploy` / CloudFormation time, not at runtime, but
they block the whole investigation:

- **`AWS::Connect::View` `Description` forbids parentheses** (and other chars).
  A description like `New line form (chat)` is rejected. Keep it alphanumeric
  + basic punctuation.
- **`ShowView` flow block requires `InvocationTimeLimitSeconds`.** Omitting it
  throws `InvalidContactFlowException` at deploy even though the block looks
  complete. Set it (e.g. `"300"`).
- **`validate_flow_json` does NOT validate per-action `Parameters`.** It checks
  structure/identifiers/transitions only, so a flow can pass local validation
  and still be rejected live with `InvalidContactFlowException`. Treat a clean
  `validate_flow_json` as necessary, not sufficient — the deploy is the real
  test.

## Verification snippets that cut hypotheses fast

- **Rule out model access** (proves it's NOT the model) — direct Converse:
  ```bash
  aws bedrock-runtime converse --model-id global.anthropic.claude-haiku-4-5-20251001-v1:0 \
    --messages '[{"role":"user","content":[{"text":"hi"}]}]' \
    --profile <profile> --region <region>
  ```
  If this returns tokens, the model and role access are fine — stop chasing it.
- **Test the backend directly** (proves it's NOT the API/Lambda) — call API
  Gateway with the api key:
  ```bash
  curl -s -H "x-api-key: <key>" "https://<api-id>.execute-api.<region>.amazonaws.com/<stage>/<path>"
  ```
- **MCP gateway can't be easily tested outside Connect**: a raw call to the
  AgentCore gateway returns `Invalid Bearer token` without a Connect-issued
  JWT. Don't interpret that as the gateway being broken — it just means you
  can't mint the token by hand. Validate the gateway via an `execute_tool`
  span instead.

## Quick reference — IDs/paths worth capturing per investigation

- assistant id, instance id + alias, failing agent id, a known-good agent id
- the AI-agent event-log group `/aws/connect/qic-ai-agent/<alias>`
- prompt id(s) and versions; the model id on each prompt
- MCP gateway id + target name; KB assistant-association id
- deploy command and profile/region

## Getting customer data into the agent prompt as `$.Custom.*` (session data)

Field-tested while building the `set-customer-session-telco` module + the
`ai-session-telco` Lambda (telco-cx). The goal: surface a looked-up customer
record into the orchestrator prompt's `<customer_info>` block via
`{{$.Custom.<field>}}`. Several non-obvious traps, in the order they bit us:

1. **`$.Custom.*` is written ONLY by `qconnect:UpdateSessionData`.** The
   `InvokeLambdaFunction` block's `ResponseValidation.ResponseType: STRING_MAP`
   result surfaces as `$.External.*`, NOT `$.Custom.*`. To populate the agent
   prompt you must have a Lambda call `UpdateSessionData(assistantId, sessionId,
   data=[{key, value:{stringValue}}])`. The STRING_MAP return is only for the
   flow's own branching/attribute writes.

2. **IAM: grant BOTH `wisdom:UpdateSessionData` AND `qconnect:UpdateSessionData`.**
   The boto3 client is `qconnect`, but Q in Connect authorizes the call under
   the legacy `wisdom:` action prefix at runtime. Granting only
   `qconnect:UpdateSessionData` yields `AccessDeniedException ... is not
   authorized to perform: wisdom:UpdateSessionData`. (Same `wisdom:` vs
   `qconnect:` quirk as `CreateAIAgent` / `ListSpans`.) Scope to
   `arn:aws:wisdom:<region>:<acct>:session/<ASSISTANT_ID>/*`.

3. **`$.Wisdom.SessionArn` is flow-scoped and is EMPTY inside an invoked flow
   module.** This is the big one. `CreateWisdomSession` sets `$.Wisdom.SessionArn`
   in the *parent* flow, but an `InvokeFlowModule`'d module runs in its own
   namespace — `$.Wisdom`, `$.External`, `$.Lex` from the parent are NOT
   visible inside the module. Passing `wisdomSessionArn: $.Wisdom.SessionArn`
   from a `LambdaInvocationAttributes` inside the module resolves to `""`, so
   the Lambda silently skips the write and every `$.Custom.*` renders blank.
   Two working fixes:
   - **(preferred) Resolve the session inside the Lambda** via
     `connect:DescribeContact(ContactId, InstanceId)` →
     `Contact["WisdomInfo"]["SessionArn"]`. No flow plumbing; needs
     `connect:DescribeContact` on `instance/<id>/contact/*`. This is the
     pattern the AWS "Customer profile lookup" sample module uses (its
     `UpdateSessionData` Lambda passes NO session ARN).
   - **(alt) Hand it over as a contact attribute.** Contact attributes
     (`$.Attributes.*`, set via `UpdateContactAttributes` / Set contact
     attributes) ARE shared parent↔module and survive the whole contact. Set
     `wisdomSessionArn` in the parent before the `InvokeFlowModule`, read
     `$.Attributes.wisdomSessionArn` inside the module. (A plain
     `UpdateContactAttributes` user attribute is NOT the same as the
     connect-defined `UpdateContactData {WisdomSessionArn}` association — only
     the latter populates `Contact.WisdomInfo` for `DescribeContact`.)

4. **`Contact.WisdomInfo.SessionArn` timing.** It is populated once the Wisdom
   session is associated to the contact (the `CreateWisdomSession` block, whose
   console form expands to `CreateWisdomSession` + a `SetContactData`/
   `UpdateContactData {WisdomSessionArn}` fragment). If a module's Lambda calls
   `DescribeContact` *before* the session is associated you get a `KeyError`/
   missing `WisdomInfo`. In practice, invoking the module right after the
   `connect-assistant` (`CreateWisdomSession`) block, `DescribeContact` resolved
   the session fine — but always confirm via the Lambda log on a real call.

5. **Always log the resolution outcome while debugging session writes.** The
   handler logged nothing on success/skip at first, so an empty `$.Custom.*`
   was indistinguishable from "wrote successfully but agent reads a different
   session." A one-line log of `session_arn` presence + `session_updated`
   immediately pinned it to the empty-`$.Wisdom`-in-module cause. Strip verbose
   logging back to failure-only once confirmed.

6. **Diagnose the chain in order:** (a) direct-invoke the Lambda with a known
   key to prove the data lookup + response contract; (b) read the Lambda log to
   see whether the session ARN resolved and the write happened; (c) read the
   agent span to confirm the rendered `<customer_info>` block. Empty fields with
   a clean Lambda run almost always = the session ARN never resolved (trap #3),
   not a DynamoDB/lookup problem.

### Cross-stack / module wiring notes (same feature)

- A flow module's id for an `InvokeFlowModule` block is derived from its ARN
  with `Fn.select(1, Fn.split("/flow-module/", arn))`. For a same-stack module,
  read `module.module_arn`; for a cross-stack handoff, publish the ARN to SSM in
  the producer stack and `ssm.StringParameter.value_for_string_parameter` +
  `Fn.split` in the consumer.
- Prefer co-locating a module and the Lambda it invokes in the **same stack**
  (one deploy, no SSM ordering) unless the module is genuinely shared.
- Editing a prompt YAML that an agent reads only takes effect if a NEW prompt
  version is minted — see the "CDK version no-re-mint trap" above (content-hash
  the version construct id).
