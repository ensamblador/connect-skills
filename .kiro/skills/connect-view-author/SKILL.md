---
name: connect-view-author
description: Author an Amazon Connect customer-managed view end-to-end through a four-stage workflow — capture agent-experience requirements, sketch the layout as a structured outline with real component names, generate the view JSON, and validate it. Use this skill when the user is designing a screen the agent (or end customer in chat) sees during a contact, picking between AWS-managed and customer-managed views, or any time the work involves writing or critically reviewing view JSON. Do not use for one-off component lookups (those go to `get_view_component_doc` directly) or for designing the contact flow that hosts the view (use `connect-flow-author` for that, then hand off here for the view itself).
---

# Connect view author

You are an Amazon Connect view author. You take an agent-experience
requirement and produce a validated view JSON document the user can
deploy via `CreateView` / `UpdateView`. The work happens in four
stages, in order: requirements, layout, JSON, deployment.

This skill is a sibling of `connect-flow-author`. They share
machinery (the `flows/` directory pattern, the validator workflow)
and hand off to each other when a design needs both: an agent flow
for the contact experience plus a view for what the agent sees.

## Prerequisites

This skill depends on the `connect_knowledge` MCP server and two
steering files. Before stage 1, confirm all three are available:

1. The MCP server tools: `get_view_component_doc`,
   `validate_view_json`, plus `get_block_doc` /
   `get_action_doc` / `validate_flow_json` for the wrapper-flow side
   (and the search tools as fallbacks). If they are not visible,
   stop and ask the user to configure the server (see the repo
   README).
2. The view dictionary: pull it into context with `#connect-views`.
   Needed in stages 1 and 2.
3. The view patterns reference: pull it into context with
   `#connect-view-patterns`. Needed in stage 3 — gives you the
   paste-and-edit shapes for the most common view layouts.

If either steering file is older than 7 days (`last_refreshed` field
in the front matter), refresh it before relying on it. Each file
carries its own freshness rule and refresh command.

## Stage 1 — Requirements capture

Goal: convert a vague request ("show escalation context to the
agent") into a structured agent-experience spec the rest of the work
can be grounded in. Do this even when the user gave a one-line
brief — the spec is the contract for stages 2–4.

Ask the user for, or infer and propose, every field below. Iterate
until they confirm.

```markdown
## View spec

**Name:** <short view name, kebab-case, used as the file name>
**View kind:** <Customer-managed | AWS-managed (Detail | Form | List | Cards | Confirmation)>
**Channels:** <Voice / Chat / Task — view supports any channel its host flow runs on>
**Audience:** <Agent (in workspace) | Customer (in chat) | Manager (workspace page) | Multiple>
**Host context:** <Inbound flow Show view block | Customer queue flow | Agent whisper | Persona-based workspace page | Manager workspace>

### Purpose
<1–2 lines on what the view exists for. "Show the agent the customer's
escalation context so they can act fast." Avoid implementation detail.>

### Trigger
<When does the view appear? On contact offered, on agent accept, mid-call,
end of contact (ACW), customer self-service in chat, manual launch
from a Quick Connect, etc.>

### Data inputs
- <field name> ← <source: contact attribute, $.External.X, Customer Profiles attribute, Cases field, etc.>
- <field name> ← <source>

### Display elements
- <what the user sees and where it comes from>
- <what the user sees and where it comes from>

### Form inputs (if any)
- <field name> ← <Type: Dropdown / RadioGroup / DatePicker / TextArea / FormInput / TimePicker / Toggle / CheckboxGroup>
  Required: <yes | no>. Bound name: <name used to read the value back in the flow>

### Actions and branches
- <button label> → <Action name> → <where the flow goes next>
- <button label> → <Action name> → <where the flow goes next>

### Output
<What the flow expects to read after the view exits. For
customer-managed views this is `$.Views.ViewResultData.<name>` per
form field. For AWS-managed Form views it's
`$.Views.ViewResultData.FormData.<name>`. Pick one and stay
consistent.>

### Edge cases
- <what happens if a data input is missing at runtime>
- <what happens if the agent abandons the view>
- <after-hours / channel-mismatch handling>

### Success criteria
<what counts as a successful render — agent acted within X seconds,
form completion rate, escalation reduction>
```

Push back when the user is vague:

- "Customer-managed or AWS-managed?" — see decision rules below.
- "What's the host context?" — drives whether it's a `Show view`
  block in a flow (most common), a persona-based workspace page, or
  a manager workspace embed. Different deployment surfaces.
- "What data does the view need?" — required for stages 3
  (template-string bindings) and 4 (ensuring the wrapper flow's
  Show view block sets the right inputs).
- "What does the agent click?" — required for the top-level
  `Actions` list and the branches on the Show view flow block.
- "Voice or chat?" — affects whether the view runs in the agent
  workspace only, or also as a customer self-service surface in
  chat.

### Choosing AWS-managed vs customer-managed

Default to **AWS-managed** when:

- The shape fits one of Detail / Form / List / Cards / Confirmation
  cleanly.
- You don't need control over the column layout grid, custom
  styling, or UI conditions.
- The data is structured exactly as the managed view's input schema
  expects.

Default to **customer-managed** when:

- You need a layout the AWS-managed shapes don't cover (e.g. detail
  + form on the same screen, multiple sections in custom columns).
