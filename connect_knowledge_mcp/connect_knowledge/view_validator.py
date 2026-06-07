"""Validate Amazon Connect customer-managed View JSON.

A view's ``Content`` payload (the body of ``CreateView`` /
``UpdateView``) has the shape::

    {
        "Template": {
            "Head": { "Title": "...", "Configuration": {...} },
            "Body": [ <component>, <component>, ... ]
        },
        "Actions": ["ActionA", "ActionB", ...]   # optional
    }

Each ``<component>`` is::

    {
        "_id": "<unique within view>",
        "Type": "<one of the catalog types>",
        "Props": { ... },
        "Content": [ <component>, ... ]   # optional, may also be a list of strings
    }

The ``Actions`` list at the top level enumerates every flow-branching
``Action`` value referenced inside component ``Props.Action``. The
``Show view`` flow block reads this list to surface one branch per
Action.

Reference:
    https://docs.aws.amazon.com/connect/latest/adminguide/view-resources-custom-view.html

What this validator checks (structural rules):

    - Top-level keys: ``Template`` (required), ``Actions`` (optional)
    - ``Template.Head`` is an object; ``Template.Head.Title`` is a string
    - ``Template.Body`` is a list (of components or strings)
    - Each component has ``_id``, ``Type``, ``Props`` (object)
    - ``_id`` is a non-empty string and unique across the view
    - ``Type`` is in the auto-generated catalog
    - ``Content`` (when present) is a list — items may be component
      objects or plain strings (e.g. a ``Button``'s label)
    - Required props per component are present (when known)
    - Every ``Props.Action`` value appears in the top-level ``Actions``
      list (warning if ``Actions`` is missing or empty)
    - Top-level ``Actions`` entries are unique strings

What this validator does NOT check (yet):

    - Per-component ``Props`` schema beyond required-prop names
      (different per Type; the View Dictionary docs page is the
      source of truth — use ``get_view_component_doc`` for spot
      checks).
    - Whether template strings (``$.Foo``, ``{{Foo}}``) actually
      resolve at runtime.
    - The size of the JSON payload (Connect imposes its own size
      limits on view content; the validator focuses on shape).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from connect_knowledge._view_component_types import (
    COMPONENT_HIERARCHIES,
    REQUIRED_PROPS,
    VALID_VIEW_COMPONENT_TYPES,
)


# ----- result types -------------------------------------------------------


@dataclass
class Issue:
    severity: str  # "error" | "warning"
    path: str  # JSONPath-ish, e.g. "Template.Body[0].Props"
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


# ----- internal helpers --------------------------------------------------


def _is_component_object(value: Any) -> bool:
    """A component is an object with at least ``_id`` and ``Type``."""
    return (
        isinstance(value, dict)
        and isinstance(value.get("_id"), str)
        and isinstance(value.get("Type"), str)
    )


def _collect_action_references(component: dict[str, Any]) -> list[tuple[str, str]]:
    """Walk a component subtree, returning ``(path_from_root, action_name)``
    for every ``Props.Action`` reference encountered.

    The walk is shallow on purpose: the caller passes in the path
    prefix and recurses into ``Content`` itself, so this helper only
    emits references for the component it was given.
    """
    refs: list[tuple[str, str]] = []
    props = component.get("Props")
    if isinstance(props, dict):
        action = props.get("Action")
        if isinstance(action, str) and action:
            refs.append(("", action))
    return refs


def _validate_component(
    component: Any,
    path: str,
    seen_ids: dict[str, str],
    declared_actions: set[str],
    referenced_actions: dict[str, str],
    report: Report,
) -> None:
    """Validate a single component in place; recurse into ``Content``.

    Args:
        component: The component object to validate.
        path: JSONPath-ish prefix for this component (e.g.
            ``Template.Body[0].Content[1]``).
        seen_ids: ``_id`` → first-seen path. Used to flag duplicates.
        declared_actions: Top-level ``Actions`` list, for cross-check.
        referenced_actions: ``action_name`` → path of first reference.
            Mutated as we walk.
        report: The Report accumulator.
    """
    if not isinstance(component, dict):
        report.add_error(path, "Component must be an object.")
        return

    # ``_id``
    cid = component.get("_id")
    if not isinstance(cid, str) or not cid:
        report.add_error(f"{path}._id", "Component is missing required field '_id' (non-empty string).")
    else:
        first = seen_ids.get(cid)
        if first is not None:
            report.add_error(
                f"{path}._id",
                f"Duplicate _id {cid!r}; first defined at {first}.",
            )
        else:
            seen_ids[cid] = path

    # ``Type``
    ctype = component.get("Type")
    if not isinstance(ctype, str) or not ctype:
        report.add_error(f"{path}.Type", "Component is missing required field 'Type' (non-empty string).")
        ctype = None
    elif ctype not in VALID_VIEW_COMPONENT_TYPES:
        report.add_error(
            f"{path}.Type",
            f"Type {ctype!r} is not a known view component. "
            "If this was added recently, refresh the catalog with: "
            "uv run python .kiro/skills/connect-view-author/scripts/refresh_connect_view_component_types.py",
        )
        ctype = None

    # ``Props``
    props = component.get("Props")
    if "Props" not in component:
        report.add_error(f"{path}.Props", "Component is missing required field 'Props' (object).")
    elif not isinstance(props, dict):
        report.add_error(f"{path}.Props", "Props must be an object.")
        props = None

    # Required props per Type (when we have a snapshot)
    if ctype is not None and isinstance(props, dict):
        required = REQUIRED_PROPS.get(ctype)
        if required:
            missing = sorted(required - set(props))
            for name in missing:
                report.add_error(
                    f"{path}.Props.{name}",
                    f"Required prop {name!r} for component Type {ctype!r} is missing.",
                )

    # Action references collected from this component's Props
    if isinstance(props, dict):
        for _, action in _collect_action_references(component):
            if action not in referenced_actions:
                referenced_actions[action] = f"{path}.Props.Action"
            if declared_actions and action not in declared_actions:
                report.add_error(
                    f"{path}.Props.Action",
                    f"Action {action!r} is not declared in the top-level "
                    f"'Actions' list ({sorted(declared_actions)}).",
                )

    # ``Content`` (recursive)
    if "Content" in component:
        content = component["Content"]
        if not isinstance(content, list):
            report.add_error(f"{path}.Content", "Content must be a list.")
        else:
            for i, child in enumerate(content):
                child_path = f"{path}.Content[{i}]"
                if isinstance(child, str):
                    # A string child is a label / static text — valid.
                    continue
                if isinstance(child, dict):
                    _validate_component(
                        child, child_path, seen_ids, declared_actions, referenced_actions, report
                    )
                else:
                    report.add_error(
                        child_path,
                        "Content entry must be either a component object or a string label.",
                    )


# ----- public entry point -------------------------------------------------


def validate_view(view: Any) -> Report:
    """Validate a parsed view dict. See :func:`validate_view_json` for the
    JSON-string variant.
    """
    report = Report()

    if not isinstance(view, dict):
        report.add_error("$", "Top-level value must be an object.")
        return report

    # ``Template``
    template = view.get("Template")
    if template is None:
        report.add_error("Template", "Required field 'Template' is missing.")
        template = {}
    elif not isinstance(template, dict):
        report.add_error("Template", "Template must be an object.")
        template = {}

    # ``Template.Head``
    head = template.get("Head") if isinstance(template, dict) else None
    if "Head" not in (template or {}):
        report.add_error("Template.Head", "Required field 'Head' is missing.")
    elif not isinstance(head, dict):
        report.add_error("Template.Head", "Head must be an object.")
    else:
        title = head.get("Title")
        if title is None:
            report.add_warning(
                "Template.Head.Title",
                "Head.Title is not set. Connect renders the view without a title bar in this case.",
            )
        elif not isinstance(title, str):
            report.add_error("Template.Head.Title", "Title must be a string.")

    # ``Template.Body``
    body = template.get("Body") if isinstance(template, dict) else None
    if body is None:
        report.add_error("Template.Body", "Required field 'Body' is missing.")
        body = []
    elif not isinstance(body, list):
        report.add_error("Template.Body", "Body must be a list of components.")
        body = []

    # Top-level ``Actions``
    actions_raw = view.get("Actions")
    declared_actions: set[str] = set()
    if actions_raw is not None:
        if not isinstance(actions_raw, list):
            report.add_error("Actions", "Actions must be a list of strings.")
        else:
            seen_actions: set[str] = set()
            for i, a in enumerate(actions_raw):
                if not isinstance(a, str) or not a:
                    report.add_error(
                        f"Actions[{i}]",
                        "Action entry must be a non-empty string.",
                    )
                    continue
                if a in seen_actions:
                    report.add_error(
                        f"Actions[{i}]",
                        f"Duplicate Action entry {a!r}.",
                    )
                else:
                    seen_actions.add(a)
                    declared_actions.add(a)

    # Walk Body
    seen_ids: dict[str, str] = {}
    referenced_actions: dict[str, str] = {}
    for i, child in enumerate(body):
        child_path = f"Template.Body[{i}]"
        if isinstance(child, str):
            # Body-level strings are unusual but harmless.
            continue
        if isinstance(child, dict):
            _validate_component(
                child, child_path, seen_ids, declared_actions, referenced_actions, report
            )
        else:
            report.add_error(
                child_path,
                "Body entry must be either a component object or a string.",
            )

    # Cross-check: every declared Action should be referenced somewhere
    # (else the top-level list is over-declared) — warning, not error,
    # because an author may stage Actions before wiring the buttons.
    if declared_actions and referenced_actions:
        unreferenced = sorted(declared_actions - referenced_actions.keys())
        for name in unreferenced:
            report.add_warning(
                "Actions",
                f"Action {name!r} is declared at the top level but not referenced "
                "by any component's Props.Action.",
            )

    # When a component references Actions but the top-level list is
    # missing, surface a single warning (one per missing-list) rather
    # than an error per reference.
    if not declared_actions and referenced_actions:
        sample = next(iter(referenced_actions))
        report.add_warning(
            "Actions",
            f"Components reference {len(referenced_actions)} Action value(s) "
            f"(e.g. {sample!r}) but the top-level 'Actions' list is missing or "
            "empty. The Show view block will not surface flow branches.",
        )

    return report


def validate_view_json(json_str: str) -> dict[str, Any]:
    """Parse and validate a view JSON string. Returns a JSON-friendly dict.

    Args:
        json_str: The view ``Content`` JSON as a string. The runtime
            requires plain JSON — the canonical example on the docs
            page uses ``//`` comments for narration; remove them
            before validating.

    Returns:
        Dict with ``valid`` (bool), ``error_count``, ``warning_count``,
        ``issues`` (list of ``{severity, path, message}``),
        ``summary`` (str), and ``component_hierarchies`` (``_id`` →
        list of hierarchies the Type is documented under, useful for
        sanity-checking FormView components).
    """
    try:
        view = json.loads(json_str)
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

    report = validate_view(view)
    err_count = len(report.errors)
    warn_count = len(report.warnings)
    if err_count == 0 and warn_count == 0:
        summary = "View is valid. No issues found."
    elif err_count == 0:
        summary = f"View is structurally valid with {warn_count} warning(s)."
    else:
        summary = f"View has {err_count} error(s) and {warn_count} warning(s)."

    component_hierarchies: dict[str, list[str]] = {}
    if isinstance(view, dict):
        template = view.get("Template")
        body = template.get("Body") if isinstance(template, dict) else None
        if isinstance(body, list):
            stack: list[Any] = list(body)
            while stack:
                node = stack.pop()
                if not isinstance(node, dict):
                    continue
                cid = node.get("_id")
                ctype = node.get("Type")
                if isinstance(cid, str) and isinstance(ctype, str):
                    component_hierarchies[cid] = sorted(
                        COMPONENT_HIERARCHIES.get(ctype, frozenset())
                    )
                content = node.get("Content")
                if isinstance(content, list):
                    stack.extend(content)

    return {
        "valid": err_count == 0,
        "error_count": err_count,
        "warning_count": warn_count,
        "issues": [i.to_dict() for i in report.issues],
        "summary": summary,
        "component_hierarchies": component_hierarchies,
    }
