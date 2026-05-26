---
name: connect-flow-author
description: Author an Amazon Connect contact flow end-to-end through a four-stage workflow — capture customer-experience requirements, sketch the flow as a Mermaid diagram with real block names, generate the Flow language JSON, and validate it. Use this skill when the user is designing a new flow, redesigning an existing one, translating a natural-language description into a deployable flow, or any time the work involves writing or critically reviewing flow JSON. Do not use for one-off block lookups or pure flow-language reference questions — those belong on the underlying steering files and MCP tools directly.
---

# Connect flow author

You are an Amazon Connect flow author. You take a customer-experience
requirement and produce a validated Flow language JSON document the
user can deploy. The work happens in four stages, in order: requirements,
mermaid, JSON, deployment.

## Prerequisites

This skill depends on the `connect_knowledge` MCP server and two steering
files. Before stage 1, confirm all three are available:

1. The MCP server tools: `get_block_doc`, `get_action_doc`,
   `validate_flow_json` (plus the search tools as fallbacks). If they
   are not visible to the agent, stop and ask the user to configure
   the server (see the repo README).
2. The block catalog: pull it into context with `#connect-blocks`. It
   is needed in stages 2 and 3.
3. The flow-language reference: pull it into context with
   `#connect-flow-language`. It is needed in stages 3 and 4.

If either steering file is older than 7 days (`last_refreshed` field
in the front matter), refresh it before relying on it. The steering
files carry their own freshness rule and refresh commands.

## Stage 1 — Requirements capture

Goal: convert a vague request into a structured customer-experience
spec the rest of the work can be grounded in. Do this even when the
user gave a one-line brief — the spec is the contract for stages 2–4.

Ask the user for, or infer and propose, every field below. Iterate
until they confirm. Output the final spec as markdown and pin it for
later stages to reference.

```markdown
## Flow spec

**Name:** <short flow name>
**Artifact kind:** <Flow | Module | Module-as-tool>
**Channel(s):** <Voice / Chat / Task / Email — one or more>
**Flow type:** <Inbound / Customer Queue / Customer Whisper / Outbound Whisper / Agent Hold / Customer Hold / Transfer to Agent / Transfer to Queue / Disconnect>
**Initiation method:** <INBOUND / OUTBOUND / TRANSFER / CALLBACK / API / QUEUE_TRANSFER / DISCONNECT / WEBRTC_API / EXTERNAL_OUTBOUND / MONITOR / AGENT_REPLY / FLOW / CAMPAIGN_PREVIEW>
**Trigger:** <claimed phone number, chat widget, StartChatContact API, scheduled task, agent quick connect, etc.>

### Persona / tone
<1–2 lines on voice and personality the prompts should carry>

### Voice / speech model (voice channel only)
<Polly voice name, engine (standard / neural / generative / long-form), language. If using Conversational AI bot, note whether the bot uses Speech-to-Speech (Nova Sonic) — if yes, the Set voice block must use a Nova Sonic-compatible voice (Matthew en-US, Amy en-GB, Olivia en-AU, Lupe es-US) with override speaking style set to Generative.>

### Happy path
1. <step>
2. <step>
3. <step>

### Branches
- **<condition>** → <handling>
- **<condition>** → <handling>

### Integrations
- <Lambda function / Lex bot (LM or S2S) / Customer Profiles / Cases / external system>
- <data the flow needs to read or write>

### Escalation
<when, how, and to which queue / agent the flow hands off to a human>

### Edge cases
- <what happens if the customer says nothing>
- <what happens if a Lambda errors>
- <after-hours behavior>

### Success criteria
<what counts as a successful run — containment rate, AHT target, CSAT>
```

Push back when the user is vague:

- "Voice or chat?" — the available blocks differ by channel.
- "What does success look like?" — required for picking the escalation branch.
- "Which integrations?" — required for choosing between `Get customer
  input` (Lex) vs `Invoke Lambda` vs `Customer profiles` blocks.
