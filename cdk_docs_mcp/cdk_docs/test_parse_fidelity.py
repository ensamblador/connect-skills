"""Property-based test for CDK construct-doc parse fidelity.

Feature: connect-iac-cdk, Property 3: Doc parse fidelity

Property 3 (design ``Correctness Properties`` / data model M2): for any
in-scope construct page the fetcher retrieves, parsing preserves

  (a) the requested construct name verbatim,
  (b) the source URL verbatim, and
  (c) a NON-EMPTY property list when the page documents any properties
      (the parsed property names round-trip, excluding the CDK plumbing
      parameters ``scope`` / ``id``).

Validates: Requirements 1.3, 1.5

Strategy: rather than ship a single hand-written fixture, this test
*generates* synthetic-but-realistic CDK Sphinx construct pages. Hypothesis
picks a construct name (``Cfn`` + identifier), an in-scope library from the
four ``fetch.LIBRARIES``, and a list of property records (name / type /
description), and renders them into the same Sphinx HTML structure the real
parser expects (mirroring the ``CfnInstance`` fixture in
``test_construct_doc.py``: a ``dl.class`` with a constructor signature of
``em.sig-param`` tokens and a ``Parameters`` field list of
``<li><p><strong>name</strong> (<span
class="sphinx_autodoc_typehints-type">Type</span>) - description</p>``).
``cdk_docs.fetch.fetch_page`` is mocked to return that HTML, so the test is
deterministic and offline.

Run with (from ``cdk_docs_mcp/``)::

    uv run --with hypothesis --with pytest pytest cdk_docs/test_parse_fidelity.py
"""

from __future__ import annotations

from typing import Any
from unittest import mock

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cdk_docs import construct_doc, fetch


# --------------------------------------------------------------------------
# Constructor parameters the parser treats as CDK plumbing (never resource
# properties). Kept in sync with ``construct_doc._PLUMBING_PARAMS``.
# --------------------------------------------------------------------------
_PLUMBING_NAMES = {"scope", "id"}

# The four in-scope construct libraries (Req 1.4), drawn from the real
# closed set the fetch layer declares.
_LIBRARIES = sorted(fetch.LIBRARIES)


# --------------------------------------------------------------------------
# Strategies.
# --------------------------------------------------------------------------
# Construct identifiers: "Cfn" + an alphanumeric suffix, e.g. "CfnInstance".
# No surrounding whitespace and no HTML-significant characters, so the name
# survives both ``construct.strip()`` and ``<strong>`` text extraction
# intact.
_construct_names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=1,
    max_size=20,
).map(lambda s: "Cfn" + s)

# Property names: snake_case-ish identifiers (lowercase + underscore), never
# a plumbing parameter. The restricted alphabet guarantees the name is
# recovered verbatim from ``<strong>name</strong>``.
_prop_names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_",
    min_size=1,
    max_size=24,
).filter(lambda s: s not in _PLUMBING_NAMES)

# Type hints: short, link-free tokens like the real ``sphinx_autodoc_typehints``
# spans render (``str``, ``Optional``, ``Union`` ...).
_type_text = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[],. ",
    min_size=1,
    max_size=30,
).map(lambda s: " ".join(s.split())).filter(lambda s: len(s) > 0)

# Descriptions: plain prose with no HTML-significant chars and no hyphen, so
# the parser's en/em-dash/hyphen description separator is unambiguous.
_desc_text = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.",
    min_size=1,
    max_size=80,
).map(lambda s: " ".join(s.split())).filter(lambda s: len(s) > 0)


@st.composite
def _property_records(draw) -> list[dict[str, str]]:
    """A list (possibly empty) of unique property records {name, type, description}."""
    names = draw(st.lists(_prop_names, unique=True, min_size=0, max_size=8))
    records: list[dict[str, str]] = []
    for name in names:
        records.append(
            {
                "name": name,
                "type": draw(_type_text),
                "description": draw(_desc_text),
            }
        )
    return records


# --------------------------------------------------------------------------
# Render a synthetic-but-realistic Sphinx construct page.
# --------------------------------------------------------------------------
def _render_param_li(name: str, ptype: str, description: str) -> str:
    return (
        f"<li><p><strong>{name}</strong> "
        f'(<span class="sphinx_autodoc_typehints-type"><code>'
        f'<span class="pre">{ptype}</span></code></span>) '
        f"\u2013 {description}</p></li>"
    )


def _render_sig_param(name: str) -> str:
    return (
        f'<em class="sig-param"><span class="n">'
        f'<span class="pre">{name}</span></span></em>'
    )


