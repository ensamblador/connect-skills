"""Deploy a Lex V2 skill from this repo's ``lex_skills/`` library.

A "skill" is a parameterized Lex V2 import bundle (template directory
that mirrors the console export layout) plus a small ``skill.json``
manifest describing its required parameters.

This script:

    1. Reads ``<skill>/skill.json``.
    2. Materializes a deployment copy of ``<skill>/template/`` in a temp
       dir, substituting ``{{PLACEHOLDER}}`` tokens (bot name, Q in
       Connect assistant ARN, etc.) and renaming the inner bot folder
       to the per-tenant bot name.
    3. Zips the bundle.
    4. ``CreateUploadUrl`` → presigned ``PUT`` upload → ``StartImport``.
    5. Polls ``DescribeImport`` until ``Completed``.
    6. ``BuildBotLocale`` for every locale, polling ``DescribeBotLocale``
       until ``Built``.
    7. ``CreateBotVersion`` (a numeric snapshot of DRAFT).
    8. ``CreateBotAlias`` (or ``UpdateBotAlias`` if it already exists)
       pointing the configured alias at the new version.
    9. *(Optional)* ``connect.associate_bot`` to wire the alias into a
       Connect instance.

Run:

    uv run --with boto3 python .kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py \\
        --skill q_in_connect_passthrough \\
        --bot-name AcmeHotelBookingBot \\
        --q-assistant-arn arn:aws:wisdom:us-east-1:111122223333:assistant/<id> \\
        --bot-role-arn arn:aws:iam::111122223333:role/AWSServiceRoleForLexV2Bots_acme \\
        --region us-east-1 \\
        --connect-instance-id <connect-instance-id>

Add ``--dry-run`` to render and zip the bundle without calling AWS.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The skill is self-contained: this script lives at
# .kiro/skills/q-in-connect-bot-deploy/scripts/deploy_lex_skill.py and the
# template library is a sibling at
# .kiro/skills/q-in-connect-bot-deploy/lex_skills/. Resolve the library
# relative to this file so the skill folder is a portable unit.
SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = SKILL_ROOT / "lex_skills"

POLL_INTERVAL = 5  # seconds between Describe* polls
IMPORT_TIMEOUT = 600  # seconds
BUILD_TIMEOUT = 900  # seconds per locale


# ----- skill manifest loading --------------------------------------------


@dataclass
class SkillManifest:
    name: str
    template_dir: Path  # absolute path to the directory holding Manifest.json
    template_bot_dir: str  # name of the bot folder inside template_dir
    locales: list[str]
    parameters: dict[str, dict[str, Any]]
    alias_name: str
    alias_description: str | None

    @classmethod
    def load(cls, skill_dir: Path) -> "SkillManifest":
        manifest_path = skill_dir / "skill.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"skill manifest not found: {manifest_path}")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        template_dir = skill_dir / data["templateDirectory"]
        if not template_dir.is_dir():
            raise FileNotFoundError(f"template dir not found: {template_dir}")
        return cls(
            name=data["name"],
            template_dir=template_dir,
            template_bot_dir=data["templateBotDirectory"],
            locales=list(data["locales"]),
            parameters=dict(data.get("parameters", {})),
            alias_name=data.get("alias", {}).get("name", "prod"),
            alias_description=data.get("alias", {}).get("description"),
        )


# ----- substitution + zip -------------------------------------------------


PLACEHOLDER_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")


def _substitute_text(text: str, substitutions: dict[str, str]) -> str:
    """Replace every ``{{KEY}}`` token with its value. Strict — unknown
    placeholders raise so we never push half-rendered JSON to AWS.
    """

    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        key = token[2:-2]
        if key not in substitutions:
            raise KeyError(f"no value provided for placeholder {token}")
        return substitutions[key]

    return PLACEHOLDER_RE.sub(repl, text)


def _materialize_bundle(
    template_dir: Path,
    template_bot_dir: str,
    bot_name: str,
    substitutions: dict[str, str],
    out_dir: Path,
) -> Path:
    """Copy the template tree into ``out_dir`` with substitutions applied,
    renaming the inner bot directory to ``bot_name``. Returns ``out_dir``.
    """
    for src_path in template_dir.rglob("*"):
        rel = src_path.relative_to(template_dir)
        # rename the inner bot dir to bot_name
        rel_parts = list(rel.parts)
        if rel_parts and rel_parts[0] == template_bot_dir:
            rel_parts[0] = bot_name
        dst_path = out_dir.joinpath(*rel_parts)
        if src_path.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
            continue
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        text = src_path.read_text(encoding="utf-8")
        rendered = _substitute_text(text, substitutions)
        dst_path.write_text(rendered, encoding="utf-8")
    return out_dir


def _zip_bundle(bundle_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in bundle_dir.rglob("*"):
            if path.is_dir():
                continue
            zf.write(path, path.relative_to(bundle_dir).as_posix())
    return zip_path


# ----- AWS calls ----------------------------------------------------------


def _import_lex_models(region: str):
    try:
        import boto3  # noqa: WPS433 — optional dep
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "boto3 is required for live deployment. Install with `uv pip install boto3` "
            "or run with --dry-run."
        ) from exc
    return boto3.client("lexv2-models", region_name=region), boto3.client(
        "connect", region_name=region
    )


def _upload_zip(presigned_url: str, zip_path: Path) -> None:
    """PUT the zip to the Lex-provided presigned URL.

    Uses urllib (stdlib) to avoid an extra dependency.
    """
    import urllib.request

    data = zip_path.read_bytes()
    req = urllib.request.Request(
        presigned_url,
        data=data,
        method="PUT",
        headers={"Content-Type": "application/zip"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 — Lex URL
        if resp.status not in (200, 204):
            raise RuntimeError(f"presigned upload failed: HTTP {resp.status}")


def _wait_import(lex, import_id: str) -> dict[str, Any]:
    deadline = time.time() + IMPORT_TIMEOUT
    while time.time() < deadline:
        resp = lex.describe_import(importId=import_id)
        status = resp["importStatus"]
        print(f"  import {import_id}: {status}", file=sys.stderr)
        if status == "Completed":
            return resp
        if status == "Failed":
            reasons = resp.get("failureReasons") or []
            raise RuntimeError(f"import failed: {reasons or resp}")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"import {import_id} did not complete within {IMPORT_TIMEOUT}s")


def _wait_locale_built(lex, bot_id: str, locale_id: str) -> None:
    deadline = time.time() + BUILD_TIMEOUT
    while time.time() < deadline:
        resp = lex.describe_bot_locale(
            botId=bot_id, botVersion="DRAFT", localeId=locale_id
        )
        status = resp["botLocaleStatus"]
        print(f"  locale {locale_id}: {status}", file=sys.stderr)
        if status == "Built":
            return
        if status == "Failed":
            reasons = resp.get("failureReasons") or []
            raise RuntimeError(f"locale {locale_id} build failed: {reasons or resp}")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(
        f"locale {locale_id} did not finish building within {BUILD_TIMEOUT}s"
    )


def _wait_version_available(lex, bot_id: str, version: str) -> None:
    deadline = time.time() + BUILD_TIMEOUT
    while time.time() < deadline:
        try:
            resp = lex.describe_bot_version(botId=bot_id, botVersion=version)
        except lex.exceptions.ResourceNotFoundException:
            # create_bot_version returns the version number before the version
            # resource is consistently queryable. Tolerate the gap.
            print(f"  version {version}: NotFoundYet", file=sys.stderr)
            time.sleep(POLL_INTERVAL)
            continue
        status = resp["botStatus"]
        print(f"  version {version}: {status}", file=sys.stderr)
        if status == "Available":
            return
        if status == "Failed":
            raise RuntimeError(f"bot version {version} failed: {resp}")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"version {version} not available within {BUILD_TIMEOUT}s")


def _ensure_alias(
    lex,
    bot_id: str,
    alias_name: str,
    bot_version: str,
    locales: list[str],
    description: str | None,
) -> dict[str, Any]:
    locale_settings = {loc: {"enabled": True} for loc in locales}
    # Reuse if it exists.
    paginator = lex.get_paginator("list_bot_aliases")
    for page in paginator.paginate(botId=bot_id):
        for summary in page.get("botAliasSummaries", []):
            if summary["botAliasName"] == alias_name:
                alias_id = summary["botAliasId"]
                print(
                    f"  alias '{alias_name}' exists ({alias_id}); updating to v{bot_version}",
                    file=sys.stderr,
                )
                kwargs: dict[str, Any] = dict(
                    botAliasId=alias_id,
                    botAliasName=alias_name,
                    botId=bot_id,
                    botVersion=bot_version,
                    botAliasLocaleSettings=locale_settings,
                )
                if description:
                    kwargs["description"] = description
                return lex.update_bot_alias(**kwargs)
    print(f"  creating alias '{alias_name}' → v{bot_version}", file=sys.stderr)
    kwargs = dict(
        botAliasName=alias_name,
        botId=bot_id,
        botVersion=bot_version,
        botAliasLocaleSettings=locale_settings,
    )
    if description:
        kwargs["description"] = description
    return lex.create_bot_alias(**kwargs)


def _associate_with_connect(
    connect, instance_id: str, alias_arn: str
) -> None:
    print(
        f"  associating alias {alias_arn} with Connect instance {instance_id}",
        file=sys.stderr,
    )
    connect.associate_bot(InstanceId=instance_id, LexV2Bot={"AliasArn": alias_arn})


def _tag_for_connect(lex, region: str, account_id: str, bot_id: str, alias_id: str) -> None:
    """Stamp the AmazonConnectEnabled tag on the bot and alias.

    The value MUST be ``True`` with a capital T. Connect's admin
    bot-management page (/bots/details/<botId>) does a case-sensitive
    check and returns 403 ("The Conversational AI bot does not have the
    required tag set") for ``true`` or any other casing. The flow
    dropdown / runtime is more lenient, but we standardize on ``True``
    so the bot is also editable in the Connect console.
    """
    bot_arn = f"arn:aws:lex:{region}:{account_id}:bot/{bot_id}"
    alias_arn = f"arn:aws:lex:{region}:{account_id}:bot-alias/{bot_id}/{alias_id}"
    for arn in (bot_arn, alias_arn):
        print(f"  tagging {arn} AmazonConnectEnabled=True", file=sys.stderr)
        lex.tag_resource(resourceARN=arn, tags={"AmazonConnectEnabled": "True"})


# ----- top-level deploy ---------------------------------------------------


def deploy(
    skill: SkillManifest,
    bot_name: str,
    substitutions: dict[str, str],
    region: str,
    bot_role_arn: str,
    connect_instance_id: str | None,
    artifact_dir: Path,
    dry_run: bool,
) -> dict[str, Any]:
    bundle_dir = artifact_dir / "bundle"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)
    print(f"materializing bundle in {bundle_dir}", file=sys.stderr)
    _materialize_bundle(
        skill.template_dir,
        skill.template_bot_dir,
        bot_name,
        substitutions,
        bundle_dir,
    )

    zip_path = artifact_dir / f"{bot_name}.zip"
    print(f"zipping → {zip_path}", file=sys.stderr)
    _zip_bundle(bundle_dir, zip_path)

    if dry_run:
        print("dry-run: skipping all AWS calls", file=sys.stderr)
        return {"bundleDir": str(bundle_dir), "zip": str(zip_path)}

    lex, connect = _import_lex_models(region)

    print("creating upload URL…", file=sys.stderr)
    upload = lex.create_upload_url()
    import_id = upload["importId"]
    print(f"  importId={import_id}", file=sys.stderr)

    print("uploading zip…", file=sys.stderr)
    _upload_zip(upload["uploadUrl"], zip_path)

    print("starting import…", file=sys.stderr)
    lex.start_import(
        importId=import_id,
        mergeStrategy="Overwrite",
        resourceSpecification={
            "botImportSpecification": {
                "botName": bot_name,
                "dataPrivacy": {"childDirected": False},
                "idleSessionTTLInSeconds": 300,
                "roleArn": bot_role_arn,
            }
        },
    )

    import_resp = _wait_import(lex, import_id)
    # The import response carries botName but not botId; resolve via list_bots.
    confirmed_bot_name = (
        import_resp["resourceSpecification"]["botImportSpecification"].get("botName")
        or bot_name
    )
    # list_bots is not a pageable operation in botocore; call it directly with
    # a name filter and walk nextToken manually.
    bot_id = None
    next_token = None
    while True:
        kwargs: dict[str, Any] = {
            "filters": [
                {
                    "name": "BotName",
                    "values": [confirmed_bot_name],
                    "operator": "EQ",
                }
            ]
        }
        if next_token:
            kwargs["nextToken"] = next_token
        resp = lex.list_bots(**kwargs)
        for summary in resp.get("botSummaries", []):
            if summary["botName"] == confirmed_bot_name:
                bot_id = summary["botId"]
                break
        next_token = resp.get("nextToken")
        if bot_id or not next_token:
            break
    if not bot_id:
        raise RuntimeError(f"could not resolve botId for {bot_name} after import")
    print(f"imported bot {bot_name} → botId={bot_id}", file=sys.stderr)

    for locale in skill.locales:
        print(f"building locale {locale}…", file=sys.stderr)
        lex.build_bot_locale(botId=bot_id, botVersion="DRAFT", localeId=locale)
        _wait_locale_built(lex, bot_id, locale)

    print("creating bot version from DRAFT…", file=sys.stderr)
    version_resp = lex.create_bot_version(
        botId=bot_id,
        botVersionLocaleSpecification={
            loc: {"sourceBotVersion": "DRAFT"} for loc in skill.locales
        },
    )
    bot_version = version_resp["botVersion"]
    print(f"  botVersion={bot_version}", file=sys.stderr)
    _wait_version_available(lex, bot_id, bot_version)

    alias_resp = _ensure_alias(
        lex,
        bot_id=bot_id,
        alias_name=skill.alias_name,
        bot_version=bot_version,
        locales=skill.locales,
        description=skill.alias_description,
    )
    alias_id = alias_resp["botAliasId"]
    sts_account = _account_id(region)
    alias_arn = f"arn:aws:lex:{region}:{sts_account}:bot-alias/{bot_id}/{alias_id}"
    print(f"  alias {skill.alias_name} → {alias_arn}", file=sys.stderr)

    # Tag the bot + alias so Connect treats it as a managed conversational
    # AI bot. Required for the admin bot-management page; value is
    # case-sensitive (True, not true).
    _tag_for_connect(lex, region, sts_account, bot_id, alias_id)

    if connect_instance_id:
        _associate_with_connect(connect, connect_instance_id, alias_arn)

    return {
        "botName": bot_name,
        "botId": bot_id,
        "botVersion": bot_version,
        "aliasName": skill.alias_name,
        "aliasId": alias_id,
        "aliasArn": alias_arn,
        "connectInstanceId": connect_instance_id,
        "connectTag": "AmazonConnectEnabled=True",
    }


def _account_id(region: str) -> str:
    import boto3

    return boto3.client("sts", region_name=region).get_caller_identity()["Account"]


# ----- CLI ----------------------------------------------------------------


def _build_substitutions(skill: SkillManifest, args: argparse.Namespace) -> dict[str, str]:
    """Map CLI args to the placeholder keys declared in skill.json."""
    subs: dict[str, str] = {
        "BOT_NAME": args.bot_name,
        "Q_ASSISTANT_ARN": args.q_assistant_arn,
        # Nova Sonic model ARN region must match the bot's deploy region —
        # Lex rejects a cross-region foundation-model ARN at import time.
        "MODEL_REGION": args.region,
    }
    # Validate against skill.json's parameter list. If the manifest ever
    # adds a new placeholder, surface it here instead of crashing mid-import.
    declared = set()
    for spec in skill.parameters.values():
        ph = spec.get("placeholder", "")
        m = re.fullmatch(r"\{\{([A-Z0-9_]+)\}\}", ph)
        if m:
            declared.add(m.group(1))
    missing = declared - subs.keys()
    if missing:
        raise SystemExit(
            f"skill '{skill.name}' declares placeholders this script doesn't know how "
            f"to fill: {sorted(missing)}. Update _build_substitutions()."
        )
    return subs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skill",
        required=True,
        help="Skill folder name under lex_skills/ (e.g., q_in_connect_passthrough).",
    )
    parser.add_argument("--bot-name", required=True, help="Per-tenant bot name.")
    parser.add_argument(
        "--q-assistant-arn",
        required=True,
        help="ARN of the Amazon Q in Connect (Wisdom) assistant to bind to.",
    )
    parser.add_argument(
        "--bot-role-arn",
        help=(
            "IAM role ARN for the Lex bot. Required unless --dry-run. "
            "Typically AWSServiceRoleForLexV2Bots."
        ),
    )
    parser.add_argument(
        "--region", default=os.environ.get("AWS_REGION", "us-east-1")
    )
    parser.add_argument(
        "--connect-instance-id",
        help="If set, associate the resulting alias with this Connect instance.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        help="Where to write the rendered bundle and zip. Defaults to a temp dir.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render and zip the bundle without calling AWS.",
    )
    args = parser.parse_args(argv)

    skill_dir = SKILLS_ROOT / args.skill
    skill = SkillManifest.load(skill_dir)
    print(f"loaded skill: {skill.name}", file=sys.stderr)

    if not args.dry_run and not args.bot_role_arn:
        parser.error("--bot-role-arn is required unless --dry-run is set")

    substitutions = _build_substitutions(skill, args)

    if args.artifact_dir:
        artifact_dir = args.artifact_dir
        artifact_dir.mkdir(parents=True, exist_ok=True)
        result = deploy(
            skill,
            args.bot_name,
            substitutions,
            args.region,
            args.bot_role_arn or "",
            args.connect_instance_id,
            artifact_dir,
            args.dry_run,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="lex-skill-") as tmp:
            result = deploy(
                skill,
                args.bot_name,
                substitutions,
                args.region,
                args.bot_role_arn or "",
                args.connect_instance_id,
                Path(tmp),
                args.dry_run,
            )

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
