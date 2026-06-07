"""Unit tests for ``cdk_docs.search.cdk_search``.

Network is mocked so the tests are deterministic and offline. They lock
in the contract that matters for task 1.8 (MCP/CLI parity) and the design
requirement that the output is *identical in format* to
``connect_knowledge.docs.aws_search``:

    Title: <title>
    URL: <url>
    Snippet: <summary or suggestionBody>

blocks joined by ``\\n---\\n``, with the ``Error searching … : …`` /
``No … results found for: <query>`` string conventions.

Run with::

    uv run python -m unittest cdk_docs.test_search
"""

from __future__ import annotations

import unittest
from unittest import mock

import requests

from cdk_docs import search


def _suggestion(title: str, link: str, summary: str = "", body: str = "") -> dict:
    excerpt: dict = {"title": title, "link": link}
    if summary:
        excerpt["summary"] = summary
    if body:
        excerpt["suggestionBody"] = body
    return {"textExcerptSuggestion": excerpt}


def _ok_response(suggestions: list[dict]) -> mock.Mock:
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"suggestions": suggestions}
    return resp


CDK_URL = (
    "https://docs.aws.amazon.com/cdk/api/v2/python/"
    "aws_cdk.aws_connect/CfnInstance.html"
)
NON_CDK_URL = "https://docs.aws.amazon.com/connect/latest/adminguide/foo.html"


class CdkSearchFormatTest(unittest.TestCase):
    def test_formats_results_as_title_url_snippet_blocks(self) -> None:
        suggestions = [
            _suggestion("CfnInstance", CDK_URL, summary="The instance construct."),
            _suggestion(
                "CfnContactFlow",
                CDK_URL.replace("CfnInstance", "CfnContactFlow"),
                summary="The contact flow construct.",
            ),
        ]
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response(suggestions)
        ):
            result = search.cdk_search("instance")

        blocks = result.split("\n---\n")
        self.assertEqual(len(blocks), 2)
        self.assertEqual(
            blocks[0],
            "Title: CfnInstance\n"
            f"URL: {CDK_URL}\n"
            "Snippet: The instance construct.",
        )

    def test_falls_back_to_suggestion_body_when_no_summary(self) -> None:
        suggestions = [_suggestion("CfnBot", CDK_URL, body="raw body text")]
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response(suggestions)
        ):
            result = search.cdk_search("bot")
        self.assertIn("Snippet: raw body text", result)

    def test_filters_to_cdk_reference_pages_only(self) -> None:
        suggestions = [
            _suggestion("Admin guide page", NON_CDK_URL, summary="not cdk"),
            _suggestion("CfnInstance", CDK_URL, summary="cdk"),
        ]
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response(suggestions)
        ):
            result = search.cdk_search("instance")
        self.assertIn(CDK_URL, result)
        self.assertNotIn(NON_CDK_URL, result)
        # Only the single CDK hit survives -> no separator.
        self.assertNotIn("\n---\n", result)

    def test_limit_caps_returned_cdk_hits(self) -> None:
        suggestions = [
            _suggestion(f"Cfn{i}", f"{CDK_URL}?n={i}", summary=str(i))
            for i in range(5)
        ]
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response(suggestions)
        ):
            result = search.cdk_search("x", limit=2)
        self.assertEqual(len(result.split("\n---\n")), 2)

    def test_no_results_message_echoes_query(self) -> None:
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response([])
        ):
            result = search.cdk_search("nomatch")
        self.assertEqual(result, "No CDK documentation results found for: nomatch")

    def test_no_cdk_results_when_only_non_cdk_hits(self) -> None:
        suggestions = [_suggestion("Admin", NON_CDK_URL, summary="x")]
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response(suggestions)
        ):
            result = search.cdk_search("alias")
        self.assertEqual(result, "No CDK documentation results found for: alias")

    def test_request_exception_returns_error_string(self) -> None:
        with mock.patch.object(
            search.requests,
            "post",
            side_effect=requests.exceptions.ConnectionError("boom"),
        ):
            result = search.cdk_search("instance")
        self.assertTrue(result.startswith("Error searching CDK docs: "))

    def test_non_retryable_http_error_returns_error_string(self) -> None:
        err_resp = mock.Mock()
        err_resp.status_code = 404
        http_error = requests.exceptions.HTTPError(response=err_resp)
        resp = mock.Mock()
        resp.raise_for_status.side_effect = http_error
        with mock.patch.object(search.requests, "post", return_value=resp):
            result = search.cdk_search("instance")
        self.assertTrue(result.startswith("Error searching CDK docs: "))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
