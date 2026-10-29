"""Unit tests for ``cdk_docs.search``.

Network and Node are mocked so the tests are deterministic and offline.
Two layers are covered:

* ``docs_index_search``, the AWS docs search proxy fallback, whose output
  format matches ``connect_knowledge.docs.aws_search``::

      Title: <title>
      URL: <url>?lang=python
      Snippet: <summary or suggestionBody>

  blocks joined by ``\\n---\\n``, with the ``Error searching … : …`` /
  ``No … results found for: <query>`` string conventions.
* ``cdk_search``, which asks Pagefind first (``pagefind.run_pagefind`` is
  mocked) and falls back to the docs index with a ``Note:`` line when
  Pagefind is unavailable.

Run with::

    uv run python -m unittest cdk_docs.test_search
"""

from __future__ import annotations

import unittest
from unittest import mock

import requests

from cdk_docs import pagefind, search


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
    "https://docs.aws.amazon.com/cdk/api/v2/docs/"
    "aws-cdk-lib.aws_connect.CfnInstance.html"
)
NON_CDK_URL = "https://docs.aws.amazon.com/connect/latest/adminguide/foo.html"


class DocsIndexSearchFormatTest(unittest.TestCase):
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
            result = search.docs_index_search("instance")

        blocks = result.split("\n---\n")
        self.assertEqual(len(blocks), 2)
        self.assertEqual(
            blocks[0],
            "Title: CfnInstance\n"
            f"URL: {CDK_URL}?lang=python\n"
            "Snippet: The instance construct.",
        )

    def test_falls_back_to_suggestion_body_when_no_summary(self) -> None:
        suggestions = [_suggestion("CfnBot", CDK_URL, body="raw body text")]
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response(suggestions)
        ):
            result = search.docs_index_search("bot")
        self.assertIn("Snippet: raw body text", result)

    def test_filters_to_cdk_reference_pages_only(self) -> None:
        suggestions = [
            _suggestion("Admin guide page", NON_CDK_URL, summary="not cdk"),
            _suggestion("CfnInstance", CDK_URL, summary="cdk"),
        ]
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response(suggestions)
        ):
            result = search.docs_index_search("instance")
        self.assertIn(CDK_URL, result)
        self.assertNotIn(NON_CDK_URL, result)
        # Only the single CDK hit survives -> no separator.
        self.assertNotIn("\n---\n", result)

    def test_module_filter_applies_to_url_segment(self) -> None:
        sso = CDK_URL.replace("aws_connect", "aws_sso")
        suggestions = [
            _suggestion("CfnInstance", sso, summary="sso"),
            _suggestion("CfnInstance", CDK_URL, summary="connect"),
        ]
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response(suggestions)
        ):
            result = search.docs_index_search("instance", module="aws-connect")
        self.assertIn(CDK_URL, result)
        self.assertNotIn(sso, result)

    def test_limit_caps_returned_cdk_hits(self) -> None:
        suggestions = [
            _suggestion(f"Cfn{i}", f"{CDK_URL}?n={i}", summary=str(i))
            for i in range(5)
        ]
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response(suggestions)
        ):
            result = search.docs_index_search("x", limit=2)
        self.assertEqual(len(result.split("\n---\n")), 2)
        # An existing query string gets ``&lang=python``, not a second ``?``.
        self.assertIn(f"{CDK_URL}?n=0&lang=python", result)

    def test_no_results_message_echoes_query(self) -> None:
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response([])
        ):
            result = search.docs_index_search("nomatch")
        self.assertEqual(result, "No CDK documentation results found for: nomatch")

    def test_no_cdk_results_when_only_non_cdk_hits(self) -> None:
        suggestions = [_suggestion("Admin", NON_CDK_URL, summary="x")]
        with mock.patch.object(
            search.requests, "post", return_value=_ok_response(suggestions)
        ):
            result = search.docs_index_search("alias")
        self.assertEqual(result, "No CDK documentation results found for: alias")

    def test_request_exception_returns_error_string(self) -> None:
        with mock.patch.object(
            search.requests,
            "post",
            side_effect=requests.exceptions.ConnectionError("boom"),
        ):
            result = search.docs_index_search("instance")
        self.assertTrue(result.startswith("Error searching CDK docs: "))

    def test_non_retryable_http_error_returns_error_string(self) -> None:
        err_resp = mock.Mock()
        err_resp.status_code = 404
        http_error = requests.exceptions.HTTPError(response=err_resp)
        resp = mock.Mock()
        resp.raise_for_status.side_effect = http_error
        with mock.patch.object(search.requests, "post", return_value=resp):
            result = search.docs_index_search("instance")
        self.assertTrue(result.startswith("Error searching CDK docs: "))


