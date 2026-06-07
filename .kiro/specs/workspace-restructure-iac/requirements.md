# Requirements Document

Workspace Restructure

## Introduction

The `connect-skills` repository has grown organically. Project artifacts
(knowledge bases, AI agents, flows, views, Lex bots) sit in sibling
top-level folders with no project grouping, skills reference code that
lives outside their own folders (`scripts/`, `src/`), hooks call
scripts from a shared `scripts/` directory, and the MCP server depends
on a package under `src/`. The unused `SampleBot/` fixture — the
reference used to build the Lex deploy skill — sits at the repo root
unattached to anything.

This feature reorganizes the workspace so that:

1. Every concrete project lives under a single `projects/<project>/`
   tree with a consistent set of subfolders.
2. Every Kiro skill is self-contained: its prompts **and** its code
   live inside the skill's own folder.
3. Every Kiro hook is self-contained: the script it runs lives inside
   the hooks tree.
4. Every script the `connect_knowledge` MCP depends on lives inside the
   MCP's own folder.
5. The unused `SampleBot/` fixture is deleted — it is fully superseded
   by the `q_in_connect_passthrough` Lex template.

The guiding constraint across all of this: **no functional
regression**. Every skill, hook, MCP tool, CLI, and deploy script that
works today must work after the move, with every internal reference
updated to the new paths.

> **Out of scope (future work):** an Infrastructure-as-Code (IaC)
> capability — skills, steering, and a CDK documentation MCP for
> authoring AWS CDK (Python) that provisions Amazon Connect resources —
> is deferred to a later spec. This spec is purely a structural
> restructure.

## Glossary

- **Project**: a tenant/industry-scoped collection of deliverables
  (e.g. `telco-cx`). Holds knowledge bases, AI agents, flows, views,
  and Lex bots that belong together.
- **Skill**: a `.kiro/skills/<name>/` directory containing a `SKILL.md`
  and, after this change, any code the skill drives.
- **Hook**: a `.kiro/hooks/<name>.kiro.hook` definition plus the script
  it runs.
- **Steering**: a `.kiro/steering/*.md` reference catalog pulled into
  context on demand.

---

## Requirements

## Requirement 1 — Projects folder

**User story:** As a maintainer, I want every concrete project to live
under `projects/<project_name>/` with a consistent subfolder layout, so
that deliverables for a tenant or industry are grouped and discoverable.

#### Acceptance Criteria

1. THE SYSTEM SHALL provide a top-level `projects/` directory.
2. WHERE a project contains knowledge bases, THE SYSTEM SHALL place each
   under `projects/<project_name>/knowledge_bases/<knowledge_base_name>/`.
3. WHERE a project contains Connect AI agents, THE SYSTEM SHALL place
   each under `projects/<project_name>/connect_ai_agents/<agent_name>/`.
4. WHERE a project contains flows, THE SYSTEM SHALL place each under
   `projects/<project_name>/flows/<flow_name>/`.
5. WHERE a project contains views, THE SYSTEM SHALL place each under
   `projects/<project_name>/views/<view_name>/`.
6. WHERE a project contains Lex bots, THE SYSTEM SHALL place each under
   `projects/<project_name>/lex_bots/<bot_name>/`.
7. THE SYSTEM SHALL preserve the internal structure and file contents of
   each moved artifact directory exactly (only the parent path changes).

## Requirement 2 — Telco project consolidation

**User story:** As a maintainer, I want all telco artifacts consolidated
under `projects/telco-cx/`, so the telco deliverables live together.

#### Acceptance Criteria

1. THE SYSTEM SHALL move `knowledge_base/telco-kb-es/` to
   `projects/telco-cx/knowledge_bases/telco-kb-es/`.
2. THE SYSTEM SHALL move
   `connect_ai_agents/telco-selfservice-es-us/` to
   `projects/telco-cx/connect_ai_agents/telco-selfservice-es-us/`.
3. THE SYSTEM SHALL move every telco-scoped flow
   (`telco-agent-screenpop-es`, `telco-selfservice-es-inbound`,
   `init-flow-es`) to `projects/telco-cx/flows/<flow_name>/`.
4. THE SYSTEM SHALL move `views/telco-escalation-handoff/` to
   `projects/telco-cx/views/telco-escalation-handoff/`.
5. WHEN an artifact is moved, THE SYSTEM SHALL update any intra-artifact
   reference (e.g. `deploy.sh`, `manifest.json`, `_tag_contents.sh`,
   `.last-deploy.json`) that contains an absolute or repo-relative path
   to its own previous location.

## Requirement 3 — Non-telco artifact placement

**User story:** As a maintainer, I want non-telco sample artifacts
placed sensibly rather than left at the root, so the root stays clean.

#### Acceptance Criteria

1. THE SYSTEM SHALL move the banking flow `abc-bank-spanish-welcome` to
   its own project under `projects/abc-bank/flows/abc-bank-spanish-welcome/`.
2. WHERE a flow is a generic, project-agnostic sample
   (`escalate-to-agent`), THE SYSTEM SHALL place it under a
   `projects/_samples/flows/<flow_name>/` location reserved for reusable
   examples.
3. WHEN a sample flow's `design.md` references its own previous path,
   THE SYSTEM SHALL update that reference to the new location.

## Requirement 4 — Self-contained skills

**User story:** As a maintainer, I want each skill to carry its own
code, so a skill folder is a complete, portable unit.

#### Acceptance Criteria

