# q-in-connect-passthrough

Reusable Lex V2 bot template that delegates every utterance to an
Amazon Q in Connect assistant.

## What it is

A Lex V2 import bundle (mirrors the format the Lex console exports)
plus a `skill.json` manifest. Three locales (`en_US`, `es_US`, `pt_BR`),
each containing two intents:

- `AmazonQinConnect` — built on `AMAZON.QInConnectIntent`, wired to a
  per-tenant `assistantArn`. Its success response is the magic token
  `((x-amz-lex:q-in-connect-response))`, which Lex replaces with the
  Q in Connect assistant's answer at runtime.
- `FallbackIntent` — required by Lex; otherwise a no-op.

All three locales use Nova Sonic v2 (`amazon.nova-2-sonic-v1:0`) for
unified speech, so deploy in a region that supports it.

## What's parameterized

`skill.json` declares two placeholders:

| Placeholder | CLI flag | Notes |
| --- | --- | --- |
| `{{BOT_NAME}}` | `--bot-name` | Per-tenant. Renames the inner bot folder during materialization. |
| `{{Q_ASSISTANT_ARN}}` | `--q-assistant-arn` | Wisdom/Q in Connect assistant ARN. Substituted into all three `AmazonQinConnect` intents. |

The bot folder in `template/` is named `HotelBookingBot/` only because
the directory name has to match the bot name on import. The deploy
script renames it on the fly.

## How deployment works

`.kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py`
walks the standard Lex V2 import path
plus the Connect association:

1. Materialize a copy of `template/` into a temp dir, substitute placeholders, rename the inner folder.
2. Zip the bundle.
3. `lexv2-models.create_upload_url` → `PUT` zip to the presigned URL → `lexv2-models.start_import` (Overwrite).
4. Poll `describe_import` until `Completed`. Resolve `botId` via `list_bots`.
5. `build_bot_locale` for each locale; poll `describe_bot_locale` until `Built`.
6. `create_bot_version` (numbered snapshot of DRAFT).
7. `create_bot_alias` (or `update_bot_alias` if `prod` already exists) pointing at the new version.
8. *(Optional)* `connect.associate_bot` with the `LexV2Bot.AliasArn`.

## Usage

Dry-run (renders the bundle, no AWS calls):

```sh
uv run --with boto3 python .kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py \
    --skill q_in_connect_passthrough \
    --bot-name AcmeHotelBookingBot \
    --q-assistant-arn arn:aws:wisdom:us-east-1:111122223333:assistant/<id> \
    --artifact-dir /tmp/acme \
    --dry-run
```

Full deploy:

```sh
uv run --with boto3 python .kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py \
    --skill q_in_connect_passthrough \
    --bot-name AcmeHotelBookingBot \
    --q-assistant-arn arn:aws:wisdom:us-east-1:111122223333:assistant/<id> \
    --bot-role-arn arn:aws:iam::111122223333:role/AWSServiceRoleForLexV2Bots_acme \
    --region us-east-1 \
    --connect-instance-id <connect-instance-id>
```

The script prints the final `botId`, `botVersion`, and `aliasArn` as
JSON on stdout — pipe into `jq` if you want to capture them.

## Updating the template

Either edit the JSON files directly or:

1. Import the current template into a Lex account.
2. Edit in the console.
3. Export from the console.
4. Drop the export back into `template/` (preserve `{{BOT_NAME}}` /
   `{{Q_ASSISTANT_ARN}}` placeholders or re-introduce them).
