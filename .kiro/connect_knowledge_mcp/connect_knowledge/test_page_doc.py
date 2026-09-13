"""Tests for the markdown-first ``page_doc`` doc fetchers.

These pin the behaviour that motivated the markdown-first reshape. The
previous design mapped ``## `` headings onto fixed keys (``channels``,
``properties``, ``configuration_tips``). AWS is migrating the block pages
to new wording, so those keys silently emptied on 10 of 58 blocks:

    old layout          new layout
    ------------------  ---------------------------
    Supported channels  Contact types
    Properties          How to configure this block
    Flow types bullets  Flow types table

The invariant now is: whatever headings a page has, they appear in
``sections`` and their content is reachable. Nothing is dropped because
AWS renamed something, and a section miss is *reported* rather than
returned as an empty value indistinguishable from a real one.

``_fetch`` is mocked with synthetic fixtures in both layouts, so the
tests are deterministic and offline.

Run with (from ``connect_knowledge_mcp/``)::

    uv run --with pytest pytest connect_knowledge/test_page_doc.py
"""

from __future__ import annotations

from unittest import mock

import pytest

from connect_knowledge import page_doc
from connect_knowledge.page_doc import ADMINGUIDE_ROOT, get_action_doc, get_block_doc


# --------------------------------------------------------------------------
# Fixtures: the same block documented in both AWS layouts.
# --------------------------------------------------------------------------
OLD_LAYOUT = """# Flow block in Connect Customer: AWS Lambda function

## Description

Calls AWS Lambda. See [Set contact attributes](set-contact-attributes.md).

## Supported channels

| Channel | Supported? |
| --- | --- |
| Voice | Yes |
| Chat | Yes |

## Flow types

+ Inbound flow
+ Customer Queue flow

## Properties

Set the timeout, max 8 seconds.

## Configuration tips

Add the function to your instance first.
"""

NEW_LAYOUT = """# Flow block in Connect Customer: Get customer input

## Description

Captures interactive input. See [Store customer input](store-customer-input.md).

## Use cases for this block

Phone menus.

## Contact types

| Channel | Supported? |
| --- | --- |
| Voice | Yes |
| Task | No |

## Flow types

| Flow type | Supported? |
| --- | --- |
| Inbound flow | Yes |
| Customer hold flow | No |

## How to configure this block

Pick a prompt, then configure DTMF.
"""

ACTION_PAGE = """# TagContact

Sets a collection of tags on the current contact.

## Parameter object

```
{ "Tags": { "Key1": "Value1" } }
```

## Errors

+ NoMatchingError - if no other Error matches.

## Corresponding block in the UI

[Contact tags](contact-tags-block.md)
"""


def _with(markdown: str):
    """Patch the module's fetch to return a fixture."""
    return mock.patch.object(page_doc, "_fetch", return_value=markdown)


class TestSectionsDiscovery:
    def test_old_layout_headings_are_listed(self):
        with _with(OLD_LAYOUT):
            d = get_block_doc("invoke-lambda-function-block")
        assert d["sections"] == [
            "Description", "Supported channels", "Flow types",
            "Properties", "Configuration tips",
        ]

    def test_new_layout_headings_are_listed(self):
        with _with(NEW_LAYOUT):
            d = get_block_doc("get-customer-input")
        assert d["sections"] == [
            "Description", "Use cases for this block", "Contact types",
            "Flow types", "How to configure this block",
        ]

    def test_new_layout_content_is_not_lost(self):
        """The regression: renamed sections must still deliver their data."""
        with _with(NEW_LAYOUT):
            d = get_block_doc("get-customer-input")
        # The channel matrix and the config prose are both present, even
        # though neither sits under the heading the old parser expected.
        assert "| Voice | Yes |" in d["markdown"]
        assert "configure DTMF" in d["markdown"]

    def test_name_is_taken_from_the_title_suffix(self):
        with _with(NEW_LAYOUT):
            d = get_block_doc("get-customer-input")
        assert d["name"] == "Get customer input"
        assert d["title"].startswith("Flow block in")

    def test_title_without_a_colon_becomes_the_name(self):
        with _with(ACTION_PAGE):
            d = get_action_doc("contact-actions-tagcontact")
        assert d["name"] == "TagContact"

    def test_metadata_is_layout_independent(self):
        with _with(NEW_LAYOUT):
            d = get_block_doc("get-customer-input")
        assert d["slug"] == "get-customer-input"
        assert d["url"] == f"{ADMINGUIDE_ROOT}/get-customer-input.html"
        assert d["section"] is None


