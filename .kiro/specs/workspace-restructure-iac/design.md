# Design — Workspace Restructure

## Overview

This is a structural refactor. It moves project artifacts, skill code,
hook scripts, and MCP source into a consistent, self-contained layout.
No new runtime features are introduced.

The work is **path-sensitive**: the value is in moving files *and*
fixing every reference to them. The design therefore treats reference
integrity as a first-class concern, with a discovery → move → rewrite →
verify loop for each unit.

Two non-negotiables shape every decision:

1. **No functional regression.** The `connect_knowledge` MCP, its eight
   tools, the three CLIs, the deploy scripts, the refresh scripts, and
   the hooks must all still work.
2. **Git-history-preserving moves.** Use the relocate/move tooling, not
   delete-and-recreate, so blame survives.

> **Out of scope (future work):** the IaC capability (CDK authoring
> skill, `connect-cdk` steering, and a CDK docs MCP server) is deferred
> to a later spec and is intentionally absent from this design.

## Architecture

This is a structural refactor only. The refactor moves project
artifacts, skill code, hook scripts, and MCP source into a consistent,
self-contained layout.

### Current layout (relevant subset)

```
connect-skills/
├── pyproject.toml                      # packages = ["src/connect_knowledge"]
├── src/connect_knowledge/              # search/parse/validate package
├── connect_knowledge_mcp/              # MCP server (depends on src package)
│   └── connect_knowledge_mcp.py
├── scripts/
│   ├── _doc_fetcher.py                 # shared helper
│   ├── deploy_connect_view.py          # used by connect-view-author
│   ├── deploy_lex_skill.py             # used by q-in-connect-bot-deploy
│   ├── refresh_*.py                    # used by hooks + steering
│   └── refresh_connect_view_component_types.py  # used by connect-view-author
├── lex_skills/q_in_connect_passthrough/  # used by q-in-connect-bot-deploy
├── flows/{abc-bank-spanish-welcome,escalate-to-agent,init-flow-es,
│          telco-agent-screenpop-es,telco-selfservice-es-inbound}/
├── views/telco-escalation-handoff/
├── knowledge_base/telco-kb-es/
├── connect_ai_agents/telco-selfservice-es-us/
├── SampleBot/                          # unused; reference for lex skill
└── .kiro/
    ├── settings/mcp.json
    ├── hooks/refresh-*.kiro.hook       # command: uv run python scripts/refresh_*.py
    ├── steering/connect-*.md           # reference scripts/refresh_*.py
    └── skills/{connect-ai-agent-author,connect-flow-author,connect-kb-author,
                connect-researcher,connect-view-author,q-in-connect-bot-deploy}/
```

### Target layout

```
connect-skills/
├── pyproject.toml                      # repoints package to MCP folder (or workspace member)
├── connect_knowledge_mcp/
│   ├── connect_knowledge_mcp.py
│   ├── pyproject.toml
│   └── connect_knowledge/              # MOVED from src/  (search/parse/validate)
├── projects/
│   ├── telco-cx/
│   │   ├── knowledge_bases/telco-kb-es/
│   │   ├── connect_ai_agents/telco-selfservice-es-us/
│   │   ├── flows/{telco-agent-screenpop-es,telco-selfservice-es-inbound,init-flow-es}/
│   │   ├── views/telco-escalation-handoff/
│   │   └── lex_bots/                   # (created when a telco bot is deployed)
│   ├── abc-bank/
│   │   └── flows/abc-bank-spanish-welcome/
│   └── _samples/
│       └── flows/escalate-to-agent/
└── .kiro/
    ├── settings/mcp.json               # entrypoint unchanged
    ├── hooks/
    │   ├── refresh-*.kiro.hook         # command -> .kiro/hooks/scripts/refresh_*.py
    │   └── scripts/                    # MOVED refresh_*.py + _doc_fetcher.py
    ├── steering/
    │   └── connect-*.md                # references updated
    └── skills/
        ├── connect-view-author/
        │   ├── SKILL.md
        │   └── scripts/{deploy_connect_view.py,refresh_connect_view_component_types.py}  # MOVED
        ├── q-in-connect-bot-deploy/
        │   ├── SKILL.md
        │   ├── scripts/deploy_lex_skill.py     # MOVED
        │   └── lex_skills/q_in_connect_passthrough/  # MOVED
        └── (other skills unchanged)
```

> `SampleBot/` (top-level) is **deleted**, not relocated — it is fully
> superseded by the `q_in_connect_passthrough` template.

## Components and Interfaces

### D1 — How `connect_knowledge` package relocation preserves imports

The package under `src/connect_knowledge/` is imported by:
- `connect_knowledge_mcp/connect_knowledge_mcp.py` (the MCP server),
- the relocated deploy/refresh scripts (some import the validators /
  doc fetchers),
- the console-script CLIs declared in the root `pyproject.toml`.

**Decision:** move `src/connect_knowledge/` to
`connect_knowledge_mcp/connect_knowledge/` and make the MCP folder the
package home. The MCP's own `pyproject.toml` becomes the build/dep
authority for the package.

