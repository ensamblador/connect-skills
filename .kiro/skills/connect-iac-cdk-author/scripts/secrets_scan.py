"""No-secrets scanner — the reusable core of the security baseline (C9).

Design references: design.md C9 (Security / credential handling), Property
10 (No-secrets invariant). Requirements: 15.2 (no generated artifact
contains AWS access keys, secret keys, or session tokens).

This module is a *pure, importable* scanner. The single public entry point
:func:`scan_for_secrets` accepts either a path (file or directory) or a raw
text string and returns a list of :class:`Finding` records — one per match
— so the same function can serve two callers:

* as a **gate** in the deploy/scaffold workflow (any finding fails the
  gate), and
* as the engine the **property test** (task 14.2, Property 10) drives with
  >=100 generated artifacts.

The scanner is deliberately free of I/O beyond reading the files it is
pointed at, performs no network or AWS calls, and is deterministic: the
same input always yields the same findings.

What counts as a secret (Req 15.2):

* **AWS access key id** — ``AKIA``/``ASIA``/``AGPA``/``AIDA``/``AROA``/
  ``AIPA``/``ANPA``/``ANVA``/``ASCA`` followed by 16 uppercase-alnum
  characters (the canonical 20-char access key id shape).
* **Secret access key** — a value assigned to an ``aws_secret_access_key``
  (or ``aws-secret-access-key`` / ``awsSecretAccessKey``) key, OR a bare
  40-char base64-ish secret heuristic when it is clearly a credential
  literal.
* **Session token** — a value assigned to an ``aws_session_token`` (or its
  hyphen/camel variants), OR an explicit ``x-amz-security-token`` header.

Robustness vs. false positives: the assignment-style patterns
(``aws_secret_access_key = "..."``) are the high-confidence signals and
fire on any non-empty assigned value. The bare 40-char base64 heuristic is
intentionally conservative — it only fires on isolated tokens (bounded by
non-base64 characters) that contain a mix of character classes, so normal
code identifiers, sha256 hex digests, base64-encoded JSON, and prose do not
trip it.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Pattern, Union

__all__ = [
    "Finding",
    "scan_text",
    "scan_file",
    "scan_directory",
    "scan_for_secrets",
    "contains_secret",
    "SecretsFound",
    "DEFAULT_SKIP_DIRS",
    "DEFAULT_SCAN_SUFFIXES",
]


# --------------------------------------------------------------------------- #
# Finding model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Finding:
    """One detected secret.

    ``kind``    -- which detector fired ("access_key_id",
                   "secret_access_key", "session_token").
    ``match``   -- the offending substring (the value, redacted-safe to
                   surface because it identifies the leak the operator must
                   remove; callers that must not echo it can read ``kind`` /
                   ``line`` / ``path`` only).
    ``path``    -- the file the match was found in, or ``None`` for a raw
                   text scan.
    ``line``    -- 1-based line number of the match (0 when unknown).
    """

    kind: str
    match: str
    path: Optional[str] = None
    line: int = 0

    def describe(self) -> str:
        loc = self.path or "<text>"
        where = f"{loc}:{self.line}" if self.line else loc
        return f"{where}: {self.kind}"


class SecretsFound(Exception):
    """Raised by :func:`scan_for_secrets` when ``raise_on_find=True``.

    Carries the findings so a gate can report each leak and abort.
    """

    def __init__(self, findings: List[Finding]):
        self.findings = findings
        joined = "; ".join(f.describe() for f in findings)
        super().__init__(f"secret material detected ({len(findings)}): {joined}")


# --------------------------------------------------------------------------- #
# Detection patterns
# --------------------------------------------------------------------------- #
# AWS access key id: a known 4-letter prefix + 16 uppercase-alnum chars,
# bounded so it is not a substring of a longer alnum run. The prefix set is
# the documented set of unique AWS key-id prefixes (AKIA long-term, ASIA
# temporary/STS, AROA role, etc.).
_ACCESS_KEY_ID_RE: Pattern[str] = re.compile(
    r"(?<![A-Z0-9])((?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASCA)[A-Z0-9]{16})(?![A-Z0-9])"
)

# Assignment-style secret access key: a key named aws_secret_access_key (or
# hyphen / camelCase variants) assigned a non-empty quoted-or-bare value.
# This is the high-confidence signal and intentionally fires on any value.
_SECRET_KEY_ASSIGN_RE: Pattern[str] = re.compile(
    r"""(?ix)
    \b
    aws[_\-]?secret[_\-]?access[_\-]?key   # the key name, any separator/case
    \b
    \s* [:=] \s*                            # assignment ( = or : )
    (['"]?)                                  # optional opening quote
    (?P<value>[^\s'"]{1,})                  # the value (non-empty)
    \1                                       # matching closing quote
    """
)

# Assignment-style session token: aws_session_token / security token.
_SESSION_TOKEN_ASSIGN_RE: Pattern[str] = re.compile(
    r"""(?ix)
    \b
    (?: aws[_\-]?session[_\-]?token         # aws_session_token
      | x[_\-]?amz[_\-]?security[_\-]?token  # x-amz-security-token header
      | aws[_\-]?security[_\-]?token )
    \b
    \s* [:=] \s*
    (['"]?)
    (?P<value>[^\s'"]{1,})
    \1
    """
)

# Bare 40-char base64-ish secret heuristic. AWS secret access keys are 40
# characters from the base64 alphabet ([A-Za-z0-9/+]). To avoid false
# positives on sha256 hex (all hex, 64 chars), normal identifiers, and
# base64-encoded blobs, we require EXACTLY 40 base64 chars bounded by
# non-base64 delimiters AND a mix of character classes (lower, upper, digit)
# — a real secret key is high-entropy and mixes classes, whereas most
# accidental 40-char runs (hex digests, slugs) do not.
_BASE64_SECRET_RE: Pattern[str] = re.compile(
    r"(?<![A-Za-z0-9/+=])([A-Za-z0-9/+]{40})(?![A-Za-z0-9/+=])"
)


def _looks_like_secret_value(token: str) -> bool:
    """Heuristic: does a 40-char base64 token look like a real secret key?

    A genuine AWS secret access key mixes lowercase, uppercase, and digits
    (high entropy). We require all three classes to be present so that
    single-class runs (e.g. a 40-char lowercase slug or an all-hex-looking
    string that happens to be 40 chars) are not flagged.
    """
    if len(token) != 40:
        return False
    has_lower = any(c.islower() for c in token)
    has_upper = any(c.isupper() for c in token)
    has_digit = any(c.isdigit() for c in token)
    return has_lower and has_upper and has_digit


# --------------------------------------------------------------------------- #
# Text scanning (the pure core)
# --------------------------------------------------------------------------- #
def scan_text(text: str, *, path: Optional[str] = None) -> List[Finding]:
    """Scan a raw string for AWS secret material (Req 15.2).

    Pure and deterministic: no I/O, no AWS calls. Returns every match as a
    :class:`Finding`, with 1-based line numbers when the match can be
    located on a line.

    Args:
        text: the artifact content to scan.
        path: optional source path to record on each finding (for
            directory walks); ``None`` for a bare text scan.

    Returns:
        A list of findings (empty when the text is clean).
    """
    findings: List[Finding] = []

    # Pre-compute line start offsets so a match offset maps to a line number
    # without rescanning the whole string each time.
    line_starts = [0]
    for idx, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(idx + 1)

    def _line_of(offset: int) -> int:
        # line_starts is sorted ascending; find the rightmost start <= offset.
        return bisect.bisect_right(line_starts, offset)

    for m in _ACCESS_KEY_ID_RE.finditer(text):
        findings.append(
            Finding("access_key_id", m.group(1), path=path, line=_line_of(m.start(1)))
        )

    for m in _SECRET_KEY_ASSIGN_RE.finditer(text):
        value = m.group("value")
        findings.append(
            Finding(
                "secret_access_key", value, path=path, line=_line_of(m.start("value"))
            )
        )

    for m in _SESSION_TOKEN_ASSIGN_RE.finditer(text):
        value = m.group("value")
        findings.append(
            Finding("session_token", value, path=path, line=_line_of(m.start("value")))
        )

    # Bare base64 secret heuristic — only add when not already covered by an
    # assignment match on the same span, and only when it looks high-entropy.
    already = {(f.match) for f in findings}
    for m in _BASE64_SECRET_RE.finditer(text):
        token = m.group(1)
        if token in already:
            continue
        if _looks_like_secret_value(token):
            findings.append(
                Finding(
                    "secret_access_key", token, path=path, line=_line_of(m.start(1))
                )
            )

    return findings


# --------------------------------------------------------------------------- #
# File / directory scanning
# --------------------------------------------------------------------------- #
# Directories never worth scanning (caches, vendored deps, VCS, synth out).
DEFAULT_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".hypothesis",
        ".mypy_cache",
        "cdk.out",
        "dist",
        "build",
        ".ruff_cache",
    }
)

# Text-like artifact suffixes the capability generates. ``None`` for the
# suffix filter means "scan every file"; this default keeps directory walks
# focused on the artifacts Req 15.2 enumerates (code, config, steering,
# SKILL.md, OpenAPI schema, spec) and skips binaries.
DEFAULT_SCAN_SUFFIXES: frozenset[str] = frozenset(
    {
        ".py",
        ".json",
        ".jsonc",
        ".yaml",
        ".yml",
        ".toml",
        ".md",
        ".txt",
        ".cfg",
        ".ini",
        ".env",
        ".sh",
        ".ts",
        ".js",
        ".mmd",
    }
)


def scan_file(path: Union[str, Path]) -> List[Finding]:
    """Scan a single file for secret material.

    Binary / unreadable files are skipped (returns no findings) rather than
    raising, so a directory walk over a mixed tree never crashes on a stray
    binary.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return scan_text(text, path=str(p))


def _iter_files(
    root: Path,
    *,
    skip_dirs: frozenset[str],
    suffixes: Optional[frozenset[str]],
) -> Iterator[Path]:
    for entry in sorted(root.rglob("*")):
        if not entry.is_file():
            continue
        # Skip anything under a skipped directory.
        if any(part in skip_dirs for part in entry.parts):
            continue
        if suffixes is not None and entry.suffix.lower() not in suffixes:
            continue
        yield entry


def scan_directory(
    path: Union[str, Path],
    *,
    skip_dirs: frozenset[str] = DEFAULT_SKIP_DIRS,
    suffixes: Optional[frozenset[str]] = DEFAULT_SCAN_SUFFIXES,
) -> List[Finding]:
    """Walk a directory tree and scan every eligible text artifact.

    Args:
        path: the directory root to walk.
        skip_dirs: directory names pruned from the walk (caches, VCS, etc.).
        suffixes: file suffixes to scan; pass ``None`` to scan every file
            regardless of extension.

    Returns:
        All findings across the tree (empty when clean), ordered by file.
    """
    root = Path(path)
    findings: List[Finding] = []
    for file_path in _iter_files(root, skip_dirs=skip_dirs, suffixes=suffixes):
        findings.extend(scan_file(file_path))
    return findings


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def scan_for_secrets(
    path_or_text: Union[str, Path],
    *,
    raise_on_find: bool = False,
    skip_dirs: frozenset[str] = DEFAULT_SKIP_DIRS,
    suffixes: Optional[frozenset[str]] = DEFAULT_SCAN_SUFFIXES,
) -> List[Finding]:
    """Scan a path (file or directory) or a raw text string for AWS secrets.

    This is the reusable core (Req 15.2 / Property 10). It is a pure
    function of its input: pass it a :class:`pathlib.Path`, a string that
    names an existing file or directory, or any other string (treated as raw
    artifact text). It returns the list of :class:`Finding` records.

    Dispatch rule:

    * a :class:`~pathlib.Path`, or a ``str`` that resolves to an existing
      file or directory, is scanned as a filesystem artifact;
    * any other ``str`` is scanned as raw text.

    Args:
        path_or_text: a path (file/dir) or raw artifact text.
        raise_on_find: when ``True``, raise :class:`SecretsFound` if any
            secret is detected (useful as a hard gate); when ``False``
            (default) just return the findings.
        skip_dirs / suffixes: forwarded to :func:`scan_directory` for the
            directory case.

    Returns:
        The list of findings (empty when clean).

    Raises:
        SecretsFound: only when ``raise_on_find=True`` and findings exist.
    """
    findings: List[Finding]

    if isinstance(path_or_text, Path):
        if path_or_text.is_dir():
            findings = scan_directory(
                path_or_text, skip_dirs=skip_dirs, suffixes=suffixes
            )
        else:
            findings = scan_file(path_or_text)
    else:
        # str: decide path vs. raw text. Only treat it as a path when it
        # actually points at something on disk; otherwise it is content.
        as_path: Optional[Path] = None
        # A short string with no newlines might be a path; guard the
        # filesystem probe so huge / multiline artifacts never hit the FS.
        if "\n" not in path_or_text and len(path_or_text) < 4096:
            try:
                candidate = Path(path_or_text)
                if candidate.exists():
                    as_path = candidate
            except (OSError, ValueError):
                as_path = None

        if as_path is not None:
            if as_path.is_dir():
                findings = scan_directory(
                    as_path, skip_dirs=skip_dirs, suffixes=suffixes
                )
            else:
                findings = scan_file(as_path)
        else:
            findings = scan_text(path_or_text)

    if raise_on_find and findings:
        raise SecretsFound(findings)
    return findings


def contains_secret(path_or_text: Union[str, Path]) -> bool:
    """Convenience boolean: ``True`` iff any secret material is present."""
    return bool(scan_for_secrets(path_or_text))


# --------------------------------------------------------------------------- #
# CLI — `python secrets_scan.py <path> [<path> ...]`
# --------------------------------------------------------------------------- #
def _main(argv: Optional[Iterable[str]] = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description=(
            "Scan files/directories for AWS access keys, secret keys, or "
            "session tokens (Req 15.2 no-secrets gate)."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Files or directories to scan (e.g. a generated CDK project).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    all_findings: List[Finding] = []
    for target in args.paths:
        all_findings.extend(scan_for_secrets(target))

    if all_findings:
        print(f"FAIL: {len(all_findings)} secret(s) detected:", file=sys.stderr)
        for f in all_findings:
            print(f"  - {f.describe()}", file=sys.stderr)
        return 1

    print("OK: no AWS secret material detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
