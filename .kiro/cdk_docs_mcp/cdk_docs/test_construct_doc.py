"""Unit tests for ``cdk_docs.construct_doc.get_cdk_construct_doc``.

Network is mocked (``cdk_docs.fetch.fetch_page`` is patched) so the tests
are deterministic and offline. They lock in the ConstructDoc contract
(design M2) and the parse-fidelity / error-result requirements:

    - Req 1.5: the requested construct name, the source URL, and the
      property list survive parsing intact.
    - Req 1.6: a page that cannot be retrieved or parsed yields a
      descriptive error *string* (never a raise) that names the requested
      identifier and the reason.

The HTML fixture below is a trimmed copy of the Sphinx structure the real
``aws_cdk.aws_connect/CfnInstance.html`` page uses (a ``dl.class`` with a
constructor signature of ``em.sig-param`` tokens and a ``Parameters``
field list of ``<li><p><strong>name</strong> (<span
class="sphinx_autodoc_typehints-type">Type</span>) – description</p>``).

Run with::

    uv run python -m unittest cdk_docs.test_construct_doc
"""

from __future__ import annotations

import unittest
from unittest import mock

from cdk_docs import construct_doc, fetch


SOURCE_URL = (
    "https://docs.aws.amazon.com/cdk/api/v2/python/"
    "aws_cdk.aws_connect/CfnInstance.html"
)

# Trimmed but structurally faithful CfnInstance page.
SAMPLE_HTML = """
<html><body>
<section id="cfninstance">
<h1>CfnInstance<a class="headerlink" href="#cfninstance">\uf0c1</a></h1>
<dl class="py class">
  <dt class="sig sig-object py" id="aws_cdk.aws_connect.CfnInstance">
    <span class="sig-name descname"><span class="pre">CfnInstance</span></span>
    <span class="sig-paren">(</span>
    <em class="sig-param"><span class="n"><span class="pre">scope</span></span></em>,
    <em class="sig-param"><span class="n"><span class="pre">id</span></span></em>,
    <em class="sig-param"><span class="o"><span class="pre">*</span></span></em>,
    <em class="sig-param"><span class="n"><span class="pre">attributes</span></span></em>,
    <em class="sig-param"><span class="n"><span class="pre">identity_management_type</span></span></em>,
    <em class="sig-param"><span class="n"><span class="pre">directory_id</span></span><span class="o"><span class="pre">=</span></span><span class="default_value"><span class="pre">None</span></span></em>,
    <em class="sig-param"><span class="n"><span class="pre">instance_alias</span></span><span class="o"><span class="pre">=</span></span><span class="default_value"><span class="pre">None</span></span></em>,
    <span class="sig-paren">)</span>
  </dt>
  <dd>
    <p>Bases: <code>CfnResource</code></p>
    <p>A toggle for an individual feature at the instance level.</p>
    <dl class="field-list simple">
      <dt class="field-odd">Parameters</dt>
      <dd class="field-odd"><ul class="simple">
        <li><p><strong>scope</strong> (<span class="sphinx_autodoc_typehints-type"><code><span class="pre">Construct</span></code></span>) \u2013 Scope in which this resource is defined.</p></li>
        <li><p><strong>id</strong> (<span class="sphinx_autodoc_typehints-type"><code><span class="pre">str</span></code></span>) \u2013 Construct identifier for this resource (unique in its scope).</p></li>
        <li><p><strong>attributes</strong> (<span class="sphinx_autodoc_typehints-type"><code><span class="pre">Union</span></code></span>) \u2013 A toggle for an individual feature at the instance level.</p></li>
        <li><p><strong>identity_management_type</strong> (<span class="sphinx_autodoc_typehints-type"><code><span class="pre">str</span></code></span>) \u2013 The identity management type.</p></li>
        <li><p><strong>directory_id</strong> (<span class="sphinx_autodoc_typehints-type"><code><span class="pre">Optional</span></code></span>) \u2013 The identifier for the directory.</p></li>
        <li><p><strong>instance_alias</strong> (<span class="sphinx_autodoc_typehints-type"><code><span class="pre">Optional</span></code></span>) \u2013 The alias of instance.</p></li>
      </ul></dd>
    </dl>
  </dd>
</dl>
<dl class="py attribute">
  <dt id="aws_cdk.aws_connect.CfnInstance.attr_arn">
    <span class="sig-name descname"><span class="pre">attr_arn</span></span>
  </dt>
  <dd><p>The Amazon Resource Name (ARN) of the instance.</p></dd>
</dl>
</section>
</body></html>
"""


