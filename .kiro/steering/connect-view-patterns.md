---
inclusion: manual
last_refreshed: 2026-05-26
---

# Connect view patterns

Worked Body examples for the most common customer-managed view shapes.
Use this as a paste-and-edit starting point during stage 3 of
`connect-view-author`. Every example below validates clean against
``validate_view_json``; copy the exact shape and substitute names,
labels, and prop values.

**Activation:** opt-in. Reference from chat with
`#connect-view-patterns` when sketching or writing view JSON.

For the full prop catalog of any component, call
`get_view_component_doc(slug=...)`. For the component list and which
hierarchies a component lives in, see `#connect-views`.


## Component prop gotchas (confirmed via get_view_component_doc)

- **`Button` has NO `Label` prop.** Its only props are `Variant`,
  `IconName`, `IconAlign`, `Disabled`, `Action`, `Loading`. The
  visible button text comes from the **`Content`** array
  (`"Content": ["Entendido"]`), not a `Label`. Passing `Label` is
  silently ignored and the button renders as an empty colored pill.
  (`SubmitButton` differs — check its doc before assuming.)
- **Multi-container layout wrapping.** `Head.Configuration.Layout.Columns`
  is a positional list that maps to the **top-level Body containers in
  order**. With `["4", "8"]` and three containers, the third wraps
  back onto a new row into the leftmost 4-wide slot — it does NOT
  auto-span. To give a footer container its own full-width row, add a
  matching width entry: `["4", "8", "12"]` (one width per top-level
  container). Column widths still must each be ≤ 12; they describe the
  width of each container's cell, not a single summed row.

## Server-side schema gaps (validate_view_json does NOT catch these)

`validate_view_json` checks structure but is looser than the
`CreateView` / `UpdateViewContent` server schema. Real 400s seen in
practice that the local validator passes:

- **Top-level `Body` items must be `Container`.** You cannot put a
  bare `Button`, `TextBox`, `Alert`, etc. directly in `Body` — the
  server returns `must be equal to constant "Container"` and
  `must NOT have additional properties` for that item's props. Wrap
  any standalone component (e.g. a footer action button) in a
  `Container` with `Configuration.Layout.Columns: "12"`. Nesting
  inside an existing Container is fine; it's only the **top level of
  Body** that is Container-only.
- When in doubt, deploy with `--status SAVED` first (lighter
  validation) or just attempt `PUBLISHED` and read the
  `InvalidParameterException` — the `instancePath` (e.g. `/Body/2/Type`)
  points at the offending node.


## Common conventions

- **Top-level shape:** every example shows the full ``{"Template":
  {"Head", "Body"}, "Actions": [...]}`` envelope. Drop the outer
  envelope when nesting one of these patterns into another.
- **`_id` values:** human-readable, kebab-case, unique within the
  view. The validator enforces uniqueness across the whole tree.
- **`Type` values:** taken straight from `#connect-views`. Always
  one of the catalog names — same value regardless of whether you
  use the UI Component or FormView Component variant of that
  component.
- **Action references:** every component button surfaces its
  `Props.Action` value as a flow branch on the Show view block. The
  top-level `Actions` list must enumerate every value referenced.
  Components without buttons (display-only) don't need entries.