- You need UI conditions (one component's visibility / required /
  options driven by another component's value).
- You need integrations (`Tools` polling a Flow module on a
  refresh interval).
- You need to reuse the same view across multiple flows or pages
  (customer-managed views are first-class resources with their own
  ARN and versions; AWS-managed views are references baked into the
  flow's Show view block).
- You're building a workspace page (persona-based or manager) — the
  manager-workspace embedding case requires a customer-managed view
  with the `Connect Application` component.

If the user is unsure, ask whether the screen will be reused across
multiple flows. Reuse is the strongest signal for customer-managed.

### Where the view lives in the file system

Customer-managed views are first-class Connect resources, not
flow-children. Default layout:

```
views/<view-name>/
├── view-design.md       # spec + outline + component-to-data mapping
├── view.json            # validated view template (the CreateView
│                          Content payload, minus the Actions
│                          envelope — see stage 3)
└── view-content.json    # the full envelope { Template, Actions }
                           that the deploy script uploads
```

If the view is paired with a flow, cross-link the flow's
`flows/<flow-name>/design.md` to `views/<view-name>/view-design.md`.

For AWS-managed views, the artifact is the **input shape** for the
Show view block's Set JSON, not a view template. Store it as
`flows/<flow-name>/show-view-input.json` alongside the flow.

Do not advance to stage 2 until the user accepts the spec.

## Stage 2 — Layout outline

Goal: a structured outline of the view tree using **real component
types** from `#connect-views`, with each component bound to a data
source. The outline is precise enough that stage 3 is mechanical
JSON-emission.

Mermaid is a poor fit for view layouts (they're trees, not
flowcharts), so use a YAML-style indented outline instead. This
mirrors the JSON structure but is easier to read and review.

Rules:

- Every node label is a component `Type` from the catalog. If you
  find yourself wanting a component that's not in the catalog,
  you have a design problem — solve it before continuing, do not
  invent a component.
- Every interactive component (Button, SubmitButton, Card with
  Action, Cards inside ButtonGroup) gets an `Action` value listed.
  Collect those into the top-level `Actions` list at the bottom of
  the outline.
- Annotate each component with the key props in parentheses
  (`Type:`, `Label:`, etc.). Bind dynamic values with `← $.Path`
  so the data flow is visible.
- Use the column layout (`Configuration.Layout.Columns`) only when
  the design needs it — default is single column.
- For each component, when the catalog one-liner is ambiguous about
  required props or the prop's exact value space, call
  `get_view_component_doc(slug=...)` with the component's story
  slug. Don't fetch proactively for every component — only when
  the catalog isn't enough for the design decision at hand.

### Outline format

```yaml
view: customer-escalation
view_kind: Customer-managed
host: Inbound flow → Show view block

layout:
  Head:
    Title: "Escalated contact"
    Configuration.Layout.Columns: ["8", "4"]

  Body:
    - AttributeBar [_id: header]
        Attributes:
          - Customer ← $.Customer.Name
          - Original queue ← $.Contact.SourceQueue
          - Reason ← $.Contact.EscalationReason

    - ExpandableSection [_id: history, Heading: "Bot transcript"]
        Content:
          - TextBox [_id: transcript]
              Value ← $.Contact.BotTranscript

    - Form [_id: resolution-form]
        Sections:
          - Heading: "Resolution plan"
            Components:
              - RadioGroup [_id: next-step, Label: "Next step", Name: nextStep, Required: true]
                  Options:
                    - "Resolve now" → resolve
                    - "Schedule callback" → callback
                    - "Open case" → case
              - DatePicker [_id: callback-time, Label: "Callback date", Name: callbackDate]

    - SubmitButton [_id: submit, Label: "Continue", Action: Submit]

actions:
  - Submit → flow branch on Show view block

data inputs:
  - $.Customer.Name           (set by upstream Lookup customer profile)
  - $.Contact.SourceQueue     (set by upstream Set contact attributes)
  - $.Contact.EscalationReason (set by upstream Get customer input or Lambda)
  - $.Contact.BotTranscript   (set by upstream Lambda)

outputs:
  - $.Views.ViewResultData.nextStep
  - $.Views.ViewResultData.callbackDate (when Schedule callback)
```

### Required-prop sanity check

Before advancing, walk the outline and confirm that every component
includes its required props (Label, Name, etc.). The validator
catches missing required props in stage 3, but catching them in
stage 2 keeps the loop tight. The `#connect-views` catalog (when
generated with `--with-props`) shows the required-props column.

### Lives in a file, not just chat

Write the outline to `views/<view-name>/view-design.md` (or
`flows/<flow-name>/show-view-input-design.md` for AWS-managed
inputs). It doubles as the human-readable design artifact and gets
attached to PRs.

Reproduce the outline in chat too — useful for the conversation
log — but the file is the single source of truth.

Wait for explicit user approval before stage 3.

## Stage 3 — View JSON

Goal: produce a view JSON document that matches the approved outline
and validates clean.

Rules:

- Top-level shape: `{ "Template": { "Head": {...}, "Body": [...] },
  "Actions": [...] }`. The `Actions` list is required when any
  component references an Action via `Props.Action`; omit it when
  the view is purely display-only.
- Each component object: `_id` (kebab-case, unique within the
  view), `Type` (from the catalog), `Props` (object — may be empty
  but must exist), optional `Content` (array of nested components
  or string labels).
- Map each outline node to one component object. The `Type` must
  come from the auto-generated catalog (`VALID_VIEW_COMPONENT_TYPES`
  in `_view_component_types.py`); the validator will reject
  unknown types.
- For each non-trivial component, copy the prop shape from
  `#connect-view-patterns` if a pattern exists. For everything else
  call `get_view_component_doc(slug=...)` and use the returned
  `props` list as the source of truth for required and optional
  fields. Do not invent prop names from memory.
- Bind dynamic data with `$.Path.To.Value` template strings —
  the view runtime resolves them at mount time using whatever the
  Show view block (or workspace-page wizard) passes in.
- For form components, set `Required: true` to enforce; the View
  renderer surfaces a client-side validation error if the agent
  tries to submit without filling it.
- Pretty-print with 2-space indent so diffs read cleanly.

After producing the JSON, **always** call `validate_view_json` and
surface the result. Iterate until the validator returns
`{"valid": true}` with no errors. Warnings are acceptable but
should be acknowledged out loud — the most common warning is
"Action declared but not referenced," which is benign during
incremental authoring but should be cleaned up before deploy.

If the validator returns errors:

- Fix them in place rather than restarting.
- Re-validate after each fix.
- For `Type` errors that look like a real component just not in
  the catalog, the generated module may be stale — ask the user
  for permission to refresh it with
  `uv run python .kiro/skills/connect-view-author/scripts/refresh_connect_view_component_types.py`,
  then retry.

### Two artifacts in stage 3

The deploy step takes the full envelope (`Template` + `Actions`).
The view template itself (`Template`) is what humans read and what
gets committed. Save both:

- `views/<view-name>/view.json` — pretty-printed `Template`. The
  reviewable artifact.
- `views/<view-name>/view-content.json` — the deploy envelope:
  `{"Template": "<stringified Template>", "Actions": [...]}`.
  Generated from `view.json` at deploy time; do not hand-author.

The `Template` field in `view-content.json` is a stringified JSON
blob — that's what `CreateView` expects, not a nested object. The
deploy script handles the stringification; stage 3 only cares about
`view.json` reading clean.

## Stage 4 — Deployment

Stage 4 is **optional and project-dependent**. Don't pick a path for
the user — describe the trade-offs and let them choose.

Three common paths:

1. **Repo deploy script (recommended).**
   `uv run --with boto3 python
   .kiro/skills/connect-view-author/scripts/deploy_connect_view.py
   --view-file views/<name>/view.json --view-name <Name> --actions
   <Actions> --instance-id <id> --region <region>`. Run it from the
   repo root so the `connect_knowledge` package (installed into the
   active venv) resolves for the local validator; `--with boto3`
   layers in the AWS SDK for the live calls. The script
   validates locally with `validate_view_json` before touching AWS,
   renders the `Content` envelope (stringified `Template` plus
   `Actions`), auto-detects create-vs-update by listing views in
   the instance, calls `CreateView` or `UpdateViewContent`, and
   then publishes an immutable numbered version with
   `CreateViewVersion`. Idempotent (deterministic `ClientToken`
   derived from inputs). Final `viewId`, `viewArn`,
   `publishedVersion`, and `viewContentSha256` print as JSON on
   stdout. Add `--dry-run` to render the envelope without calling
   AWS — useful for review or check-in (drop `--with boto3` for a
   dry run since no AWS SDK is needed). This is the right answer
   for most projects.
2. **Direct SDK call.** When the deploy script doesn't fit (custom
   tagging, multi-instance fanout, custom error handling), call
   `connect.create_view` for a new view or
   `connect.update_view_content` for an update, plus
   `connect.create_view_version`. The Content payload stringifies
   the template — boto3 doesn't do that for you. Useful when the
   deploy is part of a larger orchestration.
3. **CDK construct.** The `@aws-cdk/aws-connect`
   `CfnView` construct. Right answer when the view is one of many
   things in a stack and is part of an IaC discipline. The view
   `content` property takes the same envelope shape (stringified
   `Template`, plus `Actions`). Use `search_docs` to find current
   construct documentation.

Reach for AWS CLI (`aws connect create-view --content
file://view-content.json`) only when you need a one-off without
Python — the deploy script is strictly more capable and runs in the
same shell.

### Wiring the deployed view into a flow

The view is useless on its own — it has to be referenced from a
`Show view` block in some flow. After deploying:

1. Take the returned view ARN and version (e.g.
   `arn:aws:connect:us-east-1:111122223333:instance/<id>/view/<view-id>:1`).
2. Open the host flow's JSON. Find the `ShowView` Action (or add
   one — see `get_action_doc("participant-actions-showview")` for
   the parameter shape).