def _pf_result(title: str, label: str, url: str, excerpt: str) -> dict:
    return {
        "title": title,
        "kind_label": label,
        "url": url,
        "excerpt": excerpt,
        "filters": {},
    }


def _pf_reply(results: list[dict], unknown: dict | None = None) -> dict:
    return {"total": len(results), "results": results, "unknownFilters": unknown or {}}


class CdkSearchPagefindTest(unittest.TestCase):
    def test_formats_pagefind_hits(self) -> None:
        url = CDK_URL.replace("CfnInstance", "CfnBot").replace("aws_connect", "aws_lex")
        excerpt = (
            "CfnBot L1 construct Specifies an Amazon Lex conversational bot. "
            "CloudFormationAWS::Lex::BotSourceType last changed Example ts// code"
        )
        reply = _pf_reply([_pf_result("CfnBot", "L1 construct", url, excerpt)])
        with mock.patch.object(search.pagefind, "run_pagefind", return_value=reply):
            result = search.cdk_search("bot")
        self.assertEqual(
            result,
            "Title: CfnBot (L1 construct)\n"
            f"URL: {url}?lang=python\n"
            "Snippet: Specifies an Amazon Lex conversational bot.",
        )

    def test_passes_normalized_filters(self) -> None:
        with mock.patch.object(
            search.pagefind, "run_pagefind", return_value=_pf_reply([])
        ) as run:
            search.cdk_search("flow", limit=4, module="aws_cdk.aws_connect", kind=" Construct ")
        run.assert_called_once_with("flow", limit=4, module="aws-connect", kind="construct")

    def test_unknown_filter_returns_error_with_close_matches(self) -> None:
        unknown = {"module": {"value": "aws-conect", "known": ["aws-connect", "aws-lex", "aws-s3"]}}
        with mock.patch.object(
            search.pagefind, "run_pagefind", return_value=_pf_reply([], unknown)
        ):
            result = search.cdk_search("flow", module="aws-conect")
        self.assertTrue(result.startswith("Error searching CDK docs: unknown module 'aws-conect'"))
        self.assertIn("aws-connect", result)

    def test_no_results_names_the_filters(self) -> None:
        with mock.patch.object(
            search.pagefind, "run_pagefind", return_value=_pf_reply([])
        ):
            result = search.cdk_search("nomatch", module="aws-lex", kind="enum")
        self.assertEqual(
            result,
            "No CDK documentation results found for: nomatch (module=aws-lex, kind=enum)",
        )

    def test_falls_back_to_docs_index_with_a_note(self) -> None:
        suggestions = [_suggestion("CfnInstance", CDK_URL, summary="cdk")]
        with mock.patch.object(
            search.pagefind,
            "run_pagefind",
            side_effect=pagefind.PagefindUnavailable("the wasmtime package is not installed"),
        ), mock.patch.object(search.requests, "post", return_value=_ok_response(suggestions)):
            result = search.cdk_search("instance", kind="construct")
            expected_body = search.docs_index_search("instance")
        note, _, body = result.partition("\n\n")
        self.assertTrue(note.startswith("Note: CDK site search unavailable (the wasmtime package is not installed)."))
        self.assertIn("ignores the kind filter", note)
        # After the note, the reply is exactly the docs-index result.
        self.assertEqual(body, expected_body)
        self.assertIn(f"URL: {CDK_URL}?lang=python", body)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