- **Dynamic data:** bind any prop to runtime data with `$.<path>`
  (passed through Show view's Set JSON), e.g.
  `"Heading": "$.Customer.Name"`. The View renderer resolves
  these at view-mount time.


## 1. Detail screen pop (display-only)

The simplest useful view: shows a customer's details when the contact
is offered. No buttons, no form. Pair with a `Set event flow` block
configured to fire `DefaultFlowForAgentUI` so the view pops as soon
as the contact reaches the agent.

```json
{
  "Template": {
    "Head": {
      "Title": "Customer details"
    },
    "Body": [
      {
        "_id": "attribute-bar",
        "Type": "AttributeBar",
        "Props": {
          "Attributes": [
            {"Label": "Customer", "Value": "$.Customer.Name"},
            {"Label": "Phone", "Value": "$.Customer.Phone", "Copyable": true},
            {"Label": "Account ID", "Value": "$.Customer.AccountId", "Copyable": true}
          ]
        }
      },
      {
        "_id": "details",
        "Type": "AttributeSection",
        "Props": {
          "Items": [
            {"Label": "Tier", "Value": "$.Customer.Tier"},
            {"Label": "Last contact", "Value": "$.Customer.LastContactDate"},
            {"Label": "Open cases", "Value": "$.Customer.OpenCaseCount"}
          ]
        }
      }
    ]
  }
}
```

Notes: no `Actions` list because there are no `Props.Action`
references. The view auto-dismisses when the agent moves on; the
`Show view` flow block exits via the default branch.


## 2. Disposition / ACW form

Single-page form for end-of-contact wrap-up. The agent picks a
disposition from a dropdown, optionally adds notes, and submits.
The Show view block surfaces the captured values to the flow under
the `Submit` branch.

```json
{
  "Template": {
    "Head": {
      "Title": "Wrap-up"
    },
    "Body": [
      {
        "_id": "wrap-up-form",
        "Type": "Form",
        "Props": {
          "Sections": [
            {
              "Heading": "Disposition",
              "Components": [
                {
                  "_id": "disposition",
                  "Type": "Dropdown",
                  "Props": {
                    "Label": "Outcome",
                    "Name": "disposition",
                    "Required": true,
                    "Options": [
                      {"Label": "Resolved", "Value": "resolved"},
                      {"Label": "Escalated", "Value": "escalated"},
                      {"Label": "Callback scheduled", "Value": "callback"},
                      {"Label": "Abandoned", "Value": "abandoned"}
                    ]
                  }
                },
                {
                  "_id": "notes",
                  "Type": "TextArea",
                  "Props": {
                    "Label": "Notes",
                    "Name": "notes",
                    "HelperText": "Visible to the next agent who handles this customer."
                  }
                }
              ]
            }
          ]
        }
      },
      {
        "_id": "submit",
        "Type": "SubmitButton",
        "Props": {"Label": "Save", "Action": "Submit"}
      }
    ]
  },
  "Actions": ["Submit"]
}
```

Notes: in the customer-managed view + Form combination, captured
values land directly under the view's output (e.g.
`$.Views.ViewResultData.disposition`). For the AWS-managed Form view
the same data lands under `FormData` —
`$.Views.ViewResultData.FormData.disposition`. Pick one approach and
stay consistent across views in the same project.


## 3. Multi-action card list (escalation triage)

A list of next-step cards. Each card carries an `Action` that becomes
a flow branch on the Show view block, so the flow can route based on
which card the agent picks.

```json
{
  "Template": {
    "Head": {
      "Title": "What does the customer need?"
    },
    "Body": [
      {
        "_id": "options",
        "Type": "ButtonGroup",
        "Props": {
          "Items": [
            {
              "_id": "billing-card",
              "Type": "Card",
              "Props": {
                "Id": "billing-card",
                "Heading": "Billing question",
                "Description": "Subscription, invoices, refunds.",
                "Action": "TransferBilling"
              }
            },
            {
              "_id": "tech-card",
              "Type": "Card",
              "Props": {
                "Id": "tech-card",
                "Heading": "Technical issue",
                "Description": "App or service not working.",
                "Action": "TransferTech"
              }
            },
            {
              "_id": "escalate-card",
              "Type": "Card",
              "Props": {
                "Id": "escalate-card",
                "Heading": "Escalate to supervisor",
                "Description": "Customer wants to speak to a manager.",
                "Action": "EscalateSupervisor"
              }
            }
          ]
        }
      }
    ]
  },
  "Actions": ["TransferBilling", "TransferTech", "EscalateSupervisor"]
}
```

Notes: the Show view flow block will gain three branches — one per
Action — plus a default error branch. Wire each branch to the
appropriate flow logic (`Transfer to queue` / `Transfer to flow`).


## 4. Detail with embedded form (escalation handoff)

Combines display-only header with a form, used when the agent
inherits an escalated contact and needs to capture the resolution
plan before moving on.

