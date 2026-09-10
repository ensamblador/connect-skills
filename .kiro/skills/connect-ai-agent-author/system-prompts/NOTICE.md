# NOTICE — AWS-owned content

The YAML files in this folder are **system AI prompts authored and
shipped by AWS** through the Amazon Connect AI agents service. They
were retrieved from a live Amazon Connect AI agents domain via the
`qconnect:GetAIPrompt` API with `--origin SYSTEM`.

## Source

These are AWS `SYSTEM`-origin prompts, identical in every Amazon
Connect AI agents domain. Whoever ran the refresh pulled them from
their own domain, so the source domain is an implementation detail and
is deliberately not recorded here.

`_manifest.json` records what the local copy contains, including each
prompt's `aiPromptId`, `modelId`, and `type`. Its file mtime is the
effective "last refreshed" stamp. That manifest is gitignored alongside
the YAML files, so it describes your copy only.

Any IAM principal with `qconnect:ListAIPrompts` and
`qconnect:GetAIPrompt` on any AI agents domain sees the same content.

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
goes stale. Ask for a system-prompts refresh and the
`steering-refresher` skill will dispatch it, or call the script
directly:

```
uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py
```

Credentials alone are not enough. The script needs four things:

1. AWS credentials for an account that has an Amazon Connect AI agents
   domain, which is a Q in Connect assistant.
2. The region that domain lives in, from `--region`, `AWS_REGION`, or
   `AWS_DEFAULT_REGION`. Point it at a region without a domain and it
   finds nothing to pull.
3. IAM permissions for `qconnect:ListAssistants`,
   `qconnect:ListAIPrompts`, and `qconnect:GetAIPrompt`.
4. `boto3`, supplied by the `--with boto3` flag above.

Any domain works, since the prompts are AWS-shipped and identical
across domains. By default the script resolves the first domain from
`ListAssistants`; pass `--domain-id <uuid>` to choose a specific one.
Add `--dry-run` to list the prompts and print the manifest without
writing.

The script overwrites every YAML in this folder and rewrites
`_manifest.json`. `NOTICE.md` and `README.md` are left alone.

## Questions

If you're unsure whether a particular use of these files is
appropriate, ask AWS Legal / your account team before taking action.
