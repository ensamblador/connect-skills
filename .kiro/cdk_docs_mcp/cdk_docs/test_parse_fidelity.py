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
*generates* synthetic-but-realistic CDK v2 reference pages. Hypothesis
picks a construct name (``Cfn`` + identifier), an in-scope library from the
four ``fetch.LIBRARIES``, and a list of property records (name / type /
description), and renders them into the VitePress structure the real
parser expects (mirroring the ``CfnInstance`` fixture in
``test_construct_doc.py``: an ``<h1>``, an Initializer section whose
signature names ``scope`` and ``id``, and a Construct Props section of
``.member-row`` entries, each with a ``data-lang="python"`` variant).
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
# Initializer arguments that are CDK plumbing, never resource properties.
# The rendered page names them in the Initializer signature only.
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
# recovered verbatim from ``<code class="member-name">``.
_prop_names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_",
    min_size=1,
    max_size=24,
).filter(lambda s: s not in _PLUMBING_NAMES)

# Type hints: short, link-free Python annotations like the real
# ``member-type`` title attribute holds (``str``, ``typing.Union[...]`` ...).
_type_text = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[],. ",
    min_size=1,
    max_size=30,
).map(lambda s: " ".join(s.split())).filter(lambda s: len(s) > 0)

# Descriptions: plain prose with no HTML-significant chars.
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
# Render a synthetic-but-realistic CDK v2 reference construct page.
# --------------------------------------------------------------------------
def _render_prop_row(construct: str, name: str, ptype: str, description: str) -> str:
    """One Construct Props row. The TS variant carries a decoy camelCase name."""
    return (
        f'<div class="member-row" id="props-{construct.lower()}props-{name}">'
        '<div class="member-line">'
        f'<span class="lang-variant" data-lang="ts"><code class="member-name">ts_{name}</code></span>'
        f'<span class="lang-variant" data-lang="python"><code class="member-name">{name}</code>'
        f'<span class="member-type" title="{ptype}">{ptype}</span></span>'
        "</div>"
        f'<div class="member-summary">{description}</div></div>'
    )


def _render_construct_page(construct: str, properties: list[dict[str, str]]) -> str:
    """Render the ConstructDoc-shaped VitePress HTML the real parser consumes.

    The Initializer signature always names the ``scope`` / ``id`` plumbing
    arguments, as the real pages do, so the test also checks that they never
    surface in the parsed property list.
    """
    rows = "\n".join(
        _render_prop_row(construct, p["name"], p["type"], p["description"])
        for p in properties
    )
    return f"""<html><body>
<div class="item appearance"><p>Appearance</p></div>
<div data-pagefind-body="true">
<h1 id="class-{construct.lower()}-construct"><span>{construct}</span></h1>
<p>A generated construct page for the parse-fidelity property test.</p>
<nav class="inheritance-chain"><a class="chain-item" href="#">CfnResource</a></nav>
<h2 id="initializer">Initializer</h2>
<div><div class="lang-variant" data-lang="python"><pre><code>{construct}(scope: Construct, id: str, props: {construct}Props)</code></pre></div></div>
<h2 id="props-{construct.lower()}props">Construct Props</h2>
<div class="lang-tabs"><div class="props-table member-list">
{rows}
</div></div>
<h2 id="properties">Properties</h2>
</div>
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
    module = library.removeprefix("aws_cdk.")
    expected_url = (
        f"{construct_doc.CDK_PYTHON_REF_ROOT}"
        f"aws-cdk-lib.{module}.{construct}.html?lang=python"
    )

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
        # Empty Construct Props section: no resource properties parsed.
        assert parsed_names == []


def _sanity_example() -> dict[str, Any]:
    """Tiny non-Hypothesis smoke check that the rendered HTML parses at all."""
    props = [
        {"name": "instance_alias", "type": "str", "description": "The alias of instance."},
        {"name": "directory_id", "type": "str", "description": "The directory id."},
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
    assert result["url"].endswith("aws-cdk-lib.aws_connect.CfnInstance.html?lang=python")
    names = [p["name"] for p in result["properties"]]
    assert names == ["instance_alias", "directory_id"]