```json
{
  "Template": {
    "Head": {
      "Title": "Escalated contact",
      "Configuration": {"Layout": {"Columns": ["8", "4"]}}
    },
    "Body": [
      {
        "_id": "header",
        "Type": "AttributeBar",
        "Props": {
          "Attributes": [
            {"Label": "Customer", "Value": "$.Customer.Name"},
            {"Label": "Original queue", "Value": "$.Contact.SourceQueue"},
            {"Label": "Reason", "Value": "$.Contact.EscalationReason"}
          ]
        }
      },
      {
        "_id": "history",
        "Type": "ExpandableSection",
        "Props": {"Heading": "Bot transcript"},
        "Content": [
          {
            "_id": "transcript",
            "Type": "TextBox",
            "Props": {"Value": "$.Contact.BotTranscript"}
          }
        ]
      },
      {
        "_id": "resolution-form",
        "Type": "Form",
        "Props": {
          "Sections": [
            {
              "Heading": "Resolution plan",
              "Components": [
                {
                  "_id": "next-step",
                  "Type": "RadioGroup",
                  "Props": {
                    "Label": "Next step",
                    "Name": "nextStep",
                    "Required": true,
                    "Options": [
                      {"Label": "Resolve now", "Value": "resolve"},
                      {"Label": "Schedule callback", "Value": "callback"},
                      {"Label": "Open case", "Value": "case"}
                    ]
                  }
                },
                {
                  "_id": "callback-time",
                  "Type": "DatePicker",
                  "Props": {
                    "Label": "Callback date",
                    "Name": "callbackDate",
                    "HelperText": "Required only when 'Schedule callback' is selected."
                  }
                }
              ]
            }
          ]
        }
      },
      {
        "_id": "submit",
        "Type": "SubmitButton",
        "Props": {"Label": "Continue", "Action": "Submit"}
      }
    ]
  },
  "Actions": ["Submit"]
}
```

Notes: the `Configuration.Layout.Columns` setting in `Head` lets the
top-level Body items lay out in two columns. Components that occupy
the first column take width 8; the second column takes width 4. Total
must equal 12 (the standard flexbox grid).


## 5. AWS-managed Detail view (templated screen pop)

When a customer-managed view is overkill, point the Show view block
at the AWS-managed `Detail` view and pass it a template body. This
sample is the input shape for the `Show view` block's **Set JSON**
option — not a customer-managed view template. The block uses it
to populate the AWS-managed Detail view at runtime.

```json
{
  "Heading": "Customer details",
  "AttributeBar": [
    {"Label": "Customer", "Value": "$.Customer.Name"},
    {"Label": "Phone", "Value": "$.Customer.Phone", "Copyable": true}
  ],
  "Sections": [
    {
      "Heading": "Account",
      "Content": [
        {"Label": "Tier", "Value": "$.Customer.Tier"},
        {"Label": "Open cases", "Value": "$.Customer.OpenCaseCount"}
      ]
    },
    {
      "Heading": "Recent contact",
      "Content": [
        {"Label": "Last contact", "Value": "$.Customer.LastContactDate"},
        {"Label": "Reason", "Value": "$.Customer.LastContactReason"}
      ]
    }
  ]
}
```

