"""Validate Amazon Connect Flow language JSON.

Checks the structural rules from the Flow language reference:

    - Top-level keys: ``Version``, ``StartAction``, ``Actions``, ``Metadata?``
    - Each Action has ``Identifier``, ``Type``, ``Parameters``, ``Transitions``
    - ``Identifier`` rules: ≤50 chars, no forbidden characters or values,
      unique within the flow
    - ``Type`` is in the known catalog (auto-generated from the docs)
    - ``Transitions`` shape: ``NextAction``, ``Errors``, ``Conditions``
    - Every referenced ``NextAction`` exists as an ``Identifier``
    - ``Condition`` ``Operator`` is in the closed set
    - Conditions nest no more than 5 deep, no more than 50 sub-Conditions total
    - ``Actions`` list has at most 250 entries
    - ``Version`` is the currently supported value (``2019-10-30``)
    - The ``StartAction`` is reachable; orphan actions are reported as warnings
    - AI-agent self-service pattern lints (warnings): a
      ``ConnectParticipantWithLexBot`` Action missing the
      ``x-amz-lex:q-in-connect:ai-agent-arn`` session attribute (falls
      back to the instance default agent), or missing a
      ``NoMatchingCondition`` error branch (the branch a Q-in-Connect
      bot turn actually exits through).

What this validator does NOT check (yet):

    - Per-Action ``Parameters`` schema (different per Action; would require
      fetching ``get_action_doc`` for every distinct Type in the flow).
      Use ``get_action_doc`` directly for spot-checks.
    - Per-Action allowed ``ErrorType`` values in ``Transitions.Errors``.
    - Whether dynamic attribute references (``$.External.Foo``) actually
      resolve at runtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from connect_knowledge._action_types import ACTION_CATEGORY, VALID_ACTION_TYPES

SUPPORTED_VERSIONS = frozenset({"2019-10-30"})
MAX_ACTIONS_PER_FLOW = 250
MAX_IDENTIFIER_LEN = 50
MAX_CONDITION_DEPTH = 5
MAX_CONDITIONS_TOTAL = 50

FORBIDDEN_IDENTIFIER_CHARS = set("%:(\\/)= $,;[]{}")
# The "$" and " " above are intentional per the upstream rules.
FORBIDDEN_IDENTIFIER_VALUES: frozenset[str] = frozenset(
    {
        "__proto__",
        "constructor",
        "__defineGetter__",
        "__defineSetter__",
        "toString",
        "hasOwnProperty",
        "isPrototypeOf",
        "propertyIsEnumerable",
        "toLocaleString",
        "valueOf",
    }
)

VALID_OPERATORS: frozenset[str] = frozenset(
    {
        "Equals",
        "TextStartsWith",
        "TextEndsWith",
        "TextContains",
        "NumberGreaterThan",
        "NumberGreaterOrEqualTo",
        "NumberLessThan",
        "NumberLessOrEqualTo",
    }
)


# ----- result types -------------------------------------------------------


@dataclass
class Issue:
    severity: str  # "error" | "warning"
    path: str  # JSONPath-ish, e.g. "Actions[3].Identifier"
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"severity": self.severity, "path": self.path, "message": self.message}


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    def add_error(self, path: str, message: str) -> None:
        self.issues.append(Issue("error", path, message))

    def add_warning(self, path: str, message: str) -> None:
        self.issues.append(Issue("warning", path, message))


# ----- validators ---------------------------------------------------------


def _validate_identifier(ident: Any, path: str, report: Report) -> bool:
    if not isinstance(ident, str):
        report.add_error(path, f"Identifier must be a string, got {type(ident).__name__}.")
        return False
    if not ident:
        report.add_error(path, "Identifier must be non-empty.")
        return False
    if len(ident) > MAX_IDENTIFIER_LEN:
        report.add_error(
            path,
            f"Identifier exceeds {MAX_IDENTIFIER_LEN} characters (got {len(ident)}).",
        )
    bad_chars = sorted(set(ident) & FORBIDDEN_IDENTIFIER_CHARS)
    if bad_chars:
        report.add_error(
            path,
            f"Identifier contains forbidden character(s): {''.join(bad_chars)!r}.",
        )
    if ident in FORBIDDEN_IDENTIFIER_VALUES:
        report.add_error(
            path, f"Identifier {ident!r} is a reserved/forbidden value."
        )
    return True


def _count_conditions(condition: Any) -> tuple[int, int]:
    """Return ``(max_depth, total_sub_conditions)`` for a Condition object."""
    if not isinstance(condition, dict):
        return 0, 0
    operands = condition.get("Operands", [])
    nested = [op for op in (operands if isinstance(operands, list) else []) if isinstance(op, dict)]
    if not nested:
        return 1, 1
    depths = []
    totals = 0
    for sub in nested:
        d, t = _count_conditions(sub)
        depths.append(d)
        totals += t
    return 1 + max(depths), 1 + totals


def _validate_condition(condition: Any, path: str, report: Report) -> None:
    if not isinstance(condition, dict):
        report.add_error(path, "Condition must be an object.")
        return
    op = condition.get("Operator")
    if op is None:
        report.add_error(path, "Condition missing required field 'Operator'.")
    elif op not in VALID_OPERATORS:
        report.add_error(
            path,
            f"Operator {op!r} is not in the valid set "
            f"({', '.join(sorted(VALID_OPERATORS))}).",
        )
    if "Operands" not in condition:
        report.add_error(path, "Condition missing required field 'Operands'.")
    elif not isinstance(condition["Operands"], list):
        report.add_error(path, "Condition.Operands must be a list.")
    depth, total = _count_conditions(condition)
    if depth > MAX_CONDITION_DEPTH:
        report.add_error(
            path,
            f"Condition nested {depth} deep; maximum allowed is {MAX_CONDITION_DEPTH}.",
        )
    if total > MAX_CONDITIONS_TOTAL:
        report.add_error(
            path,
            f"Condition has {total} sub-Conditions; maximum allowed is {MAX_CONDITIONS_TOTAL}.",
        )


def _collect_next_action_targets(transitions: dict[str, Any], path: str, report: Report) -> list[str]:
    targets: list[str] = []
    next_action = transitions.get("NextAction")
    if next_action is not None:
        if not isinstance(next_action, str):
            report.add_error(f"{path}.NextAction", "NextAction must be a string Identifier.")
        else:
            targets.append(next_action)
    errors = transitions.get("Errors", [])
    if not isinstance(errors, list):
        report.add_error(f"{path}.Errors", "Errors must be a list.")
        errors = []
    for i, err in enumerate(errors):
        if not isinstance(err, dict):
            report.add_error(f"{path}.Errors[{i}]", "Error entry must be an object.")
            continue
        if "ErrorType" not in err:
            report.add_error(f"{path}.Errors[{i}]", "Error entry missing 'ErrorType'.")
        target = err.get("NextAction")
        if not isinstance(target, str):
            report.add_error(
                f"{path}.Errors[{i}].NextAction",
                "Error entry NextAction must be a string Identifier.",
            )
        else:
            targets.append(target)
    conditions = transitions.get("Conditions", [])
    if not isinstance(conditions, list):
        report.add_error(f"{path}.Conditions", "Conditions must be a list.")
        conditions = []
    for i, cond_entry in enumerate(conditions):
        cond_path = f"{path}.Conditions[{i}]"
        if not isinstance(cond_entry, dict):
            report.add_error(cond_path, "Condition entry must be an object.")
            continue
        target = cond_entry.get("NextAction")
        if not isinstance(target, str):
            report.add_error(
                f"{cond_path}.NextAction",
                "Condition entry NextAction must be a string Identifier.",
            )
        else:
            targets.append(target)
        _validate_condition(cond_entry.get("Condition"), f"{cond_path}.Condition", report)
    return targets


def _reachable_from(start: str, edges: dict[str, list[str]]) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        for nxt in edges.get(node, []):
            if nxt not in seen:
                stack.append(nxt)
    return seen


# Session attribute the Get customer input block's "Enable AI Agent"
# toggle writes to pin a specific orchestration agent + version on a
# Q-in-Connect self-service contact. Without it, the Lex / Q-in-Connect
# path falls back to the assistant's *default* SELF_SERVICE agent — a
# silent behavior change that does not fail validation or runtime, it
# just runs the wrong agent.
AI_AGENT_ARN_SESSION_ATTR = "x-amz-lex:q-in-connect:ai-agent-arn"


def _check_ai_agent_self_service(actions: list[Any], report: Report) -> None:
    """Warn on common wiring gaps in the AI-agent self-service pattern.

    Two checks, both warning-level (the flow is structurally valid
    either way, but these are the gaps that bite in production):

    1. A ``ConnectParticipantWithLexBot`` Action with no
       ``x-amz-lex:q-in-connect:ai-agent-arn`` in ``LexSessionAttributes``
       relies on the instance's *default* SELF_SERVICE agent. If you
       deployed a custom agent and did not set it as the default, the
       wrong agent runs. The Get customer input "Enable AI Agent"
       toggle sets this attribute; raw flow JSON often omits it.

    2. A ``ConnectParticipantWithLexBot`` Action whose ``Transitions``
       route the bot turn off ``NextAction`` (Success) but never wire
       the ``NoMatchingCondition`` error branch. A Q-in-Connect
       passthrough bot returns an intent that matches no condition, so
       it exits via ``NoMatchingCondition`` (the block's Default
       branch). Tool-routing hung off Success never runs.
    """
    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        if action.get("Type") != "ConnectParticipantWithLexBot":
            continue
        path = f"Actions[{i}]"
        params = action.get("Parameters")
        params = params if isinstance(params, dict) else {}
        session_attrs = params.get("LexSessionAttributes")
        session_attrs = session_attrs if isinstance(session_attrs, dict) else {}
        if AI_AGENT_ARN_SESSION_ATTR not in session_attrs:
            report.add_warning(
                f"{path}.Parameters.LexSessionAttributes",
                "ConnectParticipantWithLexBot has no "
                f"{AI_AGENT_ARN_SESSION_ATTR!r} session attribute. For "
                "Q-in-Connect self-service this means the assistant's "
                "DEFAULT SELF_SERVICE agent runs, not a specific one. "
                "Set this attribute (the Get customer input 'Enable AI "
                "Agent' toggle does it) to pin a chosen agent+version, "
                "or make your agent the instance default.",
            )
        transitions = action.get("Transitions")
        transitions = transitions if isinstance(transitions, dict) else {}
        errors = transitions.get("Errors", [])
        error_types = {
            e.get("ErrorType")
            for e in (errors if isinstance(errors, list) else [])
            if isinstance(e, dict)
        }
        if "NoMatchingCondition" not in error_types:
            report.add_warning(
                f"{path}.Transitions.Errors",
                "ConnectParticipantWithLexBot has no 'NoMatchingCondition' "
                "error branch. A Q-in-Connect passthrough bot returns an "
                "intent that matches no block condition, so the bot turn "
                "exits via NoMatchingCondition (the Default branch). Route "
                "your tool-handling (Check contact attributes) off that "
                "branch — wiring it off Success means it never runs.",
            )


# ----- public entry point -------------------------------------------------


def validate_flow(flow: dict[str, Any]) -> Report:
    """Validate a parsed flow dict. See :func:`validate_flow_json` for the JSON-string variant."""
    report = Report()

    if not isinstance(flow, dict):
        report.add_error("$", "Top-level value must be an object.")
        return report

    # Version
    version = flow.get("Version")
    if version is None:
        report.add_error("Version", "Required field 'Version' is missing.")
    elif version not in SUPPORTED_VERSIONS:
        report.add_warning(
            "Version",
            f"Version {version!r} is not in the supported set "
            f"({', '.join(sorted(SUPPORTED_VERSIONS))}). "
            "Validation may be inaccurate.",
        )

    # Actions
    actions = flow.get("Actions")
    if not isinstance(actions, list):
        report.add_error("Actions", "Required field 'Actions' must be a list.")
        return report
    if len(actions) > MAX_ACTIONS_PER_FLOW:
        report.add_error(
            "Actions",
            f"Flow has {len(actions)} Actions; maximum is {MAX_ACTIONS_PER_FLOW}.",
        )

    seen_identifiers: dict[str, int] = {}
    edges: dict[str, list[str]] = {}

    for i, action in enumerate(actions):
        path = f"Actions[{i}]"
        if not isinstance(action, dict):
            report.add_error(path, "Action must be an object.")
            continue

        # Identifier
        ident = action.get("Identifier")
        ok = _validate_identifier(ident, f"{path}.Identifier", report)
        if ok and isinstance(ident, str):
            if ident in seen_identifiers:
                report.add_error(
                    f"{path}.Identifier",
                    f"Duplicate Identifier {ident!r}; "
                    f"first defined at Actions[{seen_identifiers[ident]}].",
                )
            else:
                seen_identifiers[ident] = i

        # Type
        action_type = action.get("Type")
        if action_type is None:
            report.add_error(f"{path}.Type", "Required field 'Type' is missing.")
        elif not isinstance(action_type, str):
            report.add_error(f"{path}.Type", "Type must be a string.")
        elif action_type not in VALID_ACTION_TYPES:
            report.add_error(
                f"{path}.Type",
                f"Type {action_type!r} is not a known Action type. "
                "If this was added recently, refresh the action-types module "
                "with: uv run python .kiro/scripts/refresh_connect_flow_language.py",
            )

        # Parameters: must exist (may be empty)
        if "Parameters" not in action:
            report.add_error(f"{path}.Parameters", "Required field 'Parameters' is missing.")
        elif not isinstance(action["Parameters"], dict):
            report.add_error(f"{path}.Parameters", "Parameters must be an object.")

        # Transitions
        transitions = action.get("Transitions")
        if transitions is None:
            report.add_error(f"{path}.Transitions", "Required field 'Transitions' is missing.")
        elif not isinstance(transitions, dict):
            report.add_error(f"{path}.Transitions", "Transitions must be an object.")
        else:
            targets = _collect_next_action_targets(transitions, f"{path}.Transitions", report)
            if isinstance(ident, str):
                edges[ident] = targets

    # StartAction
    start = flow.get("StartAction")
    if start is None:
        report.add_error("StartAction", "Required field 'StartAction' is missing.")
    elif not isinstance(start, str):
        report.add_error("StartAction", "StartAction must be a string Identifier.")
    elif start not in seen_identifiers:
        report.add_error(
            "StartAction",
            f"StartAction {start!r} does not match any Action's Identifier.",
        )

    # NextAction reference resolution
    for ident, targets in edges.items():
        for target in targets:
            if target not in seen_identifiers:
                report.add_error(
                    f"Actions[{seen_identifiers[ident]}].Transitions",
                    f"NextAction {target!r} does not match any Action's Identifier.",
                )

    # Reachability (warnings only)
    if isinstance(start, str) and start in seen_identifiers:
        reachable = _reachable_from(start, edges)
        for ident in seen_identifiers:
            if ident not in reachable:
                report.add_warning(
                    f"Actions[{seen_identifiers[ident]}]",
                    f"Action {ident!r} is unreachable from StartAction.",
                )

    # AI-agent self-service pattern checks (warnings only)
    _check_ai_agent_self_service(actions, report)

    return report


def validate_flow_json(json_str: str) -> dict[str, Any]:
    """Parse and validate a flow JSON string. Returns a JSON-friendly dict.

    Args:
        json_str: The flow JSON as a string. Must be valid JSON (no
            ``//`` comments — the canonical example page on docs uses
            comments for narration, but the runtime requires plain JSON).

    Returns:
        Dict with ``valid`` (bool), ``error_count``, ``warning_count``,
        ``issues`` (list of ``{severity, path, message}``), and
        ``summary`` (str).
    """
    try:
        flow = json.loads(json_str)
    except json.JSONDecodeError as exc:
        return {
            "valid": False,
            "error_count": 1,
            "warning_count": 0,
            "issues": [
                {
                    "severity": "error",
                    "path": "$",
                    "message": (
                        f"JSON parse error: {exc.msg} at line {exc.lineno} "
                        f"column {exc.colno}. Note: the docs example uses "
                        "// comments for narration; the runtime does not "
                        "accept comments."
                    ),
                }
            ],
            "summary": "Could not parse JSON. See issues for details.",
        }

    report = validate_flow(flow)
    err_count = len(report.errors)
    warn_count = len(report.warnings)
    if err_count == 0 and warn_count == 0:
        summary = "Flow is valid. No issues found."
    elif err_count == 0:
        summary = f"Flow is structurally valid with {warn_count} warning(s)."
    else:
        summary = f"Flow has {err_count} error(s) and {warn_count} warning(s)."

    return {
        "valid": err_count == 0,
        "error_count": err_count,
        "warning_count": warn_count,
        "issues": [i.to_dict() for i in report.issues],
        "summary": summary,
        "action_categories": {
            ident: ACTION_CATEGORY.get(
                next(
                    (a.get("Type") for a in flow.get("Actions", [])
                     if isinstance(a, dict) and a.get("Identifier") == ident),
                    "",
                ),
                "Unknown",
            )
            for ident in (
                a.get("Identifier")
                for a in flow.get("Actions", [])
                if isinstance(a, dict) and isinstance(a.get("Identifier"), str)
            )
        },
    }
