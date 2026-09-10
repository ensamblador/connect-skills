# Lean / latency-first prompt guidance (advisory)

Compiled from the internal **Amazon Connect AI Prompt Wizard**
best-practices page (`https://d3tv5yrjbkjuxu.cloudfront.net/`, marked
**alpha — under active development**). This is the third source behind
the `connect-prompt-reviewer` skill's check catalog.

**Standing in the source hierarchy: advisory.** This guidance is
subordinate to (1) the canonical AWS documentation and (2) the cached
default system prompts. It never justifies breaking a rule from either.
Its core principle — *every token costs time; design prompts as if you
pay per millisecond* — is a real discipline, but it was written for a
Lambda-driven Bedrock call, not for a Connect-managed AI prompt, and
several of its rules are wrong or inapplicable in the Connect context.
Read the conflict table at the bottom before applying any of it.

Content was paraphrased and condensed for compliance with licensing
restrictions.


## What this guidance says

### Prompt structure and length
- Aim for a system prompt under ~500 tokens; shorter means faster
  time-to-first-token.
- Remove redundant instructions; don't restate what the model already
  knows.
- No pleasantries or meta-commentary; cut fluff.
- Prefer declarative statements over explanatory ones.
- Front-load the most critical instructions — attention is strongest at
  the start.
- Drop few-shot examples unless strictly necessary; each one costs
  tokens.
- Weak → strong: *"try to be concise because customers don't want long
  responses"* → *"Respond in 1–2 sentences maximum."*

### Structural efficiency
- Plain text over structured formats; the page argues JSON/XML in a
  system prompt adds cognitive overhead.
- Avoid deeply nested instructions; flat lists process faster.
- Imperative voice cuts word count. *"The assistant should always
  verify the customer's intent before proceeding"* → *"Verify intent
  before proceeding."*

### Conversation-history management (called the biggest latency lever)
- Don't pass full history beyond 4–6 turns for real-time voice.
- Use a sliding window of the last N turns.
- Summarize older context into one compressed block.
- Strip filler / acknowledgment turns before passing history.
- Paraphrase long customer utterances into shorter forms.
- Don't repeat in history what already lives in the system prompt.
- Merge consecutive assistant turns.
- Example compressed block: `[Context: Customer called about order
  #12345 delay. Confirmed identity. Checked warehouse status.]`

### Instruction precision (leave no room for deliberation)
- Vague instructions force the model to reason through ambiguity;
  specificity reduces generation overhead.
- *"Keep responses appropriate for voice"* → *"Max 2 sentences. No
  lists. No markdown. Spell out numbers."*
- *"Transfer if the customer seems frustrated"* → *"Transfer to agent
  if customer uses any of: cancel, refund, lawyer, complaint,
  supervisor."*
- Pre-define fallbacks verbatim: out-of-scope → *"I can only help with
  [X]. Shall I connect you to an agent?"*; unknown info → *"I don't
  have that information. Let me connect you with someone who can
  help."*

### Prompt architecture patterns
- Separate a fast path (simple intents, minimal context) from complex
  reasoning (full context only when warranted).
- Use a lightweight Lambda intent pre-classification before invoking
  Bedrock.
- Slot-fill: extract the needed slots, ask one question at a time for
  missing ones, confirm and proceed when full.
- Template pre-population: fetch and format customer data in Lambda
  into 1–3 lines before invoking Bedrock, e.g. `[Customer: John Smith
  | Account: Active | Open Cases: 1]`.

