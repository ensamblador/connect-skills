"""Deploy a customer-managed Amazon Connect view from a ``view.json`` file.

A "view" here is a customer-managed view template authored by the
``connect-view-author`` skill — a JSON document with ``Template.Head``
plus ``Template.Body``, possibly with a sibling ``Actions`` list of
the flow-branch names referenced inside the view.

This script:

    1. Reads ``view.json`` (the ``Template`` body).
    2. Reads the actions list from a sibling file or a CLI arg.
    3. Validates the template structurally with
       ``connect_knowledge.view_validator.validate_view_json``. Aborts
       on any error before touching AWS.
    4. Stringifies the template into the
       ``CreateView``/``UpdateViewContent`` ``Content`` shape:
       ``{"Template": "<stringified-template>", "Actions": [...]}``.
    5. Calls ``connect.list_views`` to find an existing view by name
       in the target instance:
        - If found, calls ``UpdateViewContent`` (publishes by default;
          override with ``--status SAVED``).
        - If not found, calls ``CreateView`` with an idempotency
          ``ClientToken`` derived from the inputs.
    6. Calls ``CreateViewVersion`` to publish an immutable, numbered
       version (using the returned ``ViewContentSha256`` as a
       compare-and-swap guard).
    7. Optionally writes the deploy envelope (the
       ``view-content.json`` shape that the AWS CLI accepts as
       ``--content file://view-content.json``) for review or
       check-in.

Outputs the final ``viewId``, ``viewArn``, ``version``, and
``viewContentSha256`` as JSON on stdout, the way
``deploy_lex_skill.py`` does.

Run:

    # Dry run: validate, render the deploy envelope, no AWS calls
    uv run --with boto3 python \\
        .kiro/skills/connect-view-author/scripts/deploy_connect_view.py \\
        --view-file views/customer-escalation/view.json \\
        --view-name CustomerEscalation \\
        --actions Submit,Cancel \\
        --dry-run

    # Real deploy
    uv run --with boto3 python \\
        .kiro/skills/connect-view-author/scripts/deploy_connect_view.py \\
        --view-file views/customer-escalation/view.json \\
        --view-name CustomerEscalation \\
        --actions Submit,Cancel \\
        --instance-id <connect-instance-id> \\
        --region us-east-1

    # Use a sibling ``view-content.json`` for the actions instead
    uv run --with boto3 python \\
        .kiro/skills/connect-view-author/scripts/deploy_connect_view.py \\
        --view-file views/customer-escalation/view.json \\
        --view-name CustomerEscalation \\
        --content-file views/customer-escalation/view-content.json \\
        --instance-id <connect-instance-id>

References:
    - https://docs.aws.amazon.com/connect/latest/APIReference/API_CreateView.html
    - https://docs.aws.amazon.com/connect/latest/APIReference/API_UpdateViewContent.html
    - https://docs.aws.amazon.com/connect/latest/APIReference/API_CreateViewVersion.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# This script lives at ``.kiro/skills/connect-view-author/scripts/`` —
# four levels under the repo root (scripts → connect-view-author →
# skills → .kiro → repo root).
REPO_ROOT = Path(__file__).resolve().parents[4]

# Connect view name pattern, from API_CreateView.md.
# Length 1..255; letters/numbers and a small set of punctuation. We
# enforce at the script boundary so a deploy can't 400 on something
# we could have caught in the user's shell.
VIEW_NAME_LENGTH_MIN = 1
VIEW_NAME_LENGTH_MAX = 255


# ----- input loading & validation ----------------------------------------


@dataclass
class ViewInputs:
    view_path: Path
    template: dict[str, Any]   # the {Head, Body} body
    actions: list[str]         # the top-level Actions list
    name: str
    description: str | None
    status: str                # SAVED | PUBLISHED


def _load_view_template(path: Path) -> dict[str, Any]:
    """Load and parse a view.json file.

    Accepts two shapes:

    1. A bare template: ``{"Template": {"Head": ..., "Body": [...]}}``.
       This is the form the ``connect-view-author`` skill writes.
    2. A full envelope: ``{"Template": {...}, "Actions": [...]}``.
       Same shape as ``view-content.json`` but with the template as a
       nested object instead of a stringified blob.

    Both are normalized to the bare template here; the caller layers
    on the actions list separately.
    """
    if not path.is_file():
        raise FileNotFoundError(f"view file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"could not parse {path} as JSON: {exc.msg} at line {exc.lineno}, "
            f"column {exc.colno}. Note: the runtime does not accept // comments; "
            "remove them if you copy-pasted from the docs example."
        ) from exc
    if not isinstance(doc, dict):
        raise SystemExit(f"{path}: top-level must be a JSON object")
    return doc


def _resolve_actions(
    arg_actions: list[str] | None,
    content_file: Path | None,
    template_doc: dict[str, Any],
) -> list[str]:
    """Pick the actions list from the most specific source.

    Priority: ``--actions`` CLI arg > ``--content-file`` envelope >
    ``view.json`` envelope (when authored as full envelope) > empty.
    """
    if arg_actions is not None:
        return list(arg_actions)
    if content_file is not None:
        if not content_file.is_file():
            raise SystemExit(f"--content-file not found: {content_file}")
        envelope = json.loads(content_file.read_text(encoding="utf-8"))
        actions = envelope.get("Actions")
        if not isinstance(actions, list):
            raise SystemExit(
                f"{content_file}: expected an 'Actions' list at the top level"
            )
        return list(actions)
    actions = template_doc.get("Actions")
    if isinstance(actions, list):
        return list(actions)
    return []


def _validate_view(template_obj: dict[str, Any], actions: list[str]) -> None:
    """Run the local structural validator before any AWS call."""
    from connect_knowledge.view_validator import validate_view_json  # noqa: PLC0415

    payload = json.dumps({"Template": template_obj, "Actions": actions})
    report = validate_view_json(payload)
    if not report["valid"]:
        print("error: view JSON failed validation", file=sys.stderr)
        for issue in report["issues"]:
            print(f"  [{issue['severity']:7}] {issue['path']}: {issue['message']}", file=sys.stderr)
        raise SystemExit(2)
    if report["warning_count"]:
        print(
            f"warning: view validated with {report['warning_count']} warning(s):",
            file=sys.stderr,
        )
        for issue in report["issues"]:
            if issue["severity"] == "warning":
                print(f"  - {issue['path']}: {issue['message']}", file=sys.stderr)


def _validate_view_name(name: str) -> None:
    if not (VIEW_NAME_LENGTH_MIN <= len(name) <= VIEW_NAME_LENGTH_MAX):
        raise SystemExit(
            f"view name must be {VIEW_NAME_LENGTH_MIN}..{VIEW_NAME_LENGTH_MAX} chars, "
            f"got {len(name)}"
        )


def _normalize_template(doc: dict[str, Any]) -> dict[str, Any]:
    """Pull the bare ``{Head, Body}`` body out of either input shape."""
    template = doc.get("Template")
    if not isinstance(template, dict):
        raise SystemExit("view file is missing a 'Template' object at the top level")
    return template


# ----- envelope rendering -------------------------------------------------


def _render_envelope(template_obj: dict[str, Any], actions: list[str]) -> dict[str, Any]:
    """Build the ``Content`` payload accepted by CreateView / UpdateViewContent.

    The wire shape stringifies the template — boto3 doesn't do that
    for you. We pretty-print so a check-in version of the envelope
    diffs cleanly; AWS strips the whitespace before validating.
    """
    return {
        "Template": json.dumps(template_obj, indent=2, ensure_ascii=False),
        "Actions": list(actions),
    }


def _content_token(template_obj: dict[str, Any], actions: list[str], view_name: str) -> str:
    """Stable client token for idempotent CreateView calls.

    Hashes the inputs so a re-run with the same content reuses the
    same token; a meaningful change produces a new token.
    """
    payload = json.dumps(
        {"name": view_name, "template": template_obj, "actions": list(actions)},
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:48]


# ----- AWS calls ----------------------------------------------------------


def _import_connect(region: str):
    try:
        import boto3  # noqa: WPS433 — optional dep
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "boto3 is required for live deployment. Install with `uv pip install boto3` "
            "or run with --dry-run."
        ) from exc
    return boto3.client("connect", region_name=region)


def _find_existing_view(connect, instance_id: str, view_name: str) -> dict[str, Any] | None:
    """Return the View summary for ``view_name`` in the instance, or None."""
    paginator = connect.get_paginator("list_views")
    for page in paginator.paginate(InstanceId=instance_id):
        for summary in page.get("ViewsSummaryList", []):
            if summary.get("Name") == view_name:
                return summary
    return None


def _create_view(
    connect,
    instance_id: str,
    inputs: ViewInputs,
    actions: list[str],
) -> dict[str, Any]:
    content = _render_envelope(inputs.template, actions)
    kwargs: dict[str, Any] = {
        "InstanceId": instance_id,
        "Name": inputs.name,
        "Status": inputs.status,
        "Content": content,
        "ClientToken": _content_token(inputs.template, actions, inputs.name),
    }
    if inputs.description:
        kwargs["Description"] = inputs.description
    print(f"  CreateView name={inputs.name!r} status={inputs.status}", file=sys.stderr)
    return connect.create_view(**kwargs)["View"]


def _update_view_content(
    connect,
    instance_id: str,
    view_id: str,
    inputs: ViewInputs,
    actions: list[str],
) -> dict[str, Any]:
    content = _render_envelope(inputs.template, actions)
    print(f"  UpdateViewContent ViewId={view_id} status={inputs.status}", file=sys.stderr)
    return connect.update_view_content(
        InstanceId=instance_id,
        ViewId=view_id,
        Status=inputs.status,
        Content=content,
    )["View"]


def _create_view_version(
    connect,
    instance_id: str,
    view_id: str,
    sha: str | None,
    description: str | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"InstanceId": instance_id, "ViewId": view_id}
    if sha:
        kwargs["ViewContentSha256"] = sha
    if description:
        kwargs["VersionDescription"] = description
    print(f"  CreateViewVersion ViewId={view_id}", file=sys.stderr)
    return connect.create_view_version(**kwargs)["View"]


# ----- top-level deploy ---------------------------------------------------


def deploy(
    inputs: ViewInputs,
    actions: list[str],
    instance_id: str | None,
    region: str,
    artifact_dir: Path | None,
    publish_version: bool,
    version_description: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    # Always validate before any AWS call.
    _validate_view(inputs.template, actions)
    print(f"validated {inputs.view_path} ({len(actions)} action(s))", file=sys.stderr)

    envelope = _render_envelope(inputs.template, actions)

    if artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        envelope_path = artifact_dir / "view-content.json"
        envelope_path.write_text(
            json.dumps(envelope, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote deploy envelope → {envelope_path}", file=sys.stderr)

    if dry_run:
        print("dry-run: skipping all AWS calls", file=sys.stderr)
        return {
            "dryRun": True,
            "viewName": inputs.name,
            "actions": actions,
            "envelopeBytes": len(envelope["Template"]),
            "clientToken": _content_token(inputs.template, actions, inputs.name),
        }

    if not instance_id:
        raise SystemExit("--instance-id is required unless --dry-run is set")

    connect = _import_connect(region)

    print(f"resolving view {inputs.name!r} in instance {instance_id}…", file=sys.stderr)
    existing = _find_existing_view(connect, instance_id, inputs.name)
    if existing is None:
        view = _create_view(connect, instance_id, inputs, actions)
    else:
        view_id = existing["Id"]
        print(f"  found existing view {inputs.name!r} (Id={view_id})", file=sys.stderr)
        view = _update_view_content(connect, instance_id, view_id, inputs, actions)

    view_id = view["Id"]
    sha = view.get("ViewContentSha256")

    version_payload: dict[str, Any] | None = None
    if publish_version:
        if inputs.status != "PUBLISHED":
            print(
                "warning: --publish-version requires PUBLISHED status; "
                "current status is SAVED. Skipping CreateViewVersion.",
                file=sys.stderr,
            )
        else:
            version_payload = _create_view_version(
                connect,
                instance_id=instance_id,
                view_id=view_id,
                sha=sha,
                description=version_description,
            )

    return {
        "viewName": inputs.name,
        "viewId": view_id,
        "viewArn": view.get("Arn"),
        "viewStatus": view.get("Status"),
        "viewContentSha256": sha,
        "publishedVersion": version_payload.get("Version") if version_payload else None,
        "publishedVersionArn": version_payload.get("Arn") if version_payload else None,
        "instanceId": instance_id,
        "region": region,
    }


# ----- CLI ----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--view-file",
        type=Path,
        required=True,
        help="Path to view.json (the Template body, optionally a full envelope).",
    )
    parser.add_argument(
        "--view-name",
        required=True,
        help=(
            "Name of the view in Connect (1..255 chars). Letters, digits, "
            "and ._:/=+-@()' are allowed. Must be unique within the instance."
        ),
    )
    parser.add_argument(
        "--description",
        help="Optional view description (1..4096 chars).",
    )
    actions_group = parser.add_mutually_exclusive_group()
    actions_group.add_argument(
        "--actions",
        help=(
            "Comma-separated list of top-level Actions (e.g. 'Submit,Cancel'). "
            "Defaults: read from --content-file, then from view.json's "
            "envelope if present, then empty."
        ),
    )
    actions_group.add_argument(
        "--content-file",
        type=Path,
        help=(
            "Path to a sibling view-content.json carrying the Actions list. "
            "Useful when actions live alongside the template but the "
            "view.json itself is the bare Template body."
        ),
    )
    parser.add_argument(
        "--status",
        choices=("SAVED", "PUBLISHED"),
        default="PUBLISHED",
        help=(
            "View status to set during create/update. PUBLISHED triggers "
            "full content validation server-side (default). SAVED only "
            "performs basic validation."
        ),
    )
    parser.add_argument(
        "--instance-id",
        help="Connect instance ID. Required unless --dry-run is set.",
    )
    parser.add_argument(
        "--region", default=os.environ.get("AWS_REGION", "us-east-1")
    )
    parser.add_argument(
        "--publish-version",
        action="store_true",
        default=True,
        help=(
            "After create/update, call CreateViewVersion to publish an "
            "immutable numbered version. Default: enabled. Pair with "
            "--status PUBLISHED. Use --no-publish-version to skip."
        ),
    )
    parser.add_argument(
        "--no-publish-version",
        dest="publish_version",
        action="store_false",
        help="Skip CreateViewVersion after create/update.",
    )
    parser.add_argument(
        "--version-description",
        help="Optional description for the published version.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        help=(
            "Where to write the rendered deploy envelope (view-content.json). "
            "Skipped when not provided."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and render the deploy envelope without calling AWS.",
    )
    args = parser.parse_args(argv)

    _validate_view_name(args.view_name)

    template_doc = _load_view_template(args.view_file)
    template_obj = _normalize_template(template_doc)

    arg_actions: list[str] | None = None
    if args.actions is not None:
        arg_actions = [a.strip() for a in args.actions.split(",") if a.strip()]

    actions = _resolve_actions(arg_actions, args.content_file, template_doc)

    inputs = ViewInputs(
        view_path=args.view_file,
        template=template_obj,
        actions=actions,
        name=args.view_name,
        description=args.description,
        status=args.status,
    )

    result = deploy(
        inputs,
        actions,
        instance_id=args.instance_id,
        region=args.region,
        artifact_dir=args.artifact_dir,
        publish_version=args.publish_version,
        version_description=args.version_description,
        dry_run=args.dry_run,
    )

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
