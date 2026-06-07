# NOTICE — AWS-owned content

The YAML files in this folder are **system AI prompts authored and
shipped by AWS** through the Amazon Connect AI agents service. They
were retrieved from a live Amazon Connect AI agents domain via the
`qconnect:GetAIPrompt` API with `--origin SYSTEM`.

## Source

- **Domain (assistant) ID:** `11111111-2222-3333-4444-555555555555`
  (named `my-connect-domain`)
- **AWS account:** `111122223333`
- **Region:** `us-west-2`
- **Last refreshed:** see `_manifest.json`'s file mtime, or run the
  refresh script (`hooks/refresh-system-prompts.kiro.hook`) to stamp
  it.

The same prompts are visible to any IAM principal with
`qconnect:ListAIPrompts` and `qconnect:GetAIPrompt` permissions on
any Amazon Connect AI agents domain.

## Licensing and redistribution

These prompts are AWS-owned content. They are **not** published
under an open-source license. Their use is governed by:

- The AWS Customer Agreement.
- The Amazon Connect service terms.
- Any non-disclosure provisions that apply to your AWS account.

In practice this means:

- ✅ **Use within this repo** as a structural reference for
  authoring custom prompts is appropriate. The `connect-ai-agent-author`
  skill leans on these as a read-only base.
- ✅ **Use within your organization's private codebases** is
  appropriate.
- ⚠️ **Do not redistribute** these YAML files outside AWS / your
  organization. Do not commit them to a public git repository.
  Do not paste them into public Q&A sites, blog posts, or
  third-party AI training pipelines.

The full text of these prompts is not published in AWS public
documentation. The [`Default AI prompts and AI agents`](https://docs.aws.amazon.com/connect/latest/adminguide/default-ai-system.html)
admin-guide topic lists them by name with one-line descriptions, but
does not publish the YAML bodies. The
[`Create AI prompts`](https://docs.aws.amazon.com/connect/latest/adminguide/create-ai-prompts.html)
topic shows one example (an `AnswerGeneration` MyRides demo prompt) —
that is the only system prompt body in the public docs.

## Refresh

When AWS ships an updated revision of a system prompt, the cache here
goes stale. Re-run the refresh hook:

```
.kiro/hooks/refresh-system-prompts.kiro.hook   →  userTriggered
```

Or call the refresh script directly:

```
uv run python .kiro/hooks/scripts/refresh_system_prompts.py
```

The script overwrites every YAML in this folder and rewrites
`_manifest.json`.

## Questions

If you're unsure whether a particular use of these files is
appropriate, ask AWS Legal / your account team before taking action.