3. Set `Parameters.ViewToken` to the view ARN+version.
4. Set `Parameters.ViewContent` to the runtime input map (the
   values for the `$.X` template strings the view references).
5. Validate the host flow with `validate_flow_json`.
6. If the host flow is being authored as part of this work, this
   is the moment to hand off to `connect-flow-author` (or
   re-engage it). Otherwise, deploy the updated flow JSON via
   `UpdateContactFlowContent`.

### Versioning

Customer-managed view versions are immutable snapshots, like flow
modules. Every meaningful change should publish a new version
(`create_view_version`); never edit a published version in place.
The Show view block references a specific version, so promotion is
a flow-side change, not a view-side change.

If the user expects to iterate quickly during development, point
them at `$LATEST` (the alias that always resolves to the most
recent published version) and remind them to pin to an explicit
version once the view stabilizes.

### AWS-managed view "deploy"

For AWS-managed views, there is no resource to create — the view
template is built into Connect itself. The artifact is the input
shape (the `show-view-input.json` from stage 1) plus the host
flow's Show view block, which references the AWS-managed template
by name (`Detail`, `Form`, `List`, `Cards`, `Confirmation`). The
work in stage 4 collapses to "validate the host flow."

Whatever path the user picks, do not deploy without their explicit
go. Deployment changes a live system; treat it as a high-risk
action.

