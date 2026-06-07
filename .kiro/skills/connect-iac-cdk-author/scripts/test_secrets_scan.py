"""Unit tests for the no-secrets scanner (task 14.1).

Covers the public :func:`scan_for_secrets` core and its detectors (Req
15.2): AWS access key id, assignment-style secret key / session token, and
the conservative 40-char base64 heuristic — plus the no-false-positive
guarantee on normal code. The hypothesis property test for the universal
invariant (Property 10) lives in task 14.2 and imports this module.

Run: python -m unittest test_secrets_scan  (from this scripts/ folder)
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from secrets_scan import (  # noqa: E402
    Finding,
    SecretsFound,
    contains_secret,
    scan_directory,
    scan_for_secrets,
    scan_text,
)

# A planted FAKE access key id (AKIA + 16 alnum) — not a real credential.
FAKE_ACCESS_KEY_ID = "AKIA" + "IOSFODNN7EXAMPLE"[:16]  # AKIAIOSFODNN7EXAMPL
# A planted FAKE secret access key (exactly 40 base64 chars, mixed classes).
FAKE_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


class AccessKeyIdDetection(unittest.TestCase):
    def test_flags_akia_access_key_id(self):
        findings = scan_text(f"aws_access_key_id = {FAKE_ACCESS_KEY_ID}")
        kinds = {f.kind for f in findings}
        self.assertIn("access_key_id", kinds)

    def test_flags_asia_temporary_key_id(self):
        token = "ASIA" + "ABCDEFGHIJKLMNOP"
        findings = scan_text(f"key: {token}")
        self.assertTrue(any(f.kind == "access_key_id" for f in findings))

    def test_does_not_flag_short_or_lowercase_lookalike(self):
        # Too short, and lowercase — not an access key id shape.
        self.assertEqual(scan_text("AKIAshort"), [])
        self.assertEqual(scan_text("akiaiosfodnn7example"), [])

    def test_does_not_flag_when_embedded_in_longer_alnum_run(self):
        # Bounded match: a 20-char id inside a longer token is not a key id.
        token = "X" + "AKIA" + "ABCDEFGHIJKLMNOP" + "Y"
        self.assertFalse(
            any(f.kind == "access_key_id" for f in scan_text(token))
        )


class SecretKeyDetection(unittest.TestCase):
    def test_flags_assignment_style_secret_key(self):
        for line in (
            'aws_secret_access_key = "abc123notreal"',
            "aws_secret_access_key: abc123notreal",
            'aws-secret-access-key="abc123notreal"',
            "awsSecretAccessKey = abc123notreal",
        ):
            with self.subTest(line=line):
                findings = scan_text(line)
                self.assertTrue(
                    any(f.kind == "secret_access_key" for f in findings),
                    f"expected secret_access_key finding for: {line}",
                )

    def test_flags_bare_40_char_base64_secret(self):
        findings = scan_text(f"const k = '{FAKE_SECRET_KEY}'")
        self.assertTrue(any(f.kind == "secret_access_key" for f in findings))


class SessionTokenDetection(unittest.TestCase):
    def test_flags_assignment_style_session_token(self):
        for line in (
            "aws_session_token = FwoGZXIvYXdzEXAMPLE",
            'aws_session_token: "FwoGZXIvYXdzEXAMPLE"',
            "x-amz-security-token: FwoGZXIvYXdzEXAMPLE",
        ):
            with self.subTest(line=line):
                findings = scan_text(line)
                self.assertTrue(
                    any(f.kind == "session_token" for f in findings),
                    f"expected session_token finding for: {line}",
                )


class NoFalsePositives(unittest.TestCase):
    """Normal generated artifacts must scan clean (Req 15.2 without noise)."""

    def test_normal_python_code_is_clean(self):
        code = (
            "import os\n"
            "account = os.getenv('CDK_DEFAULT_ACCOUNT')\n"
            "region = os.getenv('CDK_DEFAULT_REGION')\n"
            "def resolve(resource_type, existing_id):\n"
            "    return existing_id or None\n"
        )
        self.assertEqual(scan_text(code), [])

    def test_sha256_hex_digest_is_not_flagged(self):
        # 64-char hex (sha256) is not a 40-char base64 secret.
        digest = "sha256:" + "a" * 16
        self.assertEqual(scan_text(digest), [])

    def test_single_class_40_char_run_is_not_flagged(self):
        # 40 lowercase chars — no mixed entropy, not flagged.
        slug = "a" * 40
        self.assertFalse(any(f.kind == "secret_access_key" for f in scan_text(slug)))

    def test_arn_and_account_placeholder_are_clean(self):
        text = "arn:aws:connect:us-east-1:111122223333:instance/inst-1"
        self.assertEqual(scan_text(text), [])


class DispatchAndGate(unittest.TestCase):
    def test_scan_for_secrets_on_raw_text(self):
        self.assertTrue(contains_secret(f"key = {FAKE_ACCESS_KEY_ID}"))
        self.assertFalse(contains_secret("just some clean prose"))

    def test_scan_for_secrets_on_file_and_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "clean.py").write_text("x = 1\n", encoding="utf-8")
            (root / "leak.txt").write_text(
                f"aws_secret_access_key = {FAKE_SECRET_KEY}\n", encoding="utf-8"
            )
            # File scan
            file_findings = scan_for_secrets(root / "leak.txt")
            self.assertTrue(file_findings)
            self.assertEqual(file_findings[0].path, str(root / "leak.txt"))
            # Directory scan finds the leak and ignores the clean file
            dir_findings = scan_directory(root)
            self.assertTrue(dir_findings)
            self.assertTrue(all(f.path.endswith("leak.txt") for f in dir_findings))

    def test_raise_on_find_raises_secrets_found(self):
        with self.assertRaises(SecretsFound) as ctx:
            scan_for_secrets(f"key = {FAKE_ACCESS_KEY_ID}", raise_on_find=True)
        self.assertTrue(ctx.exception.findings)

    def test_finding_describe_is_readable(self):
        f = Finding("access_key_id", FAKE_ACCESS_KEY_ID, path="/tmp/x.py", line=3)
        self.assertIn("/tmp/x.py:3", f.describe())
        self.assertIn("access_key_id", f.describe())

    def test_planted_key_then_clean_scaffold(self):
        # Planted fake key is flagged; a representative scaffold snippet is not.
        self.assertTrue(contains_secret(f"AWS_KEY={FAKE_ACCESS_KEY_ID}"))
        scaffold_snippet = (
            'app = cdk.App()\n'
            'env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"),\n'
            '                    region=os.getenv("CDK_DEFAULT_REGION"))\n'
        )
        self.assertEqual(scan_text(scaffold_snippet), [])


if __name__ == "__main__":
    unittest.main()
