---
name: q-in-connect-bot-deploy
description: Deploy an Amazon Lex V2 bot from this repo's `lex_skills/` template library — three-locale (en_US, es_US, pt_BR) Q in Connect passthrough bot using Nova Sonic v2 unified speech, with optional Amazon Connect instance association. Use this skill when the user asks to create, deploy, or update a Lex bot that delegates to a Q in Connect (Wisdom) assistant; not for designing contact flows (use `connect-flow-author`) or for raw Lex bot authoring from scratch.
---

# Q in Connect Lex bot deploy

You are a deployment assistant for the parameterized Lex V2 templates
under this skill's `lex_skills/` folder. Today the only template is
`q_in_connect_passthrough` — a three-locale bot (`en_US`, `es_US`,
`pt_BR`) using Nova Sonic v2 unified speech, with two intents per
locale: `AmazonQinConnect` (built on `AMAZON.QInConnectIntent`,
delegates every utterance to a Q in Connect assistant) and
`FallbackIntent`.

The actual deploy is run by
`.kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py`, which
walks the standard Lex V2 import path (`CreateUploadUrl` →
presigned `PUT` → `StartImport` → poll → `BuildBotLocale` per
locale → `CreateBotVersion` → `CreateBotAlias`) and optionally
calls `connect.associate_bot` to wire the alias into a Connect
instance.

## When to use

Activate this skill when the user is asking:

- "Deploy a Q in Connect Lex bot for ACME."
- "Stand up the passthrough Lex bot pointing at this Wisdom assistant."
- "Update the Lex bot alias to a new Q assistant ARN."
- Any variation that starts from a Q in Connect (Wisdom) assistant
  and ends in a Lex V2 bot association.

Do **not** use this skill for:

- Designing or generating Connect contact flow JSON — that's
  `connect-flow-author`.
- Authoring a Lex bot from scratch (custom intents, slots, fulfillment
  Lambdas) — this skill only handles parameterized templates from
  `lex_skills/`.
- Generic AWS deployment questions — answer those directly without
  the skill.

## Prerequisites

Before stage 1, confirm:

1. The repo is checked out and
   `.kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py` is
   present.
2. The user has AWS credentials configured for the target account
   and region. If not, stop and ask them to set up `aws configure`
   or assume a role.
3. The target region supports Nova Sonic v2 (`amazon.nova-2-sonic-v1:0`).
   At time of writing that's a smaller subset of regions than the
   full Connect footprint — confirm with `search_docs` if unsure.
4. Q in Connect (Wisdom) is enabled on the target Connect instance,
   and the assistant exists. The skill needs the assistant ARN, not
   the friendly name.

## Stage 1 — Gather parameters

Get every required value before running anything. Push back on
vague answers.

| Parameter | CLI flag | Required | Notes |
|---|---|---|---|
| Skill template | `--skill` | yes | Default `q_in_connect_passthrough` (the only template available today). |
| Bot name | `--bot-name` | yes | Per-tenant. Must be unique in the AWS account. Convention: `<Tenant>HotelBookingBot` or `<Tenant>QPassthroughBot`. |
| Q assistant ARN | `--q-assistant-arn` | yes | Must match `arn:aws:wisdom:<region>:<account>:assistant/<uuid>`. Confirm by reading from the user's Connect → Wisdom configuration. |
| Bot IAM role ARN | `--bot-role-arn` | yes for real deploy | The Lex V2 service-linked role for this bot. Format: `arn:aws:iam::<account>:role/AWSServiceRoleForLexV2Bots_<suffix>` or a custom role. |
| Region | `--region` | defaults to `AWS_REGION` env or `us-east-1` | Must support Nova Sonic v2. |
| Connect instance ID | `--connect-instance-id` | optional | If set, the script associates the resulting alias with the Connect instance. Skip if the user wants to associate manually. |
| Artifact dir | `--artifact-dir` | optional | Where the rendered bundle and zip get written. Defaults to a temp dir; pass an explicit path if the user wants to inspect the rendered bundle. |

If the user gives you a Q assistant **friendly name** instead of an
ARN, ask for the ARN. Don't try to resolve it — that adds an
unnecessary AWS call to the conversation and surfaces permissions
errors at the wrong stage.

