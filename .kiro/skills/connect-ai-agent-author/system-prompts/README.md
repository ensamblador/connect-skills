# System AI prompts — read-only reference

These YAML files are the system AI prompts shipped by Amazon Connect,
pulled from an AI agents domain via
`aws qconnect get-ai-prompt --origin SYSTEM` against every prompt in
`list-ai-prompts --origin SYSTEM`. They are `SYSTEM`-origin content,
identical across domains, so the domain they came from does not matter.

These files are gitignored. Pull your own copy from your own Connect
instance; see the re-dump steps below.

> **Provenance and licensing:** these prompts are AWS-owned content,
> not published in AWS public documentation, and not under any
> open-source license. See `NOTICE.md` in this folder before
> sharing or redistributing any of these files. The full prompt
> bodies are NOT available in the AWS public docs — only the
> `AnswerGeneration` example on the
> [`Create AI prompts`](https://docs.aws.amazon.com/connect/latest/adminguide/create-ai-prompts.html)
> page is published, and the rest are mentioned by name only on the
> [`Default AI prompts and AI agents`](https://docs.aws.amazon.com/connect/latest/adminguide/default-ai-system.html)
> topic.

**This folder is reference material, not a build target.** Treat
every file as read-only.

## How the skill uses these

When `connect-ai-agent-author` reaches **Stage 3a (AI prompts)** for a
new agent, the orchestration prompt (or any other custom prompt) is
authored as a thin diff over the matching system prompt:

1. Find the system prompt that corresponds to the prompt slot
   you're customizing (e.g., `SelfServiceOrchestrationVoice` for a
   voice self-service Orchestration prompt).
2. Open the matching file in this folder. Read it end to end before
   writing the customer-specific YAML.
3. Preserve the system prompt's overall structure: the order of
   sections, the `messages:` shape (with `{{$.conversationHistory}}`
   first and the optional `role: assistant / content: <message>`
   prefill last), the use of XML-like section tags, and the few-shot
   example shape.
4. Replace the **content** of each section with use-case-specific
   content (telco self-service, healthcare intake, hotel concierge,
   etc.). Keep the **shape** identical.
5. Author the prompt body in **English**. The agent's `locale`
   field on the `orchestrationAIAgentConfiguration` (or matching
   field on other agent types) drives the output language at
   runtime — the model honors `{{$.locale}}` and the in-prompt
   locale instructions to respond in the customer's language. There
   is no benefit, and several risks, to authoring the prompt body in
   the target language: it makes diffs against the system prompt
   harder to read, breaks `{{$.locale}}`-based switching if you ever
   want to reuse the prompt across locales, and can confuse the
   model when `{{$.locale}}` doesn't match the prompt's authored
   language.

## What's here

The full list as of the last refresh — see `_manifest.json` for IDs,
model bindings, and API formats:

- `AgentAssistanceOrchestration.yaml` — system prompt for
  Orchestration agents wired into the Agent Workspace assistant
  panel.
- `AnswerGeneration.yaml` — KB-grounded answer generation
  (TEXT_COMPLETIONS).
- `CaseSummarization.yaml` — case summary prompt.
- `EmailGenerativeAnswer.yaml`, `EmailOverview.yaml`,
  `EmailQueryReformulation.yaml`, `EmailResponse.yaml` — email-aware
  prompts.
- `IntentLabelingGeneration.yaml` — Answer Recommendation pipeline.
- `NoteTaking.yaml` — generates HTML contact notes.
- `QueryReformulation.yaml` — KB query construction.
- `SalesAgent.yaml` — sales-opportunity Orchestration prompt.
- `SelfServiceAnswerGeneration.yaml` — legacy SELF_SERVICE
  Answer Generation prompt.
- `SelfServiceOrchestrationChat.yaml` — Orchestration prompt for
  chat self-service.
- `SelfServiceOrchestrationVoice.yaml` — Orchestration prompt for
  voice self-service. **The most common starting point for new
  customer-facing voice agents.**
- `SelfServicePreProcessing.yaml` — legacy SELF_SERVICE pre-routing
  prompt.

## Refresh

The cache goes stale when AWS publishes a new revision of a system
prompt. To re-dump:

- **Quick path:** ask for a system-prompts refresh — the
  `steering-refresher` skill dispatches it.
- **CLI path:**
  ```
  uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py
  ```
- **Different domain / region / profile:**
  ```
  DOMAIN_ID=<other-uuid> \
  AWS_REGION=us-east-1 \
  AWS_PROFILE=other-profile \
  uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py
  ```

The script overwrites every `*.yaml` in this folder and rewrites
`_manifest.json`. `NOTICE.md` and this README are not touched.

The system prompts here are AWS-owned content. Don't redistribute
outside this repo without checking the licensing on AWS-shipped
prompt templates. They are visible to any IAM principal with
`qconnect:GetAIPrompt` on the assistant. See `NOTICE.md` for
detail.

## Compatibility

System prompts evolve over time. The model bindings in
`_manifest.json` reflect the per-region defaults at the time of
the dump. If you build a prompt off one of these and AWS later
ships a new revision with materially different sections, your custom
prompt won't auto-update — that's by design. Re-dump when you want to
rebase.
