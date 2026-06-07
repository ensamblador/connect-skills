"""Refresh ``.kiro/skills/connect-ai-agent-author/system-prompts/``.

Pulls every SYSTEM AI prompt from a known Amazon Connect AI agents
domain and writes one YAML per prompt plus a manifest. The
`connect-ai-agent-author` skill uses these as a read-only base when
generating custom prompts.

The cache is provenance-tracked in ``NOTICE.md`` (next to the YAMLs).
That file does not change here — only the YAMLs and ``_manifest.json``
do.

Defaults target the same domain we pulled from initially:

- assistant id: ``11111111-2222-3333-4444-555555555555``
  (alias ``my-connect-domain``)
- account: ``111122223333``
- region: ``us-west-2``
- profile: ``connect-chat``

Override via env vars or CLI flags. Profile is optional — if unset,
the AWS default credential chain applies.

Run::

    uv run python .kiro/hooks/scripts/refresh_system_prompts.py             # write
    uv run python .kiro/hooks/scripts/refresh_system_prompts.py --dry-run   # preview manifest
    DOMAIN_ID=<other-uuid> uv run python .kiro/hooks/scripts/refresh_system_prompts.py
    uv run python .kiro/hooks/scripts/refresh_system_prompts.py \
        --domain-id <other-uuid> --region us-east-1 --profile other-profile
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# This script lives at ``.kiro/hooks/scripts/`` — three levels under the
# repo root (scripts → hooks → .kiro → repo root).
REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / ".kiro" / "skills" / "connect-ai-agent-author" / "system-prompts"

DEFAULT_DOMAIN_ID = "11111111-2222-3333-4444-555555555555"
DEFAULT_REGION = "us-west-2"
DEFAULT_PROFILE = "connect-chat"


def aws(*args: str, profile: str | None, region: str) -> dict:
    """Run ``aws qconnect <args>`` and return parsed JSON output."""
    cmd = ["aws", "qconnect", *args, "--region", region]
    if profile:
        cmd += ["--profile", profile]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        sys.stderr.write(
            f"\nAWS CLI failed (exit {proc.returncode}):\n"
            f"  command: {' '.join(cmd)}\n"
            f"  stderr:  {proc.stderr.strip()}\n"
        )
        raise SystemExit(proc.returncode or 1)
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def list_system_prompts(domain_id: str, *, profile: str | None, region: str) -> list[dict]:
    """Return a flat list of {aiPromptId, name, ...} for every SYSTEM prompt."""
    out: list[dict] = []
    next_token: str | None = None
    while True:
        args = [
            "list-ai-prompts",
            "--assistant-id", domain_id,
            "--origin", "SYSTEM",
            "--max-results", "50",
        ]
        if next_token:
            args += ["--next-token", next_token]
        page = aws(*args, profile=profile, region=region)
        out.extend(page.get("aiPromptSummaries", []))
        next_token = page.get("nextToken")
        if not next_token:
            break
    return out


def get_prompt(domain_id: str, prompt_id: str, *, profile: str | None, region: str) -> dict:
    return aws(
        "get-ai-prompt",
        "--assistant-id", domain_id,
        "--ai-prompt-id", prompt_id,
        profile=profile, region=region,
    )["aiPrompt"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--domain-id",
        default=os.environ.get("DOMAIN_ID", DEFAULT_DOMAIN_ID),
        help=f"Assistant (domain) UUID. Default: {DEFAULT_DOMAIN_ID}",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", DEFAULT_REGION)),
        help=f"AWS region. Default: {DEFAULT_REGION}",
    )
    parser.add_argument(
        "--profile",
        default=os.environ.get("AWS_PROFILE", DEFAULT_PROFILE),
        help=f"AWS profile (set to empty string to use the default chain). Default: {DEFAULT_PROFILE}",
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

    profile = args.profile or None  # explicit empty string → default credential chain

    sys.stderr.write(
        f"refreshing system prompts from\n"
        f"  domain:  {args.domain_id}\n"
        f"  region:  {args.region}\n"
        f"  profile: {profile or '(default credential chain)'}\n"
        f"  output:  {args.output_dir.relative_to(REPO_ROOT)}\n\n"
    )

    summaries = list_system_prompts(args.domain_id, profile=profile, region=args.region)
    sys.stderr.write(f"  listed {len(summaries)} system prompt(s)\n")

    manifest: list[dict] = []
    yaml_writes: list[tuple[Path, str]] = []
    for s in summaries:
        pid = s["aiPromptId"]
        name = s["name"]
        sys.stderr.write(f"  fetching {name} ({pid})\n")
        detail = get_prompt(args.domain_id, pid, profile=profile, region=args.region)

        yaml_text = detail["templateConfiguration"]["textFullAIPromptEditTemplateConfiguration"]["text"]
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
