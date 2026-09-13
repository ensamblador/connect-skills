"""Regression tests for response charset decoding.

Feature: connect-iac-cdk, regression: UTF-8 mis-decode in the fetch layer

The CDK reference pages are served from ``docs.aws.amazon.com`` as a bare
``Content-Type: text/html`` with **no** ``charset`` parameter. ``requests``
derives ``response.encoding`` only from that header, so it falls back to
the RFC 2616 default of ISO-8859-1 — even though the body is UTF-8 and
declares so in its own ``<meta charset="utf-8">``, which ``requests`` never
reads.

Reading ``response.text`` under that wrong encoding tears every multi-byte
sequence apart. The en dash (U+2013, ``e2 80 93``) that AWS uses to
separate a parameter name from its description arrives as the three
characters ``â\\x80\\x93``. Because the damage happens before BeautifulSoup
sees the document, no downstream parse can recover it, and it surfaced in
``get_cdk_construct_doc``'s ``raw_sections``.

These tests pin the four behaviours that matter:

  1. a missing charset on UTF-8 bytes still yields real Unicode,
  2. a charset the server *does* declare is honoured, not clobbered,
  3. a genuinely Latin-1 page that says so decodes as Latin-1, and
  4. the fix holds end-to-end through ``fetch_page``.

Real ``requests.Response`` objects are used rather than stubs, so the
tests exercise the actual ``.text`` / ``.apparent_encoding`` machinery that
caused the bug. No network.

Run with (from ``cdk_docs_mcp/``)::

    uv run --with pytest pytest cdk_docs/test_charset_decoding.py
"""

from __future__ import annotations

from unittest import mock

import pytest
import requests
from requests.utils import get_encoding_from_headers

from cdk_docs import fetch


# The exact byte sequence at the heart of the bug: UTF-8 for U+2013.
EN_DASH_UTF8 = b"\xe2\x80\x93"
# What a Latin-1 mis-decode of those bytes produces.
MOJIBAKE = "\u00e2\u0080\u0093"

# A parameter line shaped like the real CDK reference markup.
PARAM_LINE = b"scope (Construct) " + EN_DASH_UTF8 + b" Scope in which this is defined."


def _response(body: bytes, content_type: str | None = None) -> requests.Response:
    """Build a real Response with the given raw body and Content-Type.

    ``encoding`` is seeded from the headers the same way
    ``requests.adapters.HTTPAdapter.build_response`` does, so the fixture
    reproduces production rather than leaving ``encoding`` as ``None``
    (which would let ``.text`` silently fall back to content sniffing and
    hide the very bug under test).
    """
    r = requests.Response()
    r.status_code = 200
    r._content = body
    if content_type is not None:
        r.headers["Content-Type"] = content_type
    r.encoding = get_encoding_from_headers(r.headers)
    r.url = "https://docs.aws.amazon.com/cdk/api/v2/python/x.html"
    return r


class TestDecodedText:
    def test_bare_text_html_really_does_default_to_latin1(self):
        """Guard the premise, so this suite fails loudly if requests changes.

        The whole bug rests on requests resolving a bare ``text/html`` to
        ISO-8859-1. If a future version stops doing that, the fix becomes a
        no-op and this test tells us why.
        """
        r = _response(PARAM_LINE, "text/html")
        assert r.encoding is not None and r.encoding.lower() == "iso-8859-1"
        assert MOJIBAKE in r.text, "premise broken: raw .text was already clean"

    def test_utf8_body_without_declared_charset_is_not_mangled(self):
        """The regression: bare text/html + UTF-8 bytes must still decode."""
        out = fetch.decoded_text(
            _response(b"<html><body>" + PARAM_LINE + b"</body></html>", "text/html")
        )
        assert "\u2013" in out
        assert MOJIBAKE not in out

    def test_declared_utf8_charset_is_honoured(self):
        r = _response(PARAM_LINE, "text/html; charset=utf-8")
        out = fetch.decoded_text(r)
        assert "\u2013" in out
        assert MOJIBAKE not in out

    def test_declared_latin1_charset_is_not_overridden(self):
        """A server that truly means Latin-1 must be believed."""
        # 0xe9 is a lone Latin-1 'e-acute' and is NOT valid standalone UTF-8.
        r = _response(b"caf\xe9", "text/html; charset=iso-8859-1")
        assert fetch.decoded_text(r) == "caf\u00e9"

    def test_charset_detection_is_case_insensitive(self):
        r = _response(PARAM_LINE, "TEXT/HTML; CHARSET=UTF-8")
        assert "\u2013" in fetch.decoded_text(r)

    def test_missing_content_type_header_falls_back(self):
        assert "\u2013" in fetch.decoded_text(_response(PARAM_LINE, None))

    def test_empty_body_does_not_raise(self):
        assert fetch.decoded_text(_response(b"", "text/html")) == ""


class TestFetchPageEndToEnd:
    def test_fetch_page_returns_clean_unicode(self):
        body = b"<html><body>" + PARAM_LINE + b"</body></html>"
        with mock.patch(
            "cdk_docs.fetch.requests.get",
            return_value=_response(body, "text/html"),
        ):
            out = fetch.fetch_page("https://docs.aws.amazon.com/whatever.html")

        assert "\u2013" in out
        assert MOJIBAKE not in out
        assert "Scope in which this is defined." in out

    def test_no_lone_surrogate_or_replacement_chars(self):
        """Decoding must not silently substitute U+FFFD either."""
        body = "properties: \u2013 \u2014 \u2019 \u00e9 \u4e2d".encode("utf-8")
        with mock.patch(
            "cdk_docs.fetch.requests.get",
            return_value=_response(body, "text/html"),
        ):
            out = fetch.fetch_page("https://docs.aws.amazon.com/whatever.html")

        assert "\ufffd" not in out
        for ch in ("\u2013", "\u2014", "\u2019", "\u00e9", "\u4e2d"):
            assert ch in out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