Two viable mechanisms — the design picks **(a)** and falls back to
**(b)** only if console-script entry points must remain at repo root:

- **(a) Single home in the MCP folder.** `connect_knowledge_mcp/pyproject.toml`
  sets `packages = ["connect_knowledge"]`. The root `pyproject.toml`
  either declares the MCP folder as the package source (via a path
  dependency / workspace member) or drops its own `[tool.hatch...]`
  package declaration and re-exposes the CLIs from the MCP project.
- **(b) Keep root as an installable that path-depends on the MCP
  package.** Heavier; only if the three console scripts must stay
  rootinvokable as `uv run connect-docs-search`.

Verification gate: after the move, `uv run --directory
connect_knowledge_mcp python connect_knowledge_mcp.py` imports cleanly,
and one tool (e.g. `validate_flow_json`) responds.

Because `.kiro/settings/mcp.json` already points
`--directory` at `connect_knowledge_mcp/` and runs
`connect_knowledge_mcp.py` (a path unchanged by this move), the MCP
registration needs no edit for the server entrypoint — only the
internal package import resolves differently, handled by the
`pyproject.toml` change.

### D2 — Skill self-containment

Relocate each skill-driven script into a `scripts/` subfolder inside the
owning skill, and the Lex template library into the Lex skill:

| From | To |
|---|---|
| `scripts/deploy_lex_skill.py` | `.kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py` |
| `lex_skills/q_in_connect_passthrough/` | `.kiro/skills/q-in-connect-bot-deploy/lex_skills/q_in_connect_passthrough/` |
| `scripts/deploy_connect_view.py` | `.kiro/skills/connect-view-author/scripts/deploy_connect_view.py` |
| `scripts/refresh_connect_view_component_types.py` | `.kiro/skills/connect-view-author/scripts/refresh_connect_view_component_types.py` |

The unused top-level `SampleBot/` is **deleted** (R7), not relocated:
it is a single-tenant console export with a hardcoded assistant ARN,
structurally identical to the `q_in_connect_passthrough` template which
parameterizes that ARN as `{{Q_ASSISTANT_ARN}}`. The template
encapsulates everything SampleBot demonstrated.

Then rewrite each `SKILL.md` command block to the new path. The deploy
scripts that import `connect_knowledge` (e.g. `deploy_connect_view.py`
uses `validate_view_json`) keep working because the package is installed
into the environment (D1); the invocation switches from
`uv run --with boto3 python scripts/...` to a form that resolves the
package — either `uv run --directory connect_knowledge_mcp ...` style or
keeping the package installed in the active venv. The exact invocation
is settled during the task and recorded in the SKILL.md.

`deploy_lex_skill.py` references the template via `--skill` +
`templateDirectory`; after the move the script resolves the template
relative to its own new location, so the `lex_skills/` library moves
with it.

### D3 — Hook self-containment

Move every hook-invoked refresh script plus the shared `_doc_fetcher.py`
into `.kiro/hooks/scripts/`. Update each `.kiro.hook` `command` from
`uv run python scripts/refresh_X.py` to
`uv run python .kiro/hooks/scripts/refresh_X.py`. Update steering files
and `connect-ai-agent-author/SKILL.md` that name the old paths.

Scripts that import `connect_knowledge` (some refresh scripts write
generated modules into the package, e.g.
`refresh_connect_view_component_types.py` regenerates
`_view_component_types.py`) need the package importable and the **write
target path** updated to the package's new home
(`connect_knowledge_mcp/connect_knowledge/_view_component_types.py`).
Note this script is owned by the view-author skill (D2), not the hooks
tree — its write-target update is handled there. Refresh scripts that
only write steering files (`refresh_connect_blocks.py`, etc.) just need
their own relative path to the steering dir kept correct.

### D4 — Projects layout & moves

Pure directory moves preserving contents. Mapping:

| From | To |
|---|---|
| `knowledge_base/telco-kb-es/` | `projects/telco-cx/knowledge_bases/telco-kb-es/` |
| `connect_ai_agents/telco-selfservice-es-us/` | `projects/telco-cx/connect_ai_agents/telco-selfservice-es-us/` |
| `flows/telco-agent-screenpop-es/` | `projects/telco-cx/flows/telco-agent-screenpop-es/` |
| `flows/telco-selfservice-es-inbound/` | `projects/telco-cx/flows/telco-selfservice-es-inbound/` |
| `flows/init-flow-es/` | `projects/telco-cx/flows/init-flow-es/` |
| `views/telco-escalation-handoff/` | `projects/telco-cx/views/telco-escalation-handoff/` |
| `flows/abc-bank-spanish-welcome/` | `projects/abc-bank/flows/abc-bank-spanish-welcome/` |
| `flows/escalate-to-agent/` | `projects/_samples/flows/escalate-to-agent/` |

`init-flow-es` is grouped with telco because it is the Spanish telco
inbound init flow companion; if discovery shows it is generic, it moves
to `_samples` instead — resolved during the task by reading its
`design.md`.