### Token-level optimizations
- Constrain output length explicitly ("under 20 words", "one sentence
  only").
- Instruct the model to omit preambles and answer directly.
- Prohibit self-referential language ("As an AI …").
- Define response templates for predictable intents.
- Avoid reasoning tokens where possible: disable chain-of-thought for
  simple tasks; reserve it for complex, high-stakes decisions;
  structured extraction beats narrated reasoning.

### Context-window budget (the page's table)
| Size | Impact |
|---|---|
| under 500 tokens | fastest; target for simple flows |
| 500–1,500 | acceptable for moderate complexity |
| 1,500–3,000 | noticeable latency; justify every token |
| over 3,000 | avoid in real-time voice; consider async |

- Audit prompts with a token counter; every new instruction should
  cost an old one; treat the context window as scarce memory.

### Lean structure the page recommends
```
[ROLE]        1-2 sentences maximum
[TASK]        What to do, stated directly
[CONSTRAINTS] Hard rules: length, format, topics
[CONTEXT]     Dynamic customer data, compressed
[FALLBACKS]   Exact strings for edge cases
[HISTORY]     Last 3-4 turns only, stripped of filler
```
Cut completely: company backstory; ethical guidelines unless
compliance mandates them; explanations of why rules exist; redundant
reinforcement ("remember to always…"); examples of good responses
unless accuracy is actively failing; formatting instructions
irrelevant to voice output.

### The page's own checklist
System prompt < 500 tokens · no filler/explanatory language · history
capped at 4–6 turns · filler stripped from history · customer context
compressed to 1–3 lines · explicit output-length constraint · direct
answer instruction · fallback strings pre-defined · prompt cached in
Lambda memory (not fetched per call) · response streaming enabled
end-to-end · token count audited and baselined.


## What maps to a check (the parts that survive)

These translate into the skill's `P*` family and reinforce a few
docs-backed checks. They are all compatible with the Connect prompt
model:

| Lean idea | Check |
|---|---|
| No filler, backstory, meta-commentary, "remember to always…" | `P1`, `B3` |
| Enumerable triggers over impressionistic ones ("cancel/refund/lawyer…" not "seems frustrated") | `P2` |
| Imperative, declarative voice | `P3` |
| Front-load critical instructions | `P4` (also best-practices §structure) |
| Explicit output-length constraint for voice | `P5`, `V5` |
| Preamble / filler suppression | `P6` (also voice prompt §style) |
| Pre-defined verbatim fallback strings | `P7` |
| Calibrate specificity to the model | `P8` (also best-practices §latency) |
| Keep nesting shallow, every tag earns its place | `P9` |
| Remove genuinely redundant instructions/examples | `B1`, `B3`, `E2` |


## What does NOT map to a prompt finding

Never file these against an AI prompt YAML. They are either wrong for
Connect or not editable from the prompt. When relevant, surface them in
the report's **Architecture recommendations** section, clearly labeled
as outside the prompt file.

- **History windowing / sliding window / turn merging / utterance
  compression.** `{{$.conversationHistory}}` and `{{$.transcript}}` are
  injected and sized by the service (`transcript` = up to the 3 most
  recent turns). Not adjustable from the YAML.
- **Prompt cached in Lambda memory; fetch-per-call avoidance.** Connect
  manages the prompt as a versioned resource; caching is the service's
  prompt-prefix cache, not a Lambda concern.
- **End-to-end response streaming.** Transport/infra, not prompt.
- **Lambda intent pre-classification; fast-path routing.** A flow/
  Lambda architecture decision.
- **Template pre-population in Lambda.** Belongs to the session-data /
  flow layer; the prompt only consumes `{{$.Custom.<NAME>}}`.


## The four conflicts and the ruling (must-read)

The skill's precedence order is: **canonical docs > cached system
prompts > this guidance.** Where they collide:

| Topic | This guidance | Docs / system prompts | Ruling for a Connect AI prompt |
|---|---|---|---|
| **Length** | < 500 tokens; > 3,000 unacceptable for voice | Static prefix of **~1,000+ tokens enables caching**; embed static domain policy inline | Caching floor wins. A cached 2k prefix is cheaper *and* faster than an uncached 500-token one. Apply the lean advice **within** that budget: cut filler, not cacheable policy. Flag real bloat above ~8k (`B1`), not everything over 500. `C1` is **never** a blocker. |
| **Few-shot examples** | Eliminate unless accuracy is failing | Lead with instructions, reinforce with a worked example; every shipped system prompt carries several | Keep examples for orchestration (`E1`/`E2`) — they sit in the cached prefix, near-zero marginal latency. Apply the lean point only to examples that demonstrate the same rule twice. |
| **Structure** | Plain text over XML; avoid nesting | `<message>`/`<thinking>` are a hard runtime contract; system prompts use nested XML-ish sections | Tags stay — non-negotiable; stripping them makes the customer hear silence. Apply the lean advice only to gratuitous nesting (4+ levels) and to XML with no parsing/sectioning purpose (`P9`). |
| **History** | Cap at 4–6 turns, sliding window, strip filler | Injected and sized by the service | Not actionable inside the prompt. Never a prompt finding — Architecture recommendations only. |

Two minor ones:

- **Reasoning tokens.** The guidance says disable chain-of-thought for
  simple tasks; the docs use `<thinking>` to plan multi-tool sequences
  and to review available tools before claiming capabilities. Ruling:
  keep `<thinking>` **scoped**, not eliminated.
- **Ethical / security rules.** The guidance says cut ethical
  guidelines unless compliance mandates them; the system prompts devote
  whole blocks to PII, malice, persona-lock and prompt-leak refusal.
  Ruling: safety rules (`X*`) are load-bearing, not filler.