class GetConstructDocSuccessTest(unittest.TestCase):
    def setUp(self) -> None:
        self._patch = mock.patch.object(
            fetch, "fetch_page", return_value=SAMPLE_HTML
        )
        self.mock_fetch = self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_returns_construct_doc_dict_with_m2_keys(self) -> None:
        result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", "aws_cdk.aws_connect"
        )
        self.assertIsInstance(result, dict)
        for key in ("construct", "library", "url", "properties", "description", "raw_sections"):
            self.assertIn(key, result)

    def test_preserves_construct_name_verbatim(self) -> None:
        result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", "aws_cdk.aws_connect"
        )
        self.assertEqual(result["construct"], "CfnInstance")
        self.assertEqual(result["library"], "aws_cdk.aws_connect")

    def test_preserves_source_url_verbatim(self) -> None:
        result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", "aws_cdk.aws_connect"
        )
        self.assertEqual(result["url"], SOURCE_URL)
        # The fetched URL is the same canonical per-construct URL.
        self.mock_fetch.assert_called_once_with(SOURCE_URL)

    def test_property_list_non_empty_and_excludes_plumbing(self) -> None:
        result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", "aws_cdk.aws_connect"
        )
        names = [p["name"] for p in result["properties"]]
        self.assertGreater(len(names), 0)
        # scope/id are CDK plumbing, not resource properties.
        self.assertNotIn("scope", names)
        self.assertNotIn("id", names)
        self.assertIn("attributes", names)
        self.assertIn("identity_management_type", names)

    def test_property_records_carry_type_required_description(self) -> None:
        result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", "aws_cdk.aws_connect"
        )
        by_name = {p["name"]: p for p in result["properties"]}
        # required (no default in the signature)
        self.assertTrue(by_name["identity_management_type"]["required"])
        self.assertEqual(by_name["identity_management_type"]["type"], "str")
        self.assertEqual(
            by_name["identity_management_type"]["description"],
            "The identity management type.",
        )
        # optional (has a default in the signature)
        self.assertFalse(by_name["directory_id"]["required"])

    def test_description_skips_bases_line(self) -> None:
        result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", "aws_cdk.aws_connect"
        )
        self.assertIsNotNone(result["description"])
        self.assertFalse(result["description"].startswith("Bases:"))

    def test_raw_sections_is_escape_hatch_dict(self) -> None:
        result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", "aws_cdk.aws_connect"
        )
        self.assertIsInstance(result["raw_sections"], dict)
        self.assertIn("Parameters", result["raw_sections"])

    def test_library_none_searches_all_in_scope_libraries(self) -> None:
        # Library omitted -> first candidate that resolves wins.
        result = construct_doc.get_cdk_construct_doc("CfnInstance")
        self.assertIsInstance(result, dict)
        self.assertIn(result["library"], fetch.LIBRARIES)


class GetConstructDocErrorTest(unittest.TestCase):
    def test_unknown_library_returns_descriptive_error_string(self) -> None:
        result = construct_doc.get_cdk_construct_doc("CfnFoo", "aws_cdk.aws_s3")
        self.assertIsInstance(result, str)
        self.assertIn("CfnFoo", result)
        self.assertIn("aws_cdk.aws_s3", result)

    def test_empty_construct_returns_error_string(self) -> None:
        result = construct_doc.get_cdk_construct_doc("   ")
        self.assertIsInstance(result, str)
        self.assertIn("Could not retrieve", result)

    def test_fetch_failure_returns_error_naming_identifier_and_reason(self) -> None:
        err = fetch.FetchError(SOURCE_URL, "HTTP 404")
        with mock.patch.object(fetch, "fetch_page", side_effect=err):
            result = construct_doc.get_cdk_construct_doc(
                "CfnNope", "aws_cdk.aws_connect"
            )
        self.assertIsInstance(result, str)
        self.assertIn("CfnNope", result)
        self.assertIn("aws_cdk.aws_connect", result)
        self.assertIn("404", result)

    def test_fetch_failure_does_not_raise(self) -> None:
        with mock.patch.object(
            fetch, "fetch_page", side_effect=fetch.FetchError(SOURCE_URL, "boom")
        ):
            try:
                result = construct_doc.get_cdk_construct_doc(
                    "CfnX", "aws_cdk.aws_connect"
                )
            except Exception as exc:  # pragma: no cover - guards the no-raise contract
                self.fail(f"get_cdk_construct_doc raised: {exc}")
        self.assertIsInstance(result, str)

    def test_empty_response_returns_error_string(self) -> None:
        with mock.patch.object(fetch, "fetch_page", return_value=""):
            result = construct_doc.get_cdk_construct_doc(
                "CfnEmpty", "aws_cdk.aws_connect"
            )
        self.assertIsInstance(result, str)
        self.assertIn("CfnEmpty", result)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