Notes: `validate_view_json` does not check this shape — it's the
input to the AWS-managed view, not a view template itself. For its
schema see [Detail view](https://docs.aws.amazon.com/connect/latest/adminguide/view-resources-managed-view.html).
Use `connect-view-author` to pick between AWS-managed templates and
customer-managed views during stage 1.


## When to pick which pattern

| Situation | Use |
|---|---|
| Show data, no agent input | Pattern 1 (Detail screen pop) or Pattern 5 (AWS-managed Detail) |
| Capture structured wrap-up data | Pattern 2 (Disposition / ACW form) |
| Branch the flow on agent's choice | Pattern 3 (Multi-action cards) |
| Show data + capture decision in one screen | Pattern 4 (Detail + form) |
| Quick prototype, can live without custom UI | AWS-managed Detail / Form / List |

Default to **AWS-managed** when the layout fits one of the templated
shapes and you don't need full control over the layout grid. Default
to **customer-managed** (patterns 1–4) when you need a layout AWS
templates don't support, dynamic component visibility (UI conditions),
or reuse across views.


## Customer-facing chat views (hosted communications widget)

A `Show view` block can render a customer-managed view inside the
**hosted Amazon Connect chat widget** (not just the agent workspace) —
see the admin-guide `step-by-step-guides-chat` page. But the widget's
renderer supports a **much smaller component set** than the agent
workspace, and this is **not documented** anywhere in AWS docs. Learned
empirically (telco-cx new-line plan picker):

### What renders in the chat widget

- ✅ `TextBox` (read-only text) and plain `Button` (with an `Action`),
  composed inside a single top-level `Container`.
- ❌ `Dropdown`, `FormInput`, `TextArea`, `SubmitButton`, the `Form`
  FormView component, and `ButtonGroup` — these either render an empty
  box or fail with **"Something went wrong. Ensure your inputs are
  valid"** / **"…Try again later."** The same view renders fine in the
  agent workspace; the customer widget just can't draw form inputs.

**Pattern for a chat self-service choice form:** don't use a `Form` +
`Dropdown`. Use one `Button` per option inside a `Container`, each with
its own `Action` (e.g. `plan-basic`, `plan-plus`), then branch the
`ShowView` block on `$.Views.Action`. Collect any free-text fields
(area code, notes) conversationally through the AI agent instead of a
text input. Replicate the proven shape: a single `Container`
(`Columns: ["12"]`) holding a `TextBox` heading + the option buttons.

### Other chat ShowView gotchas

- **Pin a numbered view version, not `:$LATEST`.** The customer widget
  reliably renders an explicit published version
  (`…/view/<id>:3`); `$LATEST` (the mutable draft pointer) is flaky for
  the customer participant. Publish with `create_view_version` and
  reference that number from the flow.
- **ViewData keys must match the view's InputSchema exactly.** The
  runtime rejects ViewData keys that aren't in the schema (error:
  "Ensure your inputs are valid"). After removing a component's
  `DefaultValue`/binding from the view, also remove the matching key
  from the flow's `ShowView` `ViewData`, or the extra key fails
  validation. Connect title-cases the first letter of ViewData keys, so
  a flow key `planOptions` is read in the template as `$.PlanOptions`.
- **A `Dropdown`'s `DefaultValue` is typed `string[]`.** Passing an
  empty string (`""`) for it fails schema validation — pass `[]`/omit,
  or wrap a real value as a one-element array.
- **`ShowView` egress shows `Timeout`, not the client error.** When the
  widget fails to render, the customer never responds, so the flow log
  shows the `ShowView` block timing out — the actual "something went
  wrong" is client-side. Don't chase it as a flow/data bug; isolate by
  pointing the block at a dummy `TextBox`+`Button` view to confirm the
  renderer works, then add components back one at a time.
- **The local `validate_view_json` is not the server schema.** It
  passed a `ButtonGroup` shape the live `UpdateViewContent` rejected.
  The server (`CreateView`/`UpdateViewContent`) is authoritative —
  deploy to a `SAVED`/`PUBLISHED` draft to catch server-schema gaps.

## Returning control to the AI agent after a ShowView (chat)

When a chat `ShowView` hands back to a Q in Connect AI agent, do **not**
route into the main self-service entry block — that starts a fresh
agent turn and the agent **re-greets** ("¡Hola …! ¿En qué puedo
ayudarle?") instead of continuing. Instead route to a
`ConnectParticipantWithLexBot` block with a
`LexInitializationData.InitialMessage` (e.g. `[NUEVA_LINEA] El cliente
seleccionó un plan…`). The init message is fed to the agent as input,
so it acts on it (continues the task) rather than greeting.

To pass the view's result to the agent, write it into the **Q in
Connect session** (so it surfaces as `$.Custom.<key>` in the
orchestration prompt), not just a contact attribute. A small generic
Lambda that calls `qconnect:update_session_data` with whatever
key/values the flow passes is reusable for any future field — resolve
the session ARN via `connect:describe_contact` →
`Contact.WisdomInfo.SessionArn`. Reference the key in the prompt's
`<customer_info>` block as `{{$.Custom.<key>}}`.

## Passing contactAttributes from a hosted widget (frontend)

`amazon_connect('contactAttributes', obj)` captures the **object
reference** and reads it when the chat session starts. To update an
attribute (e.g. the logged-in email) before the customer opens the
chat, **mutate the same object** —
`window._connectContactAttrs.email = email` — rather than re-calling
`amazon_connect('contactAttributes', …)` or rebuilding the widget. The
widget reads the live value at open time. The snippet prepends
`HostedWidget-` to each key, so the flow reads it as
`$.Attributes.HostedWidget-email`.
