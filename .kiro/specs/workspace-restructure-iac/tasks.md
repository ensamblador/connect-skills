# Implementation Plan — Workspace Restructure

## Overview

This plan reorganizes the `connect-skills` repo into a self-contained,
project-grouped layout. Tasks are ordered to keep the repo functional at
every step: the MCP package move (task 1) is foundational because
everything that imports `connect_knowledge` depends on it; hook and skill
self-containment (tasks 2–4) build on it; SampleBot and project moves
(tasks 5–7) are independent artifact relocations; documentation and the
reference sweep (task 8) come last.

> The IaC capability (CDK docs MCP, IaC steering, IaC authoring skill) is
> deferred to a future spec and is not part of this plan.

## Tasks

- [x] 1. Make the `connect_knowledge` MCP self-contained
  - Move `src/connect_knowledge/` into `connect_knowledge_mcp/connect_knowledge/` using a history-preserving move.
  - Update `connect_knowledge_mcp/pyproject.toml` so it builds the package from its new local path.
  - Update the root `pyproject.toml`: re-point the package source (workspace member / path dependency) and keep the three console scripts (`connect-docs-search`, `connect-blog-search`, `connect-repost-search`) resolvable.
  - Confirm `.kiro/settings/mcp.json` entrypoint path is still valid (no edit expected since `--directory connect_knowledge_mcp` and `connect_knowledge_mcp.py` are unchanged).
  - Remove the now-empty `src/` tree.
  - _Verify:_ `uv run --directory connect_knowledge_mcp python connect_knowledge_mcp.py` imports clean; `validate_flow_json` responds; one CLI (`connect-docs-search`) runs.
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 8.1_

- [x] 2. Make hooks self-contained
- [x] 2.1 Relocate refresh scripts into the hooks tree
  - Move `scripts/refresh_connect_blocks.py`, `scripts/refresh_connect_flow_language.py`, `scripts/refresh_connect_views.py`, `scripts/refresh_connect_ai_agents.py`, `scripts/refresh_aws_workshops.py`, `scripts/refresh_system_prompts.py`, and the shared `scripts/_doc_fetcher.py` into `.kiro/hooks/scripts/`.
  - Fix any imports of `connect_knowledge` so they resolve against the package's new home (task 1).
  - _Requirements: 5.1, 5.4_
- [x] 2.2 Update hook definitions and references
  - Update each `.kiro/hooks/refresh-*.kiro.hook` `command` to `uv run python .kiro/hooks/scripts/refresh_*.py`.
  - Update steering files (`connect-blocks.md`, `connect-flow-language.md`, `connect-views.md`, `aws-workshops.md`, `connect-ai-agents.md`) and `connect-ai-agent-author/SKILL.md` that name the old `scripts/refresh_*.py` paths.
  - _Verify:_ run each relocated refresh script with `--dry-run` (or `--skip-descriptions`) from the new path.
  - _Requirements: 5.2, 5.3, 5.5, 8.1_

- [x] 3. Make the view-author skill self-contained
  - Move `scripts/deploy_connect_view.py` and `scripts/refresh_connect_view_component_types.py` into `.kiro/skills/connect-view-author/scripts/`.
  - Update `refresh_connect_view_component_types.py` so its generated-module write target points at `connect_knowledge_mcp/connect_knowledge/_view_component_types.py`.
  - Rewrite the command blocks in `connect-view-author/SKILL.md` to the new script paths and a package-resolving invocation.
  - _Verify:_ `deploy_connect_view.py --dry-run` runs from the new path and emits `view-content.json` for a sample view.
  - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 8.1_

- [x] 4. Make the Lex bot-deploy skill self-contained
  - Move `scripts/deploy_lex_skill.py` into `.kiro/skills/q-in-connect-bot-deploy/scripts/`.
  - Move `lex_skills/q_in_connect_passthrough/` into `.kiro/skills/q-in-connect-bot-deploy/lex_skills/q_in_connect_passthrough/`.
  - Update `deploy_lex_skill.py` template resolution so it finds the relocated `lex_skills/` relative to itself.
  - Rewrite the command blocks in `q-in-connect-bot-deploy/SKILL.md` (and any README) to the new paths.
  - _Verify:_ `deploy_lex_skill.py --skill q_in_connect_passthrough ... --dry-run` renders the bundle from the new path.
  - _Requirements: 4.1, 4.4, 4.5, 4.6, 8.1_

