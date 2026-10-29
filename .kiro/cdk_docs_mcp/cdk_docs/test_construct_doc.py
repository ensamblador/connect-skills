"""Unit tests for ``cdk_docs.construct_doc.get_cdk_construct_doc``.

Network is mocked (``cdk_docs.fetch.fetch_page`` is patched) so the tests
are deterministic and offline. They lock in the ConstructDoc contract
(design M2) and the parse-fidelity / error-result requirements:

    - Req 1.5: the requested construct name, the source URL, and the
      property list survive parsing intact.
    - Req 1.6: a page that cannot be retrieved or parsed yields a
      descriptive error *string* (never a raise) that names the requested
      identifier and the reason.

The HTML fixture below is a trimmed copy of the VitePress structure the
real ``aws-cdk-lib.aws_connect.CfnInstance.html`` page uses: an ``<h1>``
and lead paragraph, an Initializer section, then Construct Props,
Properties and Methods sections of ``.member-row`` entries. Each row
renders one ``<span class="lang-variant" data-lang="...">`` per language.
The fixture keeps the TypeScript variant beside the Python one so the
tests prove the parser reads the Python names. It also keeps the theme's
"Appearance" paragraph, which the Sphinx parser once returned as the
description.

Run with::

    uv run python -m unittest cdk_docs.test_construct_doc
"""

from __future__ import annotations

import unittest
from unittest import mock

from cdk_docs import construct_doc, fetch


SOURCE_URL = (
    "https://docs.aws.amazon.com/cdk/api/v2/docs/"
    "aws-cdk-lib.aws_connect.CfnInstance.html?lang=python"
)


def _prop_row(ts_name: str, py_name: str, py_type: str, summary: str, *, required: bool) -> str:
    """One Construct Props row with TypeScript and Python variants."""
    optional = (
        ""
        if required
        else '<span class="member-optional"><span aria-hidden="true">?</span>'
        '<span class="member-optional-label">optional</span></span>'
    )
    badge = '<span class="member-required">required</span>' if required else ""
    return (
        f'<div class="member-row" id="props-cfninstanceprops-{ts_name.lower()}">'
        '<div class="member-line">'
        f'<span class="lang-variant" data-lang="ts"><code class="member-name">{ts_name}</code>'
        f'{optional}<span class="member-type" title="string">string</span></span>'
        f'<span class="lang-variant" data-lang="python"><code class="member-name">{py_name}</code>'
        f'{optional}<span class="member-type" title="{py_type}">{py_type}</span></span>'
        f"{badge}</div>"
        f'<div class="member-summary">{summary}</div></div>'
    )


# Trimmed but structurally faithful CfnInstance page.
SAMPLE_HTML = f"""
<html><body>
<div class="VPNavScreen"><div class="item appearance"><p>Appearance</p></div></div>
<div data-pagefind-body="true">
<h1 id="class-cfninstance-construct"><span>CfnInstance</span>
  <span class="VPBadge tip api-badge api-badge-l1">L1 construct</span></h1>
<p>The <code>AWS::Connect::Instance</code> resource specifies an Amazon Connect instance.</p>
<nav class="inheritance-chain"><a class="chain-item" href="#">CfnResource</a></nav>
<h2 id="initializer">Initializer</h2>
<div><div class="lang-variant" data-lang="python"><pre><code>CfnInstance(scope: Construct, id: str, props: CfnInstanceProps)</code></pre></div></div>
<h2 id="props-cfninstanceprops">Construct Props</h2>
<div class="lang-tabs"><div class="props-table member-list">
{_prop_row("attributes", "attributes", "typing.Union[IResolvable, AttributesProperty]",
           "A toggle for an individual feature at the instance level.", required=True)}
{_prop_row("directoryId", "directory_id", "str",
           "The identifier for the directory.", required=False)}
{_prop_row("identityManagementType", "identity_management_type", "str",
           "The identity management type.", required=True)}
{_prop_row("instanceAlias", "instance_alias", "str",
           "The alias of instance.", required=False)}
</div></div>
<h2 id="properties">Properties</h2>
<div class="lang-tabs"><div class="props-table member-list">
<div class="member-row" id="attrarn"><div class="member-line">
<span class="lang-variant" data-lang="ts"><code class="member-name">attrArn</code></span>
<span class="lang-variant" data-lang="python"><code class="member-name">attr_arn</code>
<span class="member-type" title="str">str</span></span></div>
<div class="member-summary">The Amazon Resource Name (ARN) of the instance.</div></div>
</div></div>
<h2 id="methods">Methods</h2>
<div class="lang-tabs"><div class="methods-table member-list">
<div class="member-row" id="addoverride"><div class="member-line">
<span class="lang-variant" data-lang="ts"><code class="member-signature">addOverride(path: string, value: any): void</code></span>
<span class="lang-variant" data-lang="python"><code class="member-signature">def add_override(self, path: str, value: typing.Any) -&gt; None</code></span></div>
<div class="member-summary">Adds an override to the synthesized CloudFormation resource.</div></div>
</div></div>
</div>
</body></html>
"""