If the user is on a fresh project and doesn't have a bot IAM role
yet, point them at the
[Lex V2 service-linked role docs](https://docs.aws.amazon.com/lexv2/latest/dg/using-service-linked-roles.html)
or offer to write a one-time `aws iam create-service-linked-role`
command. Don't try to create the role inside the skill — that's
infra-side scope creep.

Restate the gathered parameters back to the user and wait for
confirmation before stage 2.

## Stage 2 — Dry-run

Render and zip the bundle without calling AWS. This catches
parameter substitution errors and lets the user inspect the
rendered template before any AWS-side work.

```bash
uv run --with boto3 python .kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py \
    --skill q_in_connect_passthrough \
    --bot-name <BOT_NAME> \
    --q-assistant-arn <Q_ASSISTANT_ARN> \
    --artifact-dir /tmp/<BOT_NAME>-render \
    --dry-run
```

After the run:

- The bundle lives at `/tmp/<BOT_NAME>-render/`.
- A zip file lives next to it.
- The script's stdout is JSON describing the rendered bundle.

Tell the user what to look at — specifically, the `Bot.json` and
the three `BotLocale.json` files for sanity. If the user wants to
diff against the previous deploy, point them at the output dir.

Do not proceed to stage 3 until the user explicitly approves.

## Stage 3 — Deploy

This stage hits live AWS. Treat as a high-risk action — confirm
before running, especially if `--connect-instance-id` is set
(that step changes the Connect instance's bot routing).

```bash
uv run --with boto3 python .kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py \
    --skill q_in_connect_passthrough \
    --bot-name <BOT_NAME> \
    --q-assistant-arn <Q_ASSISTANT_ARN> \
    --bot-role-arn <BOT_ROLE_ARN> \
    --region <REGION> \
    --connect-instance-id <CONNECT_INSTANCE_ID>   # optional
```

Walk the user through what will happen, in order:

1. Render the bundle (same as dry-run).
2. Upload the zip via `CreateUploadUrl` + presigned `PUT`.
3. `StartImport` with `Overwrite` — if a bot with the same name
   exists, it is replaced. Flag this if the bot name might
   collide with an existing one.
4. Poll `DescribeImport` until `Completed`. Up to 10 minutes.
5. `BuildBotLocale` for `en_US`, `es_US`, `pt_BR`. Each can take
   several minutes; the script polls until `Built`.
6. `CreateBotVersion` — a numeric snapshot of DRAFT.
7. `CreateBotAlias` (or `UpdateBotAlias` if `prod` already exists)
   pointing at the new version.
8. *(Optional)* `connect.associate_bot` with the
   `LexV2Bot.AliasArn`.

The script prints final `botId`, `botVersion`, and `aliasArn` as
JSON on stdout. Capture and surface these — the user will likely
want them for follow-up automation.

If the script fails partway through:

- **Import failed** → check the error message; almost always a
  malformed template (substitution issue) or a region mismatch.
  Re-run dry-run to verify.
- **Build failed for a locale** → the `DescribeBotLocale` output
  in the error message has a `failureReasons` field. Surface it
  verbatim and let the user decide whether to retry.
- **Connect association failed** → the bot is already deployed and
  versioned; the user can run `connect.associate_bot` manually
  with the printed `aliasArn`. Tell them so.

## Stage 4 — Verify

Once the script returns, verify the deploy:

1. `aws lexv2-models describe-bot-alias --bot-id <botId> --bot-alias-id <aliasId>`
   — confirms the alias is `Available`.
2. (If associated) `aws connect list-bots --instance-id <id> --lex-version V2 --max-results 50`
   — confirms the bot appears in the Connect instance's bot list.
3. `aws lexv2-models list-tags-for-resource --resource-arn arn:aws:lex:<region>:<acct>:bot/<botId>`
   — confirms `AmazonConnectEnabled` is set to **`True`** (capital T).
   The script stamps this automatically. The value is case-sensitive:
   the Connect admin bot-management page (`/bots/details/<botId>`)
   returns 403 ("The Conversational AI bot does not have the required
   tag set") for `true` or any other casing, even though the flow
   dropdown and runtime accept it. If a user reports that 403, this
   tag value is the first thing to check.
4. End-to-end: place a test contact through a flow that uses the
   bot, or use the Lex V2 console's Test panel to send an utterance
   and verify the Q in Connect response comes back.

If verification fails, the bot is still deployed. Don't delete
anything without the user's go.

## Updating the template itself

If the user wants to *change* what the template produces (different
intents, slots, locales, speech model), this skill is the wrong
place — that's editing source under
`.kiro/skills/q-in-connect-bot-deploy/lex_skills/q_in_connect_passthrough/template/`.
The README in that folder explains the round-trip: import → console
edit → export → drop back into `template/`, preserving the
`{{BOT_NAME}}` and `{{Q_ASSISTANT_ARN}}` placeholders.

## Failure modes

- `.kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py`
  not found → stop, ask the user to pull the latest repo.
- AWS credentials missing or wrong region → don't try to silently
  fall back; surface the error and ask.
- Q in Connect assistant ARN doesn't exist → script fails at
  import time. Better to validate the ARN format up front (matches
  the regex in `skill.json`); the skill's `aws wisdom describe-assistant`
  check is optional.
- Bot name collision with an existing bot → `StartImport` runs in
  `Overwrite` mode and replaces it. Flag to the user before stage 3.
- Region without Nova Sonic v2 → import succeeds, build fails with
  a model-not-available error. Validate the region during stage 1
  if the user picks something unusual.

## Do not

- Do not deploy without an explicit user go after stage 2's
  dry-run.
- Do not invent IAM role ARNs, assistant ARNs, or instance IDs.
  Every ARN must come from the user or from a script call you can
  cite.
- Do not skip the dry-run. The dry-run is fast and cheap; the real
  deploy takes 5–15 minutes and changes a live system.
- Do not modify the template under
  `.kiro/skills/q-in-connect-bot-deploy/lex_skills/<name>/template/`
  inside this skill. That's a separate workflow (see "Updating the
  template itself").
- Do not chase Connect instance association if the user only asked
  for a bot deploy. `--connect-instance-id` is opt-in for a reason.