def _render_construct_page(construct: str, properties: list[dict[str, str]]) -> str:
    """Render the ConstructDoc-shaped Sphinx HTML the real parser consumes.

    Always includes the ``scope`` / ``id`` plumbing parameters (as the real
    pages do) so the test also exercises that plumbing is excluded from the
    parsed property list.
    """
    sig_params = [
        _render_sig_param("scope"),
        _render_sig_param("id"),
        '<em class="sig-param"><span class="o"><span class="pre">*</span></span></em>',
    ]
    sig_params += [_render_sig_param(p["name"]) for p in properties]
    signature = ",\n    ".join(sig_params)

    param_lis = [
        _render_param_li("scope", "Construct", "Scope in which this resource is defined."),
        _render_param_li("id", "str", "Construct identifier for this resource."),
    ]
    param_lis += [
        _render_param_li(p["name"], p["type"], p["description"]) for p in properties
    ]
    lis = "\n        ".join(param_lis)

    return f"""<html><body>
<section id="{construct.lower()}">
<h1>{construct}<a class="headerlink" href="#{construct.lower()}">\uf0c1</a></h1>
<dl class="py class">
  <dt class="sig sig-object py" id="library.{construct}">
    <span class="sig-name descname"><span class="pre">{construct}</span></span>
    <span class="sig-paren">(</span>
    {signature}
    <span class="sig-paren">)</span>
  </dt>
  <dd>
    <p>Bases: <code>CfnResource</code></p>
    <p>A generated construct page for the parse-fidelity property test.</p>
    <dl class="field-list simple">
      <dt class="field-odd">Parameters</dt>
      <dd class="field-odd"><ul class="simple">
        {lis}
      </ul></dd>
    </dl>
  </dd>
</dl>
</section>
</body></html>"""


# --------------------------------------------------------------------------
# Property 3: Doc parse fidelity (>=100 iterations).
# --------------------------------------------------------------------------
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
    construct=_construct_names,
    library=st.sampled_from(_LIBRARIES),
    properties=_property_records(),
)
def test_property3_doc_parse_fidelity(
    construct: str, library: str, properties: list[dict[str, str]]
) -> None:
    """Feature: connect-iac-cdk, Property 3: Doc parse fidelity.

    For any in-scope construct page the fetcher retrieves, parsing preserves
    the requested construct name verbatim, the source URL verbatim, and a
    non-empty property list (with round-tripping names) whenever the page
    documents any resource properties.

    Validates: Requirements 1.3, 1.5
    """
    html = _render_construct_page(construct, properties)

    # The canonical per-construct URL the parser builds and must preserve
    # verbatim into the result (design M2 / Req 1.5).
    expected_url = f"{construct_doc.CDK_PYTHON_REF_ROOT}{library}/{construct}.html"

    with mock.patch.object(fetch, "fetch_page", return_value=html) as mock_fetch:
        result = construct_doc.get_cdk_construct_doc(construct, library)

    # Parsing a retrievable page yields the ConstructDoc dict, never an error.
    assert isinstance(result, dict), f"expected ConstructDoc dict, got: {result!r}"

    # (a) the requested construct name is preserved verbatim.
    assert result["construct"] == construct
    assert result["library"] == library

    # (b) the source URL is preserved verbatim, and it is the URL fetched.
    assert result["url"] == expected_url
    mock_fetch.assert_called_once_with(expected_url)

    parsed_names = [p["name"] for p in result["properties"]]
    documented_names = [p["name"] for p in properties]

    # CDK plumbing (scope / id) is never surfaced as a resource property.
    assert "scope" not in parsed_names
    assert "id" not in parsed_names

    # (c) when the page documents any resource properties, the parsed list is
    # non-empty and the documented names round-trip exactly (order preserved).
    if documented_names:
        assert parsed_names, "page documented properties but parsed list was empty"
        assert parsed_names == documented_names
    else:
        # Only plumbing parameters present -> no resource properties parsed.
        assert parsed_names == []


def _sanity_example() -> dict[str, Any]:
    """Tiny non-Hypothesis smoke check that the rendered HTML parses at all."""
    props = [
        {"name": "instance_alias", "type": "str", "description": "The alias of instance."},
        {"name": "directory_id", "type": "Optional", "description": "The directory id."},
    ]
    html = _render_construct_page("CfnInstance", props)
    with mock.patch.object(fetch, "fetch_page", return_value=html):
        return construct_doc.get_cdk_construct_doc("CfnInstance", "aws_cdk.aws_connect")


def test_property3_rendered_fixture_parses() -> None:
    """A concrete example pins the generator/parser contract (defense in depth).

    Feature: connect-iac-cdk, Property 3: Doc parse fidelity
    Validates: Requirements 1.3, 1.5
    """
    result = _sanity_example()
    assert isinstance(result, dict)
    assert result["construct"] == "CfnInstance"
    assert result["url"].endswith("aws_cdk.aws_connect/CfnInstance.html")
    names = [p["name"] for p in result["properties"]]
    assert names == ["instance_alias", "directory_id"]
