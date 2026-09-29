# Using this workspace

A tour of what to ask for, ordered by how much machinery each request
pulls in. Every group ends with prompts you can paste, each with the
result that tells you it worked.

Setup lives in [README.md](README.md). Repo conventions for agents
working on the code live in [AGENTS.md](AGENTS.md).

## Kiro or Claude Code

The prompts below work in both clients. Three pieces of syntax differ.

| Action | Kiro | Claude Code |
|---|---|---|
| Invoke a skill | `/connect-flow-author` | `/connect-flow-author`, via the `.claude/skills` symlink |
| Pull in a catalog | `#connect-blocks` | Keep `#connect-blocks` in the prompt; [CLAUDE.md](CLAUDE.md) resolves it to one section of `.kiro/steering/connect-blocks.md`. Type `@.kiro/steering/connect-blocks.md` only to load the whole file |
| Check or reconnect MCP servers | MCP Server view in the feature panel | `claude mcp list` in a shell, `/mcp` in a session |

The mapping, and why catalogs load one section at a time in Claude Code,
is in the README under
[Skills and steering in Claude Code](README.md#skills-and-steering-in-claude-code).

## The four layers

| Layer | What it is | How it activates |
|---|---|---|
| MCP tools | 10 functions over live AWS sources | The agent calls them when your question needs a fact |
| Steering | 13 reference catalogs | You type `#name`, or a skill pulls one in |
| Skills | 10 multi-stage workflows | Description match, or you type `/name` |
| Custom agents | None defined yet | See [Custom agents](#custom-agents) |

Reach for the smallest layer that answers the question. A block lookup
does not need a skill.

---

## Group 1: Direct MCP lookups

The cheapest layer. No skill, no steering. Ask a factual question and the
agent calls one tool.

### connect_knowledge, 8 tools

| Tool | Answers |
|---|---|
| `search_docs` | "What does the docs say about X" |
| `search_blogs` | "Is there a published pattern for X" |
| `search_repost` | "Has anyone hit this error" |
| `get_block_doc` | Full detail on one flow block |
| `get_action_doc` | Exact `Parameters` shape for one Flow language Action |
| `get_view_component_doc` | Props table for one view component |
| `validate_flow_json` | Structural check on flow JSON |
| `validate_view_json` | Structural check on view JSON |

`get_block_doc` and `get_action_doc` return AWS's markdown plus a
`sections` list. Ask for one section when you want a short answer.

### cdk_docs, 2 tools

| Tool | Answers |
|---|---|
| `search_cdk_docs` | "Which construct do I need" |
| `get_cdk_construct_doc` | Full property list for one construct |

Scoped to `aws_cdk.aws_connect`, `aws_cdk.aws_lex`, `aws_cdk.aws_wisdom`,
and `aws_cdk.aws_bedrockagentcore`.

### Prompts to test

```
Which channels does the Get customer input block support? Just the
channel matrix, not the whole page.
```
Expect a Voice, Chat, Task, Email table. Chat reads "Yes, when Amazon Lex
is used". Proves `get_block_doc` with a `section` filter, and proves the
tool handles the newer page layout.

```
What are the exact Parameters for the InvokeLambdaFunction action?
```
Expect `LambdaFunctionARN`, `InvocationTimeLimitSeconds` capped at 8,
`InvocationType`, `LambdaInvocationAttributes`, `ResponseValidation`.

```
Why do Connect Lambda invocations fail at 8 seconds? Check re:Post.
```
Expect several community threads on the 8-second synchronous cap.

```
What are the required properties on CfnAIAgent?
```
Expect `assistant_id`, `configuration`, `type` as required, with
`description`, `name`, `tags` optional. Proves library auto-resolution,
since you never named `aws_cdk.aws_wisdom`.

```
Validate this flow JSON:
{"Version":"2019-10-30","StartAction":"a","Actions":[
 {"Identifier":"a","Type":"MessageParticipant","Parameters":{"Text":"hi"},
  "Transitions":{"NextAction":"nope"}},
 {"Identifier":"b","Type":"DisconnectParticipant","Parameters":{},
  "Transitions":{}}]}
```
Expect 1 error for the dangling `NextAction` to `nope`, and 1 warning
that `b` is unreachable. A clean pass means the tool is not working.

```
Show me the props for the Datepicker view component.
```
Expect `Label` and `Name` required, three optional. This one drives
headless Chromium, so it also proves the Playwright install.

---

## Group 2: Steering catalogs

Reference material you pull into context on purpose. All 13 are
`inclusion: manual` except `concise`, which always loads. That keeps the
large tables out of context until you ask.

In Kiro, type `#` in chat and pick, or write the name inline. In Claude
Code, write `#name` inline the same way; the picker is Kiro-only.

### Generated catalogs

Scripts rewrite these from live AWS sources.

| Reference | Contents | Entries |
|---|---|---|
| `#connect-blocks` | Every flow block with its channel matrix | 58 |
| `#connect-flow-language` | Grammar, Action catalog, deploy gaps | 56 |
| `#connect-views` | View Dictionary and admin-guide view pages | 66 |
| `#cdk-connect` | `aws_cdk.aws_connect` constructs | 37 |
| `#cdk-agentcore` | `aws_cdk.aws_bedrockagentcore` constructs | 26 |
| `#cdk-q-in-connect` | `aws_cdk.aws_wisdom` constructs | 12 |
| `#cdk-lex` | `aws_cdk.aws_lex` constructs | 4 |
| `#aws-workshops` | Connect workshops with deep-linked modules | 14 |
| `#connect-ai-agents` | AI agent design and troubleshooting prose | 20 sources |

### Hand-authored

No script overwrites these.

| Reference | Contents |
|---|---|
| `#cdk-iac` | CDK Python conventions for Connect |
| `#connect-view-patterns` | Worked Body examples for common view shapes |
| `#troubleshoot-ai-agents` | Playbook for an agent that greets then stalls |
| `#concise` | Output style. Always loaded |

### Catalog or MCP tool?

The catalog is a one-line-per-entry index, cheap and good for breadth.
The MCP tool is the full page, expensive and good for depth. Start with
the catalog to find the name, then call the tool for detail.

### Prompts to test

```
#connect-blocks Which blocks work on the Email channel?
```
Expect a filtered list read off the table, with no page fetches.

```
#connect-flow-language I need to loop a prompt every 30 seconds in a
customer queue flow. Which Action types do I need?
```
Expect `Loop`, `MessageParticipant`, and a `Wait`, named from the
catalog.

```
#cdk-q-in-connect #cdk-agentcore I want a Q in Connect assistant whose
AI agent calls an AgentCore gateway. Which constructs, in what order?
```
Two catalogs at once. Expect a construct chain, not prose.

```
#troubleshoot-ai-agents My self-service agent greets the caller then
goes silent. Where do I start?
```
Expect the playbook's ordered causes.

```
#aws-workshops Which workshop covers outbound campaigns, and what are
its modules?
```
Expect the Multi-channel Outbound Campaigns workshop with 12 deep links.

---

## Group 3: Skills

Multi-stage workflows. A skill takes over the conversation, asks
clarifying questions, and produces artifacts in order rather than
answering in one shot.

Two ways to start one. Describe the task and let the description match,
or invoke it directly with `/name`.

| Skill | Use when |
|---|---|
| `/connect-flow-author` | Designing or reviewing a contact flow |
| `/connect-view-author` | Designing an agent-facing or chat screen |
| `/connect-ai-agent-author` | Building a self-service or agent-assist AI agent |
| `/connect-kb-author` | Populating a Q in Connect knowledge base |
| `/connect-prompt-reviewer` | Hardening an existing prompt YAML |
| `/connect-researcher` | Open-ended question needing several sources |
| `/connect-iac-cdk-author` | Writing CDK Python for the Connect chain |
| `/mcp-gateway-author` | Exposing a REST API as MCP tools via AgentCore |
| `/q-in-connect-bot-deploy` | Deploying the three-locale Lex passthrough bot |
| `/steering-refresher` | Refreshing the generated catalogs |

### What to expect

The authoring skills run four or five stages and pause between them. The
flow author sketches Mermaid with real block names before writing JSON,
then validates. Approve or redirect at each stage rather than waiting for
a finished artifact.

Two skills touch AWS. `q-in-connect-bot-deploy` and the deploy step of
`connect-view-author` create real resources, so ask for a dry run first.

### Prompts to test

```
/connect-flow-author I need an inbound flow for a bank. Spanish and
English, business hours check, then queue with a callback offer over 5
contacts waiting.
```
Expect requirements questions, then a Mermaid sketch with real block
names, then JSON, then a `validate_flow_json` result. Refuse the JSON if
it arrives before the sketch; the stages exist for a reason.

```
/connect-researcher What is the real difference between an
answer-recommendation AI agent and a self-service one, and when do I
need both?
```
Expect docs, blog, and re:Post sources triangulated, with citations.

```
/connect-view-author An agent screen showing caller name, account
balance, last 3 payments, and a Take payment button.
```
Expect a layout outline naming real components, then view JSON, then
`validate_view_json`.

```
/steering-refresher which catalogs are stale?
```
Expect each catalog checked against its own freshness window. 30 days for
workshops, 7 for the rest. Read-only.

```
/connect-prompt-reviewer review
.kiro/skills/connect-ai-agent-author/system-prompts/SelfServiceOrchestrationVoice.yaml
```
Expect findings ranked by severity. Needs the cached prompts pulled
first; see the README section on that.

```
/mcp-gateway-author I have a telco REST API on API Gateway with account
lookup and plan change. Expose it to a Connect AI agent.
```
Expect an OpenAPI schema, the `CfnGateway` and `CfnGatewayTarget` pair,
and the API-key credential provider wiring.

---

## Custom agents

`.kiro/agents/` is empty. No custom agents ship with this workspace.

A custom agent differs from a skill. A skill is a workflow the main
session follows. An agent is a separate session with its own system
prompt and tool allowlist, which you delegate to. Delegation keeps a long
investigation out of your main context.

Candidates worth defining here, given what the repo already does:

- A read-only Connect researcher, restricted to the six search and doc
  tools, with no write access.
- A steering auditor that checks freshness and reports, never refreshing.
- A flow reviewer that reads flow JSON and critiques against
  `#connect-flow-language` without editing.

Ask Kiro to create one and it will scaffold the definition into
`.kiro/agents/`. Claude Code keeps subagents in `.claude/agents/`, a
separate format; the `.claude/skills` symlink does not cover agents.

---

## Composing the layers

The layers stack. A realistic session uses three at once.

```
/connect-flow-author #connect-blocks #connect-flow-language
Design a callback-offer queue flow. Use the catalogs for block and Action
names, and call get_action_doc before writing any Parameters.
```

The skill drives the stages, the catalogs supply names cheaply, and the
MCP tools confirm the exact parameter shapes. That ordering is the point:
breadth from steering, depth from tools, sequencing from the skill.

## When something looks wrong

- A tool returns nothing or errors on a slug. Confirm the slug against
  the catalog link. Slugs are URL stems, not display names.
- Answers ignore a catalog you named. Steering is `manual`, so it loads
  only when the `#name` resolves. In Kiro, retype it from the `#`
  picker. In Claude Code, confirm the session loaded CLAUDE.md, which
  carries the `#name` rule.
- An MCP tool is missing from the session. In Kiro, reconnect both
  servers from the MCP Server view, then reload the window if it
  persists. In Claude Code, run `claude mcp list`; both should read
  Connected.
- Skills are missing in Claude Code. The `.claude/skills` symlink did
  not survive checkout, which happens on Windows without symlink
  support. Recreate it with `ln -s ../.kiro/skills .claude/skills`.
- A generated catalog looks stale or wrong. Run `/steering-refresher`.
  Never hand-edit those files; the next refresh overwrites them.