- [x] 5. Delete the unused SampleBot fixture
  - Confirm `SampleBot/` has zero references and that `q_in_connect_passthrough` is a structural superset (identical layout; placeholder vs hardcoded ARN).
  - Delete the top-level `SampleBot/` directory.
  - _Verify:_ repo-wide grep for `SampleBot` returns no matches; the `SampleBot/` directory no longer exists.
  - _Requirements: 7.1, 7.2, 7.3, 8.2_

- [x] 6. Create the telco-cx project and move its artifacts
- [x] 6.1 Move telco knowledge base, AI agent, and view
  - Move `knowledge_base/telco-kb-es/` → `projects/telco-cx/knowledge_bases/telco-kb-es/`.
  - Move `connect_ai_agents/telco-selfservice-es-us/` → `projects/telco-cx/connect_ai_agents/telco-selfservice-es-us/`.
  - Move `views/telco-escalation-handoff/` → `projects/telco-cx/views/telco-escalation-handoff/`.
  - _Requirements: 1.1, 1.2, 1.3, 1.5, 2.1, 2.2, 2.4, 1.7_
- [x] 6.2 Move telco flows
  - Read each flow `design.md` to confirm telco scope; move `telco-agent-screenpop-es`, `telco-selfservice-es-inbound`, and `init-flow-es` into `projects/telco-cx/flows/` (route `init-flow-es` to `_samples` instead only if discovery shows it is generic).
  - _Requirements: 1.4, 2.3, 1.7_
- [x] 6.3 Fix telco intra-artifact path references
  - Scan `deploy.sh`, `.last-deploy.json`, `agent/*.json`, `manifest.json`, `_tag_contents.sh`, `_bucket-policy.json`, `_kms-key-policy.json`, `spec.md`, and each `design.md` for self-referential old paths and rewrite them.
  - _Verify:_ grep for `knowledge_base/telco-kb-es`, `connect_ai_agents/telco-selfservice-es-us`, and old `flows/telco-*` fragments returns no functional references.
  - _Requirements: 2.5, 8.1, 8.2_

- [x] 7. Place non-telco flows into projects
  - Move `flows/abc-bank-spanish-welcome/` → `projects/abc-bank/flows/abc-bank-spanish-welcome/`.
  - Move `flows/escalate-to-agent/` → `projects/_samples/flows/escalate-to-agent/`.
  - Update each moved `design.md` self-reference; remove the now-empty top-level `flows/`, `views/`, `knowledge_base/`, `connect_ai_agents/` dirs.
  - _Verify:_ grep for old `flows/abc-bank`, `flows/escalate-to-agent` fragments returns no functional references.
  - _Requirements: 3.1, 3.2, 3.3, 1.7, 8.1, 8.2_

- [x] 8. Update documentation and run the final reference sweep
  - Rewrite the `README.md` "Repository layout" section for the new `projects/` tree, self-contained skills/hooks/MCP folders.
  - Update every `README.md` command example that referenced an old `scripts/...`, `lex_skills/...`, `src/...` path.
  - Check `.gitignore` for rules keyed to moved paths and update them.
  - Run a repo-wide sweep for every old path fragment; confirm no functional dangling references remain.
  - _Requirements: 9.1, 9.2, 8.2, 8.3_

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1", "5", "6.1"] },
    { "wave": 2, "tasks": ["2.1", "3", "4", "6.2"] },
    { "wave": 3, "tasks": ["2.2", "6.3"] },
    { "wave": 4, "tasks": ["7"] },
    { "wave": 5, "tasks": ["8"] }
  ],
  "dependencies": {
    "1": [],
    "2.1": ["1"],
    "2.2": ["2.1"],
    "3": ["1"],
    "4": ["1"],
    "5": [],
    "6.1": [],
    "6.2": ["6.1"],
    "6.3": ["6.2"],
    "7": ["6.3"],
    "8": ["1", "2.2", "3", "4", "5", "6.3", "7"]
  }
}
```

Dependency summary:
- 2, 3, 4 depend on 1 (package import resolution).
- 2.2 depends on 2.1; 6.2 depends on 6.1; 6.3 depends on 6.2.
- 7 depends on 6 (shared cleanup of top-level `flows/`).
- 8 depends on all prior tasks.
- 5 and 6.1 have no upstream dependencies and can run any time.

## Notes

- All moves use history-preserving relocate tooling, never
  delete-and-recreate.
- Every task carries a verification gate (`--dry-run`, import check, or
  grep sweep); a task is complete only when its gate passes.
- The repo has no formal test suite; verification is operational per the
  design's Testing Strategy.
- `init-flow-es` is tentatively telco-scoped (task 6.2); confirm by
  reading its `design.md` before moving — route to `_samples` only if
  it proves generic.
- The IaC capability is out of scope for this spec and deferred to
  future work.