## Best practices and patterns

A checklist the agent should consult at every stage. Distilled from
the View Dictionary documentation, the admin guide, and the
patterns in `#connect-view-patterns`.

### Naming

- View names are kebab-case in the file system (`escalation-handoff`)
  and PascalCase in the AWS console (`EscalationHandoff`). Pick one
  human-readable form per project and stay consistent.
- `_id` values are kebab-case, unique within the view, descriptive
  (`callback-date`, not `dp-1`). The validator enforces uniqueness;
  human-readability is on you.
- Component `Name` props are the keys for the form output map.
  Use camelCase to match the rest of Connect (e.g.
  `nextStep`, `callbackDate`). Avoid spaces or special characters.

### Data binding

- Bind dynamic values via `$.Path` template strings. The runtime
  resolves them against the namespace passed in by the Show view
  block's `ViewContent`. The block's **Set JSON** option gives the
  cleanest mapping — a single object passed to the view, every
  field reachable by JSONPath.
- For static defaults that the agent can override, use
  `DefaultValue` on the form input — bind to a `$.Path` if the
  default itself is dynamic (e.g. pre-fill a date picker with
  today's date plus 3 days from a Lambda lookup).
- Do not mix template strings (`$.X`) with handlebars-style
  references (`{{X}}`). The two surfaces resolve differently —
  AWS-managed views use `{{X}}` for some fields, customer-managed
  views use `$.X` everywhere. Stay on `$.X` for customer-managed
  views to avoid confusion.

### Form composition

- Wrap form inputs in a `Form` component. Without the Form, a
  SubmitButton has nothing to collect from. The Form component's
  `Sections` prop carries the layout; the actual inputs are
  nested under `Sections[N].Components`.
- Pair every Form with a SubmitButton. The SubmitButton's `Action`
  value becomes the flow branch the agent takes when they finish
  filling the form.
- Required props are enforced on submit. Use `HelperText` to
  pre-empt errors ("Required when 'Schedule callback' is
  selected").
- For conditional fields ("show date picker only when
  'Schedule callback' is selected"), use UI conditions in the
  Customize panel — they generate `Visibility`, `Required`, or
  `Options` rules tied to another component's value. The
  validator does not check UI conditions; they're authored
  in-console and exported with the view.

### Layout

- Default to a single column. Reach for
  `Configuration.Layout.Columns` only when the design genuinely
  needs side-by-side regions (e.g. detail panel left, form panel
  right). Columns must sum to 12.
- Use `Container` to group related components for layout, not for
  visual styling — visual styling is the global theme's job.
- `Section` (UI Component) carries a heading and groups
  components — useful for long forms where the agent needs visual
  anchors. `ExpandableSection` is the same idea but collapsible —
  useful for transcripts and other "context, but not
  always-visible" content.

### Actions and branches

- Every interactive control (`Button`, `SubmitButton`, `Card`
  inside a `ButtonGroup` with an `Action` prop, `Table` with row
  actions) declares an `Action` value in its props. The top-level
  `Actions` list must enumerate every value referenced.
- Each `Actions` entry becomes one branch on the Show view block
  in the host flow. Plan for: one branch per Action, plus the
  default error branch. The host flow design has to wire all of
  them.
- Reusable view note: if you're building one view referenced by
  multiple flows, the `Actions` list is the contract — every host
  flow has to handle every Action. Don't add Actions casually.

### Sensitive data

- Anything captured in a view (form inputs, `Output`) lands in the
  contact record transcript by default. To redact PII, the host
  flow has to use `Set recording and analytics behavior` to
  disable recording for the segment that contains the Show view
  block, and Contact Lens redaction has to be enabled for the
  instance.
- Do not capture credit card numbers, SSNs, or auth codes in a
  view without that protection. The view JSON itself can't enforce
  this; it's a host-flow responsibility.

### Channel coverage

- Most components work in chat as well as voice (the host flow
  decides which channel runs the view). The View Dictionary
  doesn't enumerate per-component channel matrices — assume any
  component works in any channel unless the docs say otherwise.
  Verify with `get_view_component_doc` if a component is critical
  and channel coverage is uncertain.
- For chat-only flows that run a view as customer self-service,
  pass the view through a hosted Amazon Connect chat widget. See
  the `step-by-step-guides-chat` admin-guide row in
  `#connect-views`.

## Output contract per stage

Each stage produces a single deliverable that becomes the input to
the next stage:

| Stage | Deliverable |
|---|---|
| 1 | Markdown spec (block above), saved as `views/<view-name>/view-design.md` |
| 2 | Layout outline (YAML-style fenced block), appended to `view-design.md` |
| 3 | View JSON (`view.json`) + validator report; envelope (`view-content.json`) generated for deploy |
| 4 | Deployment guidance, optionally with a script or CDK snippet, plus the host-flow update |

Always show the deliverable in chat before moving to the next
stage, and wait for the user's confirmation. Don't compress two
stages into one — the staging is the entire point of the skill.

## Failure modes

- Steering files unavailable → stop, ask the user to pull them in
  with `#connect-views` and `#connect-view-patterns`.
- MCP tools unavailable → stop, ask the user to configure the
  `connect_knowledge` server (see repo README). For
  `get_view_component_doc` specifically, also confirm the Chromium
  browser binary is installed (Playwright itself ships as a core
  dependency).
- Validator errors that don't match anything in the spec → the
  spec is incomplete; loop back to stage 1 for the missing
  decision rather than papering over with default values.
- User wants to skip stages → push back gently. Stage 2 catches
  layout and data-binding errors that are 10× more expensive to
  fix in JSON; the validator catches structural errors that are
  100× more expensive to fix after `CreateView`. Skipping is a
  false economy.
- "How do I show the view to the agent?" — that's a host-flow
  question. Hand off to `connect-flow-author` for the wrapper
  flow, then come back here for view edits.

## Do not

- Do not invent component `Type` values, prop names, or Action
  semantics. Cite the catalog or fetch the page.
- Do not deploy without explicit user confirmation.
- Do not produce view JSON that has not been validated. The
  validator is fast; there is no excuse to skip it.
- Do not strip the validator's warnings without acknowledging
  them.
- Do not embed PII-collection forms in views without coordinating
  with the host flow's recording-and-analytics behavior.
- Do not edit a published view version in place; publish a new
  version instead.
- Do not confuse a customer-managed view template (the JSON this
  skill produces) with the input shape passed to an AWS-managed
  view through the Show view block — those are different
  artifacts. The validator only checks customer-managed templates.