# A page with no construct heading or Initializer section: the shape the
# Sphinx parser met after AWS's redirect, reduced to the theme chrome.
UNRECOGNISED_HTML = """
<html><body>
<div class="item appearance"><p>Appearance</p></div>
<p>Loading API index...</p>
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

    def test_property_list_uses_python_names_and_excludes_plumbing(self) -> None:
        result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", "aws_cdk.aws_connect"
        )
        names = [p["name"] for p in result["properties"]]
        self.assertEqual(
            names,
            ["attributes", "directory_id", "identity_management_type", "instance_alias"],
        )
        # scope/id appear only in the Initializer signature.
        self.assertNotIn("scope", names)
        self.assertNotIn("id", names)
        # The TypeScript variant's camelCase name is never picked.
        self.assertNotIn("identityManagementType", names)

    def test_property_records_carry_type_required_description(self) -> None:
        result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", "aws_cdk.aws_connect"
        )
        by_name = {p["name"]: p for p in result["properties"]}
        # required: the row carries the member-required badge
        self.assertTrue(by_name["identity_management_type"]["required"])
        self.assertEqual(by_name["identity_management_type"]["type"], "str")
        self.assertEqual(
            by_name["identity_management_type"]["description"],
            "The identity management type.",
        )
        self.assertEqual(
            by_name["attributes"]["type"],
            "typing.Union[IResolvable, AttributesProperty]",
        )
        # optional: the Python variant carries member-optional
        self.assertFalse(by_name["directory_id"]["required"])

    def test_description_is_lead_paragraph_not_page_chrome(self) -> None:
        # The Sphinx parser fell back to the first <p> on the page, which
        # on the new site is the theme's "Appearance" toggle.
        result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", "aws_cdk.aws_connect"
        )
        self.assertEqual(
            result["description"],
            "The AWS::Connect::Instance resource specifies an Amazon Connect instance.",
        )

    def test_raw_sections_is_escape_hatch_dict(self) -> None:
        result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", "aws_cdk.aws_connect"
        )
        sections = result["raw_sections"]
        self.assertIsInstance(sections, dict)
        self.assertEqual(
            sorted(sections), ["Attributes", "Description", "Methods", "Parameters"]
        )
        self.assertIn(
            "attr_arn: The Amazon Resource Name (ARN) of the instance.",
            sections["Attributes"],
        )
        self.assertEqual(sections["Methods"], "add_override")

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

    def test_unrecognised_layout_returns_error_not_empty_result(self) -> None:
        # A page without the construct layout must report a miss. An empty
        # property list would read like a construct with no properties.
        with mock.patch.object(fetch, "fetch_page", return_value=UNRECOGNISED_HTML):
            result = construct_doc.get_cdk_construct_doc(
                "CfnInstance", "aws_cdk.aws_connect"
            )
        self.assertIsInstance(result, str)
        self.assertIn("CfnInstance", result)
        self.assertIn("failed to parse", result)
        self.assertIn("Initializer", result)

    def test_empty_response_returns_error_string(self) -> None:
        with mock.patch.object(fetch, "fetch_page", return_value=""):
            result = construct_doc.get_cdk_construct_doc(
                "CfnEmpty", "aws_cdk.aws_connect"
            )
        self.assertIsInstance(result, str)
        self.assertIn("CfnEmpty", result)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