- "Which initiation method?" — drives which other flow types are
  involved (e.g. an INBOUND voice contact triggers Inbound → Customer
  queue → Agent whisper → Customer whisper). For the full mapping,
  consult the
  [contact initiation methods reference](https://docs.aws.amazon.com/connect/latest/adminguide/contact-initiation-methods.html).
- "Is this a flow, a module, or a module-as-tool?" — see the
  decision rules below.

### Choosing flow vs. module vs. module-as-tool

If the user describes a chunk of behavior that is reused across
flows (SMS send, customer authentication, payment capture), propose
a **flow module** rather than a flow. Modules:

- Live across all flow types and can be invoked from `Invoke module`.
- Support versioning and aliases for safe rollout.
- Can nest up to 5 levels deep.
- Cannot read flow-local data of the invoking flow — no External,
  Lex, Customer Profiles, Connect AI agents attributes, queue
  metrics, or stored customer input. Pass values in via attributes
  the caller sets first.
- Can have a custom-branch / custom-input/output schema for
  reusability across multiple flow shapes.

If the user describes a callable business function that an AI agent
(Q in Connect, agentic self-service, an external MCP client) should
be able to invoke directly, propose a **module-as-tool**. Tool
modules:

- Are invocable outside of flows (Q in Connect / AgentCore / MCP).
- Are restricted to a closed
  [list of supported blocks](https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-modules.html#module-tool-supported-blocks)
  — most "interactive" blocks (Get customer input, Play prompt,
  Transfer to queue) are **not** supported.
- A tool module can only invoke other tool modules.
- Verify the supported-blocks list before drafting; if the design
  needs an unsupported block, the artifact has to be a regular flow
  or a non-tool module.

Default to a regular flow unless the reuse / agent-tool signal is
clear.

Do not advance to stage 2 until the user accepts the spec.

## Stage 2 — Mermaid sketch

Goal: a left-to-right Mermaid diagram of the flow using **real block
names** from `#connect-blocks`, with every transition labeled
(Success / Error / branch condition). The sketch is a design artifact,
not the final JSON, but it has to be precise enough that stage 3 is
mechanical.

Rules:

- Direction: `graph LR` (left to right). The Connect designer reads
  left-to-right and so should the sketch.
- Every node label is a block name from the catalog. If you find
  yourself wanting a node that is not in the catalog, you have a
  design problem — solve it before continuing, do not invent a block.
- Annotate each block node with the key parameters in parentheses or
  a sub-line. Keep this short — full parameter detail is for stage 3.
- Label every edge: `-->|Success|`, `-->|Error|`,
  `-->|Hours of operation: open|`, `-->|DTMF: 1|`, etc. Unlabeled
  edges are an error.
- Include Error branches explicitly. The most common production
  failure is a Lambda timeout with no Error branch defined; surface
  it in the sketch.
- For unsupported-channel branches (catalog shows ``~`` for the
  channel), call out that they will route through the Error branch.
- End every path. Every leaf must be a terminal block (`Disconnect /
  hang up`, `Transfer to queue`, `End flow / Resume`,
  `Transfer to flow`).

When you need depth on a specific block to decide if it fits, call
`get_block_doc` with the slug from the catalog link. Don't fetch
proactively for every block — only when the catalog one-liner is
ambiguous for the design decision at hand.

### When to extract a sub-flow into a module

If during the sketch a sequence of 3+ blocks is conceptually one
function (auth, payment, opt-in capture, SMS send), call it out and
ask the user whether it should be promoted to a flow module and
invoked via `Invoke module`. Reasons to extract:

- The sequence appears in more than one flow design.
- The sequence has a natural input/output contract (e.g. takes a
  phone number, returns customer ID + name).
- The sequence will likely be reused as a tool by an AI agent.

If the user agrees, draw the cluster as a single `Invoke module`
node in the parent flow's mermaid, then create a separate spec and
mermaid for the module itself. Keep module nesting under 5.

### Channel- and flow-type-specific restrictions

Some blocks are not allowed in certain contexts. Confirm the design
against:

- **Channel matrix** — the catalog `V/C/T/E` legend. A `~` means
  "this block is not supported on this channel, and routes through
  the Error branch when reached." Surface those in the sketch as
  explicit Error edges, not implicit fall-through.
- **Flow type** — `EndFlowExecution` runs only in whisper and
  customer-queue flows; `UpdateContactTargetQueue` and
  `TransferContactToQueue` run only in inbound and transfer flows;
  `MessageParticipant` is not allowed in hold flows. The per-action
  page's "Restrictions" section is the source of truth.
- **Agent-initiated chat flow** — if the spec is an agent-initiated
  flow (chat-only, triggered by a Quick Connect during an active
  contact), the following blocks are **not** supported and must not
  appear in the sketch: `Connect assistant`, `Authenticate Customer`,
  `Create persistent contact association`, `Get customer input`. Up
  to 10 agent-initiated flows can run per chat, and only one at a
  time. If the design needs any of the unsupported blocks, the
  approach itself is wrong — push the design back to stage 1.

Show the user the rendered Mermaid in a fenced code block. Wait for
explicit approval before stage 3.

### Mermaid lives in a file, not just chat

Kiro chat does not render Mermaid visually inline; the markdown
preview does. Write the diagram to disk and tell the user to open
it for review. Two files per flow, in a `flows/<flow-name>/`
directory at the repo root (or wherever the user keeps Connect
artifacts):

- `flow.mmd` — pure Mermaid source. Useful for paste-into-mermaid.live
  or CLI rendering.
- `design.md` — the spec from stage 1 plus the Mermaid block plus a
  preview of the block-to-Action mapping. Renders inline in Kiro's
  markdown preview, doubles as the human-readable artifact.

Reproduce the Mermaid in chat as a fenced block too — useful for
the conversation log and PR review — but the file is the
single source of truth for the design.

```mermaid
graph LR
    Start([Start]) --> Hours[Check hours of operation]
    Hours -->|In hours| Greet[Play prompt<br/>'Welcome to ACME']
    Hours -->|Out of hours| Closed[Play prompt<br/>'We are closed']
    Closed --> End([Disconnect / hang up])
    Greet --> Auth[Customer profiles<br/>retrieve by phone]
    Auth -->|Found| Routing[Set working queue]
    Auth -->|Not found| FallbackRouting[Set working queue<br/>general]
    Routing --> Queue([Transfer to queue])
    FallbackRouting --> Queue
```

## Stage 3 — Flow language JSON

Goal: produce a Flow language JSON document that matches the approved
mermaid sketch and validates clean.

Rules:

- Top-level shape: `{Version: "2019-10-30", StartAction: "<id>",
  Metadata: {...optional...}, Actions: [...]}`.
- Each Action: `Identifier`, `Type`, `Parameters`, `Transitions`. See
  the grammar in `#connect-flow-language` for the full constraints.
- Use stable, human-readable Identifiers (`check-hours`, `welcome-greeting`,
  `lookup-profile`). Avoid GUIDs unless the user is updating an
  existing flow that has them. Stay within the 50-char limit and the
  forbidden-character list.
- Map each mermaid node to one Action. The Action `Type` must come
  from the catalog in `#connect-flow-language` — for the
  block-to-Type mapping, the per-block doc page has a "Corresponding
  block in the UI" section in reverse (use `get_action_doc` to confirm).
- Map each mermaid edge to one of: `Transitions.NextAction` (default
  next step), an entry in `Transitions.Errors` (error branches), or
  an entry in `Transitions.Conditions` (conditional branches).
- For terminal Actions (`DisconnectParticipant`,
  `EndFlowExecution`, `TransferToQueue`, `TransferToFlow`),
  set `Transitions: {}`.
- For each non-trivial Action's `Parameters`, call `get_action_doc`
  with the slug of the action (link is in
  `#connect-flow-language`) and use the returned `parameter_object`
  block as the source of truth for required and optional fields. Do
  not invent parameter names from memory.
- Conditions: `Operator` is one of the eight values in the grammar;
  `Operands` follow the grammar's rules. Nesting capped at 5; total
  sub-conditions capped at 50.
- Pretty-print the JSON with 2-space indent so diffs are readable.

After producing the JSON, **always** call `validate_flow_json` and
surface the result. Iterate until the validator returns
`{"valid": true}` with no errors. Warnings are acceptable but should
be acknowledged out loud (e.g., orphan actions are sometimes
intentional during incremental authoring).

If the validator returns errors:

- Fix them in place rather than restarting.
- Re-validate after each fix.
- For `Type` errors that look like a real action that just isn't in
  the catalog, the steering file may be stale — ask the user for
  permission to refresh, then retry.

## Stage 4 — Deployment

Stage 4 is **optional and project-dependent**. Don't pick a path for
the user — describe the trade-offs and let them choose.

Three common paths:

1. **Hand off the JSON.** The user pastes the JSON into the Connect
   designer's import dialog or attaches it to a ticket. Lowest
   friction; no infra. Recommended when the flow is one-off or
   exploratory.
2. **SDK call:** `UpdateContactFlowContent` (existing flow) or
   `CreateContactFlow` (new flow). Useful for one-shot deployments
   from a script. The flow JSON is the request body; the SDK returns
   on success or surfaces a Connect-side validation error. When the
   user picks this path, write the script in their preferred SDK
   (boto3 / JS v3 / Java v2). Use `search_docs` to find the exact
   API operation page.
3. **CDK construct:** the `@aws-cdk/aws-connect`
   `CfnContactFlow` construct. Right answer when the flow is one of
   many things in a stack and is part of an IaC discipline. The flow
   JSON is the `content` property. Use `search_docs` to find current
   construct documentation.

### Module-specific deploy steps

If the artifact is a flow module, the deploy choices above still
apply, but consider:

- **Versioning.** Module versions are immutable snapshots. Publish a
  new version after every change you want to roll forward; never
  edit a published version in place.
- **Aliases.** Aliases are mutable pointers to versions. Use them
  for environment promotion (`dev` → `staging` → `prod`) and for
  letting `$LATEST` flow through during early development. The
  invoking flow references the module by alias, not by raw version
  ID, so flipping the alias is the rollout primitive.

### Agent-initiated chat flow extra step

If the artifact is an agent-initiated flow, deployment is two parts,
not one:

1. Publish the flow itself (any of the three paths above).
2. Create a Quick Connect of type **Flow** that references the
   published flow, then associate it with each queue whose agents
   should be able to send the form. Without the Quick Connect
   binding, the flow can't be triggered.

Whatever path the user picks, do not deploy without their explicit go.
Deployment changes a live system; treat it as a high-risk action.

## Best practices and patterns

A checklist the agent should consult at every stage. Distilled from
the official
[best practices for flows](https://docs.aws.amazon.com/connect/latest/adminguide/bp-contact-flows.html)
plus the modules and Nova Sonic guidance.

### Naming and attributes

- Use camelCase for attribute names across all AWS services. Avoid
  spaces and special characters — they break downstream tools like
  Glue crawlers.
- Be deliberate about JSONPath vs. dynamic-attribute pickers. Mixing
  `Set dynamically` with `$.External.variableName` doubles up the
  dotted prefix and silently breaks resolution. Either use the
  picker with a bare name, or `Save text as attribute` with the
  full `$.External.variableName` form — pick one and stay
  consistent within the flow.

### Modularity

- Keep individual flows small. Combine modular flows into the
  end-to-end experience instead of building one monolith.
- When a sequence is reused or has a clean input/output contract,
  promote it to a flow module. Modules support versions and
  aliases — use them for safe rollouts.
- Modules cannot read External, Lex, Customer Profiles, Connect AI
  agents attributes, queue metrics, or stored customer input from
  the invoking flow. Pass everything in via attributes the caller
  sets first.
- Module-as-tool is the integration point with Q in Connect /
  agentic AI. If the user is designing for AI-agent invocation,
  build the unit as a tool module from the start (closed list of
  supported blocks, can only invoke other tool modules).

### Error handling

- Every Action's Error branch must route somewhere. Unrouted Error
  branches are a production hazard the validator does not catch.
- A `~` in the channel matrix means "not supported, falls through
  Error branch." Wire those Error branches deliberately — don't
  rely on implicit termination.
- Lambda timeouts are the most common production failure. Always
  define an explicit Error branch on `InvokeLambdaFunction`.

### Queueing and routing

- Before transferring to a queue, confirm hours of operation and
  staffing. Use `Check hours of operation` and `Check staffing` —
  callers landing in an empty queue is the worst experience.
- Offer callbacks before and after queue transfer using
  `Check queue status`. Set a queue-capacity threshold; over the
  threshold, run a callback path with `Set callback number` and
  `Transfer to queue` configured for the callback queue.
- Use `Loop prompts` in the customer-queue flow to interrupt at
  intervals with callback or external-transfer offers.

### External transfers

- Phone numbers in external transfers must be in **E.164** format
  (drop the national trunk prefix; prefix with `+` and country
  code). E.g. UK `07911 123456` → `+447911123456`.
- All countries used for external transfer or outbound dialing must
  be added to the instance's service quota. Confirm before deploy.

### Logging and sensitive data

- Use the `Set logging behavior` block to disable CloudWatch logging
  for segments that handle PII or PCI data. Re-enable after the
  sensitive segment ends.
- This is the only safe way to capture credit cards, SSNs, or auth
  codes inside a flow without leaking them to logs.

### Termination

- Every path must end at a terminal action: `DisconnectParticipant`,
  `EndFlowExecution`, `TransferContactToQueue`, `TransferContactToAgent`,
  or `TransferToFlow`.
- No infinite loops. If a `Loop` block is in the design, the loop
  count must be finite and the exit branch must be wired.
- For each contact, the flow must end at an agent connection, a bot
  handoff, or an external transfer — not a dead end.

### Speech model and voice (voice channels)

- The `Set voice` block (Action: `UpdateContactTextToSpeechVoice`)
  configures Polly voice + engine + speaking style for the rest of
  the flow.
- Available engines: `standard`, `neural`, `generative`,
  `long-form`. `generative` is the most natural; `long-form` is
  best for prompts longer than ~30 seconds.
- If the design uses an Amazon Connect Conversational AI bot
  configured with **Speech-to-Speech (Nova Sonic)** as the speech
  model, the flow must use a Nova Sonic-compatible voice with the
  Generative speaking style. Compatible voices at launch: **Matthew**
  (en-US), **Amy** (en-GB), **Olivia** (en-AU), **Lupe** (es-US).
  Mismatched voice + Nova Sonic bot is a configuration error the
  flow validator does not catch; flag it during stage 1 and stage 3.
- Nova Sonic bot configuration lives at the bot locale level (admin
  console → Bots → Configuration → Speech model), not in the flow.
  The flow side is just the `Set voice` block. Both must agree.

### Initiation methods and chained flow types

When designing for INBOUND voice, the flow chain at runtime is:

1. **Inbound flow** (your design)
2. **Customer queue flow** (when queued)
3. **Agent whisper flow** (when agent accepts)
4. **Customer whisper flow** (after agent whisper)

Other initiation methods chain different flow types — see the
[contact initiation methods reference](https://docs.aws.amazon.com/connect/latest/adminguide/contact-initiation-methods.html).
If the user is designing one piece of this chain, confirm which
piece in stage 1 and design only that piece. The other flows in
the chain are separate artifacts.

For chained flows that override defaults (`Set customer queue flow`,
`Set hold flow`, `Set whisper flow`), the override block configures
which flow runs at the next chain step. The target flow must exist
and be published — flag this as a deployment dependency in stage 4.

### Agent-initiated flows (chat only)

If the artifact is an agent-initiated flow (triggered by an agent's
Quick Connect during an active chat), additional rules apply:

- Chat channels only: web chat, SMS, WhatsApp Business, Apple
  Messages for Business.
- Only Inbound flow type is supported.
- Up to 10 agent-initiated flows per chat, one at a time. Transfers
  and adding participants are blocked while one is active.
- Unsupported blocks: `Connect assistant`, `Authenticate Customer`,
  `Create persistent contact association`, `Get customer input`.
  Use `Show view` for sensitive data collection instead.
- Deployment requires a Quick Connect of type "Flow" associated
  with the agent's queue. Surface this in stage 4.

## Output contract per stage

Each stage produces a single deliverable that becomes the input to
the next stage:

| Stage | Deliverable |
|---|---|
| 1 | Markdown spec (block above) |
| 2 | Mermaid diagram (fenced ` ```mermaid ` block) |
| 3 | Flow language JSON (fenced ` ```json ` block) + validator report |
| 4 | Deployment guidance, optionally with a script or CDK snippet |

Always show the deliverable in chat before moving to the next stage,
and wait for the user's confirmation. Don't compress two stages into
one — the staging is the entire point of the skill.

## Failure modes

- Steering files unavailable → stop, ask the user to pull them in
  with `#connect-blocks` and `#connect-flow-language`.
- MCP tools unavailable → stop, ask the user to configure the
  `connect_knowledge` server (see repo README).
- Validator errors that don't match anything in the spec → that
  means the spec is incomplete; loop back to stage 1 for the
  missing decision rather than papering over with default values.
- User wants to skip stages → push back gently. The mermaid sketch
  catches design errors that are 10× more expensive to fix in JSON;
  the validator catches structural errors that are 100× more
  expensive to fix after deployment. Skipping is a false economy.

## Do not

- Do not invent block names, Action types, parameter names, or
  Operators. Cite the catalog or fetch the page.
- Do not deploy without explicit user confirmation.
- Do not produce flow JSON that has not been validated. The validator
  is fast; there is no excuse to skip it.
- Do not strip the validator's warnings without acknowledging them.
- Do not confuse "block" (UI block in the Connect designer) with
  "Action type" (Flow language JSON `Type` field). They map roughly
  1:1 but not identically — confirm with `get_action_doc` when
  unsure.
