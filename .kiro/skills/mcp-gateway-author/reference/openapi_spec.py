"""
REFERENCE helper (adapt per project) — load an authored OpenAPI spec and
render it for the AgentCore gateway's inline OpenAPI target.

Flow ("render at synth with Fn.sub"):
  1. apis/openapi/openapi.yaml is the authored, rich spec. Its servers[0].url
     is a TEMPLATE: https://${ApiId}.execute-api.${AWS::Region}.amazonaws.com/${Stage}
  2. At synth, parse the YAML and re-serialize to a compact JSON string (the
     inline_payload is a single string; JSON is a valid OpenAPI doc and avoids
     YAML-in-string quoting pitfalls). Keep the ${...} markers intact.
  3. The gateway construct wraps the string in Fn.sub so ${ApiId}/${Stage}
     resolve at deploy time to the REAL deployed API; ${AWS::Region} is a CFN
     pseudo-parameter.

Requires PyYAML in the project requirements.
"""

from __future__ import annotations

import json
import os

import yaml

SPEC_PATH = os.path.join(os.path.dirname(__file__), "openapi", "openapi.yaml")

SERVER_URL_TEMPLATE = (
    "https://${ApiId}.execute-api.${AWS::Region}.amazonaws.com/${Stage}"
)


def load_spec() -> dict:
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def render_spec_json() -> str:
    """Authored spec as a compact JSON string with the server URL set to the
    Fn::Sub template (markers intact)."""
    spec = load_spec()
    spec["servers"] = [
        {"url": SERVER_URL_TEMPLATE, "description": "Deployed API Gateway endpoint"}
    ]
    return json.dumps(spec, separators=(",", ":"))


def operation_summaries() -> list[dict]:
    """List (path, method, operationId, summary) for every operation — handy
    for building native-target tool filters/overrides if needed."""
    spec = load_spec()
    out: list[dict] = []
    for path, methods in spec.get("paths", {}).items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            out.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "operationId": op.get("operationId"),
                    "summary": op.get("summary"),
                }
            )
    return out
