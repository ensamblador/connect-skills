"""Per-construct deep-dive parser for the AWS CDK (Python) reference.

Public entry point:

    get_cdk_construct_doc(construct, library=None)
        e.g. get_cdk_construct_doc("CfnInstance", "aws_cdk.aws_connect")

It fetches the construct's page from the AWS CDK v2 API reference and
parses it into the ``ConstructDoc`` model (design M2):

    {
        "construct":    str,            # the requested identifier (verbatim)
        "library":      str,            # one of the four LIBRARIES
        "url":          str,            # source CDK doc page (verbatim)
        "properties":   list[Property], # [{name, type?, required?, description?}]
        "description":  str | None,
        "raw_sections": dict[str, str], # escape hatch, like page_doc.raw_sections
    }

Source layout. AWS replaced the Sphinx-generated Python reference at
``cdk/api/v2/python/<library>/<Construct>.html`` with one VitePress site
for all five CDK languages at
``cdk/api/v2/docs/aws-cdk-lib.<module>.<Construct>.html``. The old
addresses answer 301 to the new ones. The Sphinx parser kept running
against the redirect target, found no ``<dl class="py class">``, returned
an empty property list, and took the site's "Appearance" menu as the
description. That reply looked like a construct with no properties. The
parser now raises ``LayoutNotRecognized`` when the construct heading or
the Initializer section is missing, so the next layout change surfaces as
an error string instead of an empty result. Nested property types such as
``CfnGateway.AuthorizerConfigurationProperty`` are struct pages with no
Initializer, so they take the same error path.

Why HTML and not markdown. Each page links a ``.md`` twin, but the twin
carries only the TypeScript variant: camelCase names and TS types, with
no Python form at any address. The Python names and annotations exist
only in the HTML, in ``<span class="lang-variant" data-lang="python">``
inside each ``.member-row``, so this module parses HTML.

Parse fidelity (Req 1.5): the requested construct name, the source URL,
and the property list (non-empty when the page documents any) survive
parsing intact.

Error handling (Req 1.6): nothing raises out of ``get_cdk_construct_doc``.
When a page cannot be retrieved or parsed, a descriptive error string is
returned that names the requested identifier and the reason, mirroring
how ``connect_knowledge.docs.aws_search`` returns an error string rather
than raising.

The HTTP GET and the closed set of in-scope construct libraries come from
``cdk_docs.fetch``: the module-level ``LIBRARIES`` mapping (module name to
reference URL) and ``fetch_page(url)``, which returns the page text or
raises ``FetchError``. The import is lazy inside the public function so
this module imports cleanly even if ``fetch.py`` is briefly absent.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# Root of the AWS CDK v2 API reference. Every construct page lives at
# ``<root>aws-cdk-lib.<module>.<Construct>.html``, so the per-construct URL
# is built from this root rather than from the library landing pages in
# ``LIBRARIES``.
CDK_PYTHON_REF_ROOT = "https://docs.aws.amazon.com/cdk/api/v2/docs/"

# Candidate attribute names for the fetch callable exposed by
# ``cdk_docs.fetch``. ``fetch_page`` is the real name; the rest are
# defensive fallbacks.
_FETCH_CALLABLE_NAMES = (
    "fetch_page",
    "fetch",
    "fetch_doc",
    "fetch_url",
    "fetch_cdk_page",
    "get",
    "http_get",
)

# Each member row renders one ``lang-variant`` span per language.
_PY_VARIANT = '.member-line [data-lang="python"]'
# Method rows carry a Python signature such as ``def add_override(self, ...)``.
_METHOD_NAME = re.compile(r"def\s+(\w+)")
# The props heading id embeds the props type: ``props-cfninstanceprops``.
_PROPS_HEADING = re.compile(r"^props-")
# Elements that end the lead paragraphs under the construct ``<h1>``.
_LEAD_STOP = {"nav", "dl", "div", "h2"}


class LayoutNotRecognized(ValueError):
    """The page lacks the construct heading and Initializer section."""


# ----- fetch.py integration ----------------------------------------------


def _load_fetch_and_libraries() -> tuple[Any, dict[str, str]]:
    """Import ``cdk_docs.fetch`` and resolve its fetch callable and LIBRARIES.

    Returns:
        A ``(fetch_callable, LIBRARIES)`` pair.

    Raises:
        ImportError, AttributeError: When fetch.py is unavailable or does
            not expose the documented interface. Callers convert these
            into a descriptive error result.
    """
    from cdk_docs import fetch as fetch_mod

    libraries = getattr(fetch_mod, "LIBRARIES", None)
    if not isinstance(libraries, dict) or not libraries:
        raise AttributeError(
            "cdk_docs.fetch does not expose a non-empty LIBRARIES mapping"
        )

    fetch_callable = None
    for name in _FETCH_CALLABLE_NAMES:
        candidate = getattr(fetch_mod, name, None)
        if callable(candidate):
            fetch_callable = candidate
            break
    if fetch_callable is None:
        raise AttributeError(
            "cdk_docs.fetch does not expose a recognized fetch function "
            f"(looked for: {', '.join(_FETCH_CALLABLE_NAMES)})"
        )
    return fetch_callable, libraries


def _construct_url(library: str, construct: str) -> str:
    """Build the canonical CDK v2 reference URL for a construct.

    ``aws_cdk.aws_connect`` with ``CfnInstance`` becomes
    ``<root>aws-cdk-lib.aws_connect.CfnInstance.html?lang=python``. The
    query only selects the Python tab for a human reader. The server sends
    every language variant either way.
    """
    module = library.removeprefix("aws_cdk.")
    return f"{CDK_PYTHON_REF_ROOT}aws-cdk-lib.{module}.{construct}.html?lang=python"


# ----- HTML parsing helpers ----------------------------------------------


def _text(tag: Tag | None) -> str:
    """Tag text with whitespace collapsed, or ``""`` for ``None``."""
    return " ".join(tag.get_text().split()) if tag is not None else ""


def _section_rows(soup: BeautifulSoup, heading_id: str | re.Pattern[str]) -> list[Tag]:
    """Return the ``.member-row`` entries between an ``<h2>`` and the next one."""
    h2 = soup.find("h2", id=heading_id)
    if h2 is None:
        return []
    rows: list[Tag] = []
    for sib in h2.next_siblings:
        if not isinstance(sib, Tag):
            continue
        if sib.name == "h2":
            break
        rows.extend(sib.select(".member-row"))
    return rows


def _python_name(row: Tag) -> str:
    """Python identifier of a member row, property or method."""
    variant = row.select_one(_PY_VARIANT)
    if variant is None:
        return ""
    name = variant.select_one(".member-name")
    if name is not None:
        return _text(name)
    match = _METHOD_NAME.search(_text(variant.select_one(".member-signature")))
    return match.group(1) if match else ""


def _lead_paragraphs(h1: Tag) -> list[tuple[str, str]]:
    """``(tag_name, text)`` for each paragraph or blockquote under the heading.

    The lead ends at the type-hierarchy ``<nav>``. ``CfnBot`` opens with a
    blockquote before its first paragraph, so the caller picks the first
    ``p`` for ``description`` and keeps the whole lead in ``raw_sections``.
    """
    lead: list[tuple[str, str]] = []
    for sib in h1.find_next_siblings():
        if sib.name in _LEAD_STOP:
            break
        text = _text(sib)
        if sib.name in ("p", "blockquote") and text:
            lead.append((sib.name, text))
    return lead


def _parse_properties(rows: list[Tag]) -> list[dict[str, Any]]:
    """Map Construct Props rows to ``[{name, type?, required?, description?}]``.

    ``required`` is ``True`` when the row carries the ``.member-required``
    badge and ``False`` when the Python variant carries ``.member-optional``.
    The type comes from the Python variant's ``title`` attribute, which
    holds the annotation without the spaces that nested links add to the
    element text.

    Args:
        rows: ``.member-row`` elements from the Construct Props section.

    Returns:
        One record per row with a Python name, in page order.
    """
    properties: list[dict[str, Any]] = []
    for row in rows:
        name = _python_name(row)
        if not name:
            continue
        variant = row.select_one(_PY_VARIANT)
        prop: dict[str, Any] = {"name": name}

        type_span = variant.select_one(".member-type")
        if type_span is not None:
            type_text = type_span.get("title") or _text(type_span)
            if type_text:
                prop["type"] = type_text

        if row.select_one(".member-line .member-required") is not None:
            prop["required"] = True
        elif variant.select_one(".member-optional") is not None:
            prop["required"] = False

        parts = (
            _text(row.select_one(".member-summary")),
            _text(row.select_one(".member-details")),
        )
        description = " ".join(part for part in parts if part)
        if description:
            prop["description"] = description

        properties.append(prop)
    return properties


def _name_lines(pairs: list[tuple[str, str]]) -> str:
    """Render ``(name, text)`` pairs as ``name: text`` lines."""
    return "\n".join(f"{name}: {text}" if text else name for name, text in pairs)


def _parse_construct_page(html: str, construct: str, library: str, url: str) -> dict[str, Any]:
    """Parse construct reference HTML into the ConstructDoc dict (M2).

    Raises:
        LayoutNotRecognized: When the page has no ``<h1>`` or no
            Initializer section. The caller turns this into an error string.
    """
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1 is None or soup.find("h2", id="initializer") is None:
        raise LayoutNotRecognized(
            "no construct heading and Initializer section; "
            "the CDK reference layout may have changed"
        )

    lead = _lead_paragraphs(h1)
    description = next((text for tag, text in lead if tag == "p"), None)
    properties = _parse_properties(_section_rows(soup, _PROPS_HEADING))

    raw_sections: dict[str, str] = {}
    if lead:
        raw_sections["Description"] = "\n\n".join(text for _, text in lead)
    if properties:
        raw_sections["Parameters"] = _name_lines(
            [(p["name"], p.get("description", "")) for p in properties]
        )
    attributes = [
        (name, _text(row.select_one(".member-summary")))
        for row in _section_rows(soup, "properties")
        if (name := _python_name(row))
    ]
    if attributes:
        raw_sections["Attributes"] = _name_lines(attributes)
    methods = [name for row in _section_rows(soup, "methods") if (name := _python_name(row))]
    if methods:
        raw_sections["Methods"] = "\n".join(methods)

    return {
        "construct": construct,  # requested identifier, preserved verbatim (Req 1.5)
        "library": library,
        "url": url,  # source URL, preserved verbatim (Req 1.5)
        "properties": properties,
        "description": description,
        "raw_sections": raw_sections,
    }


# ----- public API ---------------------------------------------------------


def get_cdk_construct_doc(construct: str, library: str | None = None) -> dict[str, Any] | str:
    """Fetch and parse a CDK construct reference page.

    Args:
        construct: The construct identifier, e.g. ``CfnInstance``.
        library: One of the in-scope ``LIBRARIES`` keys
            (``aws_cdk.aws_connect``, ``aws_cdk.aws_lex``,
            ``aws_cdk.aws_wisdom``, ``aws_cdk.aws_bedrockagentcore``). When
            ``None``, every in-scope library is tried until one resolves.

    Returns:
        On success, the ConstructDoc dict (design M2). On failure, a
        descriptive error string naming the requested identifier and the
        reason (Req 1.6). This function never raises.
    """
    if not construct or not construct.strip():
        return "Could not retrieve CDK construct: no construct identifier was provided"
    construct = construct.strip()

    try:
        fetch_callable, libraries = _load_fetch_and_libraries()
    except (ImportError, AttributeError) as exc:
        return (
            f"Could not retrieve construct '{construct}': "
            f"the CDK fetch layer (cdk_docs.fetch) is unavailable: {exc}"
        )

    if library is not None:
        library = library.strip()
        if library not in libraries:
            valid = ", ".join(sorted(libraries))
            return (
                f"Could not retrieve construct '{construct}' in '{library}': "
                f"'{library}' is not an in-scope CDK library (expected one of: {valid})"
            )
        candidate_libraries = [library]
    else:
        candidate_libraries = list(libraries)

    errors: list[str] = []
    for lib in candidate_libraries:
        url = _construct_url(lib, construct)
        try:
            html = fetch_callable(url)
        except Exception as exc:  # fetch raises on failure (network / HTTP / 404)
            errors.append(f"{lib}: {exc}")
            continue

        if not html:
            errors.append(f"{lib}: empty response from {url}")
            continue

        try:
            result = _parse_construct_page(html, construct, lib, url)
        except Exception as exc:  # unrecognised or malformed page: report, do not raise
            errors.append(f"{lib}: failed to parse {url}: {exc}")
            continue

        return result

    if len(candidate_libraries) == 1:
        return (
            f"Could not retrieve construct '{construct}' in "
            f"'{candidate_libraries[0]}': {errors[0] if errors else 'unknown error'}"
        )
    detail = "; ".join(errors) if errors else "no in-scope library resolved"
    return (
        f"Could not retrieve construct '{construct}' in any in-scope CDK "
        f"library (tried {', '.join(candidate_libraries)}): {detail}"
    )


__all__ = ["get_cdk_construct_doc", "CDK_PYTHON_REF_ROOT", "LayoutNotRecognized"]
