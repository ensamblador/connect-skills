"""Refresh ``.kiro/skills/connect-ai-agent-author/system-prompts/``.

Pulls every SYSTEM AI prompt from an Amazon Connect AI agents domain
(a Q in Connect assistant) and writes one YAML per prompt plus a
manifest. The `connect-ai-agent-author` skill uses these as a
read-only base when generating custom prompts.

The cache is provenance-tracked in ``NOTICE.md`` (next to the YAMLs).
That file does not change here — only the YAMLs and ``_manifest.json``
do.

Credentials and region come from the **ambient environment** only —
this script never selects an AWS profile. Whatever
``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` / ``AWS_SESSION_TOKEN``
(or an attached role) and ``AWS_REGION`` / ``AWS_DEFAULT_REGION`` are in
the environment is what gets used, via the standard boto3 chain.

The domain is resolved by default from ``qconnect:ListAssistants`` — the
first (and typically only) assistant in the account/region is used. If
the account has more than one, the choice is reported to stderr and can
be pinned with ``DOMAIN_ID`` or ``--domain-id``.

Run::

    uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py            # write
    uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py --dry-run  # preview
    DOMAIN_ID=<uuid> uv run --with boto3 python .kiro/scripts/refresh_system_prompts.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# This script lives at ``.kiro/scripts/`` — two levels under the
# repo root (scripts → .kiro → repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / ".kiro" / "skills" / "connect-ai-agent-author" / "system-prompts"


def make_client(region: str | None):
    """Build a qconnect client from the ambient credential chain.

    No profile is ever passed: environment credentials (or an attached
    role) are used as-is.
    """
    session = boto3.session.Session(region_name=region)
    if session.region_name is None:
        raise SystemExit(
            "no AWS region configured — set AWS_REGION (or AWS_DEFAULT_REGION), "
            "or pass --region"
        )
    return session.client("qconnect")


def default_domain_id(client) -> str:
    """Return the domain (assistant) id to use, from ListAssistants."""
    summaries: list[dict] = []
    paginator = client.get_paginator("list_assistants")
    for page in paginator.paginate():
        summaries.extend(page.get("assistantSummaries", []))

    if not summaries:
        raise SystemExit(
            "no Connect AI agents domains (Q in Connect assistants) found in "
            f"region {client.meta.region_name} — set DOMAIN_ID or pass --domain-id"
        )

    chosen = summaries[0]
    if len(summaries) > 1:
        names = ", ".join(f"{s.get('name')} ({s['assistantId']})" for s in summaries)
        sys.stderr.write(
            f"  note: {len(summaries)} domains found ({names});\n"
            f"        using the first one — pin another with --domain-id\n"
        )
    sys.stderr.write(
        f"  resolved domain: {chosen.get('name')} ({chosen['assistantId']})\n"
    )
    return chosen["assistantId"]


def list_system_prompts(client, domain_id: str) -> list[dict]:
    """Return a flat list of {aiPromptId, name, ...} for every SYSTEM prompt."""
    out: list[dict] = []
    paginator = client.get_paginator("list_ai_prompts")
    for page in paginator.paginate(assistantId=domain_id, origin="SYSTEM"):
        out.extend(page.get("aiPromptSummaries", []))
    return out


def get_prompt(client, domain_id: str, prompt_id: str) -> dict:
    return client.get_ai_prompt(assistantId=domain_id, aiPromptId=prompt_id)["aiPrompt"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--domain-id",
        default=os.environ.get("DOMAIN_ID"),
        help="Assistant (domain) UUID. Default: first domain from ListAssistants.",
    )
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region. Default: AWS_REGION / AWS_DEFAULT_REGION from the environment.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List prompts and print the manifest to stdout, but don't write any files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUT_DIR,
        help=f"Output directory (default: {OUT_DIR.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args(argv)

    try:
        client = make_client(args.region)
        sys.stderr.write(
            f"refreshing system prompts\n"
            f"  region:  {client.meta.region_name}\n"
            f"  creds:   ambient environment credential chain (no profile)\n"
            f"  output:  {args.output_dir.relative_to(REPO_ROOT)}\n"
        )

        domain_id = args.domain_id or default_domain_id(client)

        summaries = list_system_prompts(client, domain_id)
        sys.stderr.write(f"  listed {len(summaries)} system prompt(s)\n")

        manifest: list[dict] = []
        yaml_writes: list[tuple[Path, str]] = []
        for s in summaries:
            pid = s["aiPromptId"]
            name = s["name"]
            sys.stderr.write(f"  fetching {name} ({pid})\n")
            detail = get_prompt(client, domain_id, pid)

            yaml_text = detail["templateConfiguration"][
                "textFullAIPromptEditTemplateConfiguration"
            ]["text"]
            yaml_writes.append((args.output_dir / f"{name}.yaml", yaml_text))

            manifest.append({
                "name": name,
                "aiPromptId": pid,
                "type": detail.get("type"),
                "apiFormat": detail.get("apiFormat"),
                "modelId": detail.get("modelId"),
                "templateType": detail.get("templateType"),
                "visibilityStatus": detail.get("visibilityStatus"),
                "origin": detail.get("origin"),
                "status": detail.get("status"),
                "yamlBytes": len(yaml_text),
            })
    except (ClientError, BotoCoreError) as exc:
        sys.stderr.write(f"\nAWS call failed: {exc}\n")
        return 1

    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    if args.dry_run:
        sys.stderr.write("\n--- manifest (dry run) ---\n")
        sys.stdout.write(manifest_text)
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path, text in yaml_writes:
        path.write_text(text, encoding="utf-8")
    (args.output_dir / "_manifest.json").write_text(manifest_text, encoding="utf-8")
    sys.stderr.write(
        f"\nwrote {len(yaml_writes)} YAML file(s) + _manifest.json to "
        f"{args.output_dir.relative_to(REPO_ROOT)}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
