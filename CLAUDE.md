@AGENTS.md

# Reading a Kiro workspace as Claude Code

This repo targets Kiro. Two of its conventions need a translation step,
and one symlink covers the first.

## Skills

The ten workflows live in `.kiro/skills/<name>/SKILL.md`. Claude Code
discovers them through the `.claude/skills` symlink, which points at that
directory, so `/connect-flow-author` and its nine siblings work with no
copy and no drift. Editing a skill in either path edits the same file.

## Steering catalogs

The thirteen reference catalogs live in `.kiro/steering/<name>.md`. Every
skill cites one as `#name`, which is Kiro syntax that resolves to
nothing here.

**When a skill or a prompt says `#name`, open `.kiro/steering/name.md`
and retrieve the part you need, not the whole file.**

These are reference tables and sectioned notes, so reading one end to end
is almost never the right call. Two commands cover every lookup:

```bash
grep -n '^## ' .kiro/steering/connect-ai-agents.md        # the section map
grep -n 'TagContact' .kiro/steering/connect-flow-language.md   # one row
```

Get the map, then read that one section by offset. `Language alignment
(CRITICAL)` is about sixty lines of `connect-ai-agents.md` rather than all
843. Catalogs with no `##` headings, `connect-blocks.md` among them, are a
single table: grep the row and stop.

Read a catalog whole only when it is small. Six are not: `connect-ai-agents.md`
at 44K, then `connect-flow-language.md`, `aws-workshops.md`,
`connect-views.md` and `troubleshoot-ai-agents.md` between 21K and 24K, and
`connect-view-patterns.md` at 18K. The other seven run 2K to 14K and are
cheap to read in full.

Skipping a cited catalog because it looks expensive is the failure this
rule exists to prevent. Pulling `Language alignment (CRITICAL)` out of
`connect-ai-agents.md` costs 440 bytes for the map plus 3.5K for the
section, against 44K for the file. There is no reason to work without the
reference a skill asked for.

Do not add `@` imports for these. The thirteen total 213K, so importing
them eagerly would spend the context window on tables nobody asked for.
`#concise` is the exception: it is `inclusion: always` in Kiro, so it is
imported below and governs every answer in this repo.

@.kiro/steering/concise.md