1. THE SYSTEM SHALL relocate `scripts/deploy_lex_skill.py` and the
   `lex_skills/` template library into the
   `.kiro/skills/q-in-connect-bot-deploy/` folder.
2. THE SYSTEM SHALL relocate `scripts/deploy_connect_view.py` into the
   `.kiro/skills/connect-view-author/` folder.
3. THE SYSTEM SHALL relocate `scripts/refresh_connect_view_component_types.py`
   (invoked by the view-author skill) into the
   `.kiro/skills/connect-view-author/` folder.
4. WHEN a skill's code is relocated, THE SYSTEM SHALL update every path
   reference inside that skill's `SKILL.md` to the new location.
5. WHEN a relocated script imports the shared `connect_knowledge`
   package, THE SYSTEM SHALL ensure the import still resolves after the
   move (via the installed package or an explicit dependency
   declaration).
6. THE SYSTEM SHALL ensure each relocated deploy script still runs and
   produces the same output it did before the move (verified with a
   `--dry-run` where the script supports it).

## Requirement 5 — Self-contained hooks

**User story:** As a maintainer, I want each hook's script to live in
the hooks tree, so hook definitions and their scripts are co-located and
the shared `scripts/` clutter is removed.

#### Acceptance Criteria

1. THE SYSTEM SHALL relocate every refresh script invoked by a hook
   (`refresh_connect_blocks.py`, `refresh_connect_flow_language.py`,
   `refresh_connect_views.py`, `refresh_connect_ai_agents.py`,
   `refresh_aws_workshops.py`, `refresh_system_prompts.py`) plus the
   shared helper `_doc_fetcher.py` into the `.kiro/hooks/` tree.
2. WHEN a refresh script is relocated, THE SYSTEM SHALL update the
   corresponding `.kiro.hook` definition's `command` to the new script
   path.
3. WHEN a steering file or skill references a refresh script's old path,
   THE SYSTEM SHALL update that reference to the new path.
4. WHEN a relocated refresh script imports the shared `connect_knowledge`
   package, THE SYSTEM SHALL ensure the import still resolves after the
   move.
5. THE SYSTEM SHALL ensure each relocated refresh script still runs
   (verified with `--dry-run` where supported).

## Requirement 6 — Self-contained MCP

**User story:** As a maintainer, I want the `connect_knowledge` MCP to
own all the code it depends on, so the MCP folder is a complete unit and
the `src/` clutter is removed.

#### Acceptance Criteria

1. THE SYSTEM SHALL relocate the `src/connect_knowledge/` package into
   the `connect_knowledge_mcp/` folder.
2. THE SYSTEM SHALL update `connect_knowledge_mcp/pyproject.toml` and the
   root `pyproject.toml` so the package builds and resolves from its new
   location.
3. THE SYSTEM SHALL keep the MCP server entrypoint
   (`connect_knowledge_mcp.py`) and its eight tools functional after the
   move.
4. THE SYSTEM SHALL keep the console-script CLIs
   (`connect-docs-search`, `connect-blog-search`,
   `connect-repost-search`) functional after the move.
5. WHEN `.kiro/settings/mcp.json` references the MCP entrypoint, THE
   SYSTEM SHALL keep that reference valid (path unchanged or updated).
6. THE SYSTEM SHALL verify the MCP server starts and at least one tool
   responds after the move.

## Requirement 7 — SampleBot removal

**User story:** As a maintainer, I want the unused `SampleBot/` fixture
deleted, so the root is clean and a stale committed account ID/assistant
ARN is removed.

#### Acceptance Criteria

1. THE SYSTEM SHALL confirm `SampleBot/` has no references anywhere in
   the repository before deleting it. *(Confirmed: zero references.)*
2. THE SYSTEM SHALL confirm the `q_in_connect_passthrough` template is a
   structural superset of `SampleBot/` (identical layout; the template
   uses the `{{Q_ASSISTANT_ARN}}` placeholder where SampleBot hardcodes
   a real ARN). *(Confirmed.)*
3. THE SYSTEM SHALL delete the top-level `SampleBot/` directory.

## Requirement 8 — Reference integrity

**User story:** As a maintainer, I want zero broken references after the
restructure, so nothing silently stops working.

#### Acceptance Criteria

1. WHEN any file is moved, THE SYSTEM SHALL update every other file in
   the repo that references the moved file's old path (skills, hooks,
   steering, READMEs, `pyproject.toml`, `mcp.json`, deploy scripts,
   manifests).
2. THE SYSTEM SHALL leave no dangling reference to a pre-move path
   (verified by a repository-wide search for old path fragments
   returning no functional references).
3. THE SYSTEM SHALL update the `.gitignore` if any moved directory
   relied on an ignore rule keyed to its old path.

## Requirement 9 — Documentation

**User story:** As a new contributor, I want the README to reflect the
new layout, so the documented structure matches reality.

#### Acceptance Criteria

1. THE SYSTEM SHALL update the root `README.md` "Repository layout"
   section to show the `projects/` tree, self-contained skills, hooks,
   and MCP folders.
2. THE SYSTEM SHALL update every command example in `README.md` that
   referenced an old script path to the new path.

## Non-functional / cross-cutting

1. **No regression**: every skill, hook, MCP tool, CLI, and deploy
   script functional before the change is functional after it.
2. **Atomic moves**: file moves use a move/rename that preserves git
   history where possible (the move tool, not delete+recreate).
3. **Verification per move**: each relocation is followed by a
   `--dry-run` or import check before the task is marked complete.
4. **Reversibility**: the restructure is staged so a single project's
   move can be validated before the next begins.