After moves, scan moved artifacts for self-referential paths:
- `connect_ai_agents/telco-selfservice-es-us/deploy.sh`,
  `.last-deploy.json`, `agent/*.json`
- `knowledge_base/telco-kb-es/manifest.json`, `_tag_contents.sh`,
  `_bucket-policy.json`, `_kms-key-policy.json`, `spec.md`
- each flow/view `design.md`

and rewrite any path that points at the artifact's old location.

## Data Models

This refactor introduces no new persisted data models. The relevant
"models" are the directory-layout contract and the path-mapping tables.

### Project layout contract

```
projects/<project_name>/
├── knowledge_bases/<knowledge_base_name>/
├── connect_ai_agents/<agent_name>/
├── flows/<flow_name>/
├── views/<view_name>/
└── lex_bots/<bot_name>/
```

### Path-mapping tables

The authoritative move mappings live in D2 (skill/SampleBot moves) and
D4 (project artifact moves). Those tables are the data model for the
restructure: each row is a `(from, to)` pair, and every move must update
all references to the `from` path.

## Data / reference flow after restructure

```
.kiro/settings/mcp.json
  └── connect_knowledge → uv run --directory connect_knowledge_mcp python connect_knowledge_mcp.py
                            └── imports connect_knowledge (now local to that folder)

.kiro/hooks/refresh-*.kiro.hook
  └── command: uv run python .kiro/hooks/scripts/refresh_*.py
                 └── (some) import connect_knowledge / write into its new home

.kiro/skills/q-in-connect-bot-deploy/SKILL.md
  └── scripts/deploy_lex_skill.py  + lex_skills/

.kiro/skills/connect-view-author/SKILL.md
  └── scripts/{deploy_connect_view.py, refresh_connect_view_component_types.py}
```

## Correctness Properties

These are the invariants every task must preserve.

### Property 1: Functional parity

For every skill, hook, MCP tool, CLI, and deploy/refresh script that
works before a move, the same command (at its updated path) produces
equivalent output after the move.

**Validates: Requirements 4.6, 5.5, 6.6**

### Property 2: No dangling references

After any move, a repo-wide search for the old path fragment returns no
*functional* reference (only historical mentions in dated notes are
acceptable).

**Validates: Requirements 8.1, 8.2**

### Property 3: Import resolution

Any relocated script that imports `connect_knowledge` resolves the
import from the package's single new home
(`connect_knowledge_mcp/connect_knowledge/`).

**Validates: Requirements 4.5, 5.4, 6.1**

### Property 4: Content preservation

A moved artifact directory's file contents are byte-identical to before
the move, except for path references it contains to its own previous
location.

**Validates: Requirements 1.7, 2.5**

### Property 5: History preservation

Moves use rename/relocate tooling so git blame survives.

**Validates: Requirements 1.7**

### Property 6: Layout consistency

Every project artifact lands at exactly the path dictated by the project
layout contract (Data Models).

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**

## Error Handling

### Error Handling and Edge Cases

- **Import breakage after package move (D1).** Mitigated by the
  per-move verification gate: run the MCP entrypoint and a CLI before
  marking the package-move task complete. If imports fail, the
  `pyproject.toml` package path is the first suspect.
- **Hook command path drift (D3).** Each hook edit is paired with a
  `--dry-run` of the relocated script to confirm it runs from the new
  path.
- **Self-referential paths in moved artifacts (D4).** A grep for the
  old path fragment (e.g. `connect_ai_agents/telco-selfservice-es-us`,
  `knowledge_base/telco-kb-es`, `flows/`) across the moved artifact
  catches deploy scripts and manifests that hardcode their own location.
- **`.gitignore` rules keyed to old paths (R8.3).** Checked and
  updated if any moved dir was ignored by path.

## Testing strategy

This repo has no formal test suite; verification is operational:

1. **Package move:** MCP server imports + one tool responds; one CLI
   runs.
2. **Skill scripts:** each relocated deploy script runs with `--dry-run`
   from its new path and produces equivalent output.
3. **Hook scripts:** each relocated refresh script runs with `--dry-run`
   (or `--skip-descriptions` quick mode) from its new path.
4. **Reference integrity:** repo-wide grep for each old path fragment
   returns no functional references (only historical mentions in dated
   notes are acceptable).

Each task carries its own verification gate; a task is not complete
until its gate passes.

## Implementation phasing

Ordered to keep the repo working at every step:

1. **MCP package self-containment (D1)** — foundational; everything that
   imports `connect_knowledge` depends on it resolving.
2. **Hook self-containment (D3)** — depends on (1) for import-bearing
   scripts.
3. **Skill self-containment (D2)** — depends on (1).
4. **SampleBot relocation (R7)** — independent, low risk.
5. **Projects moves (D4)** — independent of code moves; pure artifact
   relocation + intra-artifact reference fixes.
6. **README + reference sweep (R8/R9)** — last; documents the final
   state and catches stragglers.