class TestSectionSelection:
    def test_exact_match(self):
        with _with(NEW_LAYOUT):
            d = get_block_doc("get-customer-input", "Contact types")
        assert d["section"] == "Contact types"
        assert d["markdown"].startswith("## Contact types")
        assert "| Voice | Yes |" in d["markdown"]

    def test_case_insensitive_match(self):
        with _with(NEW_LAYOUT):
            d = get_block_doc("get-customer-input", "contact types")
        assert d["section"] == "Contact types"

    def test_substring_match(self):
        with _with(NEW_LAYOUT):
            d = get_block_doc("get-customer-input", "configure")
        assert d["section"] == "How to configure this block"

    def test_selecting_a_section_shrinks_the_payload(self):
        with _with(NEW_LAYOUT):
            whole = get_block_doc("get-customer-input")
            part = get_block_doc("get-customer-input", "Contact types")
        assert len(part["markdown"]) < len(whole["markdown"])

    def test_miss_is_reported_not_silently_empty(self):
        """A wrong heading must not look like 'this block has no channels'."""
        with _with(NEW_LAYOUT):
            d = get_block_doc("get-customer-input", "Supported channels")
        assert d["section"] is None
        assert d["markdown"] == ""
        assert "No section matching 'Supported channels'" in d["error"]
        # The real headings are offered so the caller can retry.
        assert "Contact types" in d["error"]

    def test_hit_carries_no_error_key(self):
        with _with(NEW_LAYOUT):
            d = get_block_doc("get-customer-input", "Contact types")
        assert "error" not in d

    def test_action_parameter_object_slice(self):
        with _with(ACTION_PAGE):
            d = get_action_doc("contact-actions-tagcontact", "Parameter object")
        assert d["section"] == "Parameter object"
        assert '"Tags"' in d["markdown"]
        assert "NoMatchingError" not in d["markdown"]


class TestRelativeLinkRewriting:
    def test_relative_md_link_becomes_absolute_html(self):
        with _with(OLD_LAYOUT):
            d = get_block_doc("invoke-lambda-function-block")
        assert f"]({ADMINGUIDE_ROOT}/set-contact-attributes.html)" in d["markdown"]
        assert "](set-contact-attributes.md)" not in d["markdown"]

    def test_anchor_is_preserved(self):
        md = "See [x](connect-lambda-functions.md#tutorial-invokelambda)."
        out = page_doc._rewrite_relative_links(md, ADMINGUIDE_ROOT)
        assert out == (
            f"See [x]({ADMINGUIDE_ROOT}/connect-lambda-functions.html"
            "#tutorial-invokelambda)."
        )

    def test_absolute_and_special_links_are_untouched(self):
        md = (
            "[a](https://docs.aws.amazon.com/x/y.md) "
            "[b](http://example.invalid/z.md) "
            "[c](mailto:someone@example.com) "
            "[d](#in-page-anchor) "
            "[img](https://docs.aws.amazon.com/i/pic.png)"
        )
        assert page_doc._rewrite_relative_links(md, ADMINGUIDE_ROOT) == md

    def test_rewriting_uses_the_pages_own_root(self):
        """A devguide page must not get adminguide URLs."""
        with _with(ACTION_PAGE):
            d = get_action_doc("contact-actions-tagcontact")
        assert f"]({page_doc.FLOW_LANGUAGE_ROOT}/contact-tags-block.html)" in d["markdown"]


class TestWholePagePassthrough:
    def test_markdown_is_the_source_not_a_reconstruction(self):
        with _with(OLD_LAYOUT):
            d = get_block_doc("invoke-lambda-function-block")
        # Every heading survives verbatim, including ones no named field
        # ever covered.
        for heading in d["sections"]:
            assert f"## {heading}" in d["markdown"]

    def test_no_duplicated_body_in_the_payload(self):
        """Content appears once. The old shape carried it 2-3 times over."""
        with _with(OLD_LAYOUT):
            d = get_block_doc("invoke-lambda-function-block")
        assert d["markdown"].count("Add the function to your instance first.") == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
