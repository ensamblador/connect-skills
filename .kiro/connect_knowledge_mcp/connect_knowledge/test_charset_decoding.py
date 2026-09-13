"""Regression tests for response charset decoding in ``page_doc``.

``requests`` derives ``response.encoding`` only from the ``charset``
parameter of the ``Content-Type`` header, and resolves a bare ``text/*``
to the RFC 2616 default of ISO-8859-1. Decoding UTF-8 bytes under that
encoding mangles every multi-byte sequence: an en dash (U+2013,
``e2 80 93``) becomes the three characters ``â\\x80\\x93``.

The sibling ``cdk_docs_mcp`` server hit this for real, because the CDK
reference ``.html`` pages carry no charset. ``page_doc`` fetches ``.md``
sources, which AWS *does* serve with ``charset=utf-8``, so it was correct
by luck rather than by construction. ``_decoded_text`` removes that
dependency on an upstream header we do not control.

These tests pin the behaviour in both directions: a missing charset is
filled in, and a charset the server genuinely declares is obeyed.

Run with (from ``connect_knowledge_mcp/``)::

    uv run --with pytest pytest connect_knowledge/test_charset_decoding.py
"""

from __future__ import annotations

import pytest
import requests
from requests.utils import get_encoding_from_headers

from connect_knowledge import page_doc


EN_DASH_UTF8 = b"\xe2\x80\x93"
MOJIBAKE = "\u00e2\u0080\u0093"
BODY = b"## Properties\n\nTimeout " + EN_DASH_UTF8 + b" max 8 seconds.\n"


def _response(body: bytes, content_type: str | None = None) -> requests.Response:
    """Build a real Response, seeding ``encoding`` the way requests does."""
    r = requests.Response()
    r.status_code = 200
    r._content = body
    if content_type is not None:
        r.headers["Content-Type"] = content_type
    r.encoding = get_encoding_from_headers(r.headers)
    r.url = "https://docs.aws.amazon.com/connect/latest/adminguide/x.md"
    return r


class TestDecodedText:
    def test_bare_text_plain_would_mangle_without_the_guard(self):
        """Guard the premise so the suite explains itself if requests changes."""
        r = _response(BODY, "text/plain")
        assert r.encoding is not None and r.encoding.lower() == "iso-8859-1"
        assert MOJIBAKE in r.text

    def test_missing_charset_is_filled_in(self):
        out = page_doc._decoded_text(_response(BODY, "text/plain"))
        assert "\u2013" in out
        assert MOJIBAKE not in out

    def test_declared_utf8_is_honoured(self):
        out = page_doc._decoded_text(_response(BODY, "text/plain; charset=utf-8"))
        assert "\u2013" in out
        assert MOJIBAKE not in out

    def test_declared_latin1_is_not_overridden(self):
        r = _response(b"caf\xe9", "text/plain; charset=iso-8859-1")
        assert page_doc._decoded_text(r) == "caf\u00e9"

    def test_absent_content_type_falls_back(self):
        assert "\u2013" in page_doc._decoded_text(_response(BODY, None))

    def test_empty_body_does_not_raise(self):
        assert page_doc._decoded_text(_response(b"", "text/plain")) == ""

    def test_wide_range_of_non_ascii_survives(self):
        body = "\u2013 \u2014 \u2019 \u00e9 \u4e2d \U0001f600".encode("utf-8")
        out = page_doc._decoded_text(_response(body, "text/plain"))
        assert "\ufffd" not in out
        for ch in ("\u2013", "\u2014", "\u2019", "\u00e9", "\u4e2d", "\U0001f600"):
            assert ch in out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
