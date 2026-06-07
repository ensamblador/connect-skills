"""Property-based test for MCP tool / CLI parity.

Feature: connect-iac-cdk, Property 4: MCP tool / CLI parity

Property 4 (design ``Correctness Properties`` / C1 "MCP tool / CLI twin"
table): *for any* lookup input (a search query/limit, or a construct
identifier/library), the result produced by the ``CDK_Docs_MCP`` tool and
the result produced by the corresponding console script are EQUIVALENT,
because both delegate to the *same* underlying ``cdk_docs`` package
function.

Validates: Requirements 1.7

Equivalence is pinned three ways per input, under a single mocked backend
so the underlying function is deterministic:

  search:
    - ``cdk_docs_mcp.search_cdk_docs(query, limit)``  (the MCP tool)
      == ``cdk_docs.search.cdk_search(query, limit=limit)`` (the function
         the CLI calls)
    - the ``cdk-docs-search`` CLI (``cli.docs_main``) prints exactly that
      function's output verbatim (``print`` adds one trailing newline).

  construct:
    - ``cdk_docs_mcp.get_cdk_construct_doc(construct, library)`` (MCP tool)
      == ``cdk_docs.construct_doc.get_cdk_construct_doc(construct,
         library=library)`` (the function the CLI calls)
    - the ``cdk-construct-doc`` CLI (``cli.construct_main``) prints exactly
      ``cli._render_construct_doc(result)`` (pretty JSON for a dict result,
      the error string verbatim for an error result).

The search backend (``cdk_docs.search.requests.post``) and the per-construct
fetch (``cdk_docs.fetch.fetch_page``) are mocked exactly the way
``test_search.py`` / ``test_construct_doc.py`` mock them, so the test is
deterministic and offline.

Run with (from ``cdk_docs_mcp/``)::

    uv run --with hypothesis --with pytest pytest cdk_docs/test_mcp_cli_parity.py
"""

from __future__ import annotations

import contextlib
import io
from unittest import mock

import requests
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# The server module (``cdk_docs_mcp.py``) lives at the top of the
# ``cdk_docs_mcp/`` directory, one level above this ``cdk_docs`` package.
# Its ``@mcp.tool()`` decorator returns the wrapped function unchanged, so
# ``cdk_docs_mcp.search_cdk_docs`` / ``.get_cdk_construct_doc`` are directly
# callable and delegate to the same package functions the CLI calls.
import cdk_docs_mcp as server
from cdk_docs import cli, construct_doc, fetch, search


# ==========================================================================
# Search parity
# ==========================================================================
_CDK_LINK_PREFIX = "https://docs.aws.amazon.com/cdk/api/v2/python"
_NON_CDK_LINK = "https://docs.aws.amazon.com/connect/latest/adminguide/foo.html"

# Snippet/title text: keep it to a readable, control-char-free alphabet so
# the formatted output is stable. (Parity holds for any text, since all
# three call paths format identically; this just keeps examples legible.)
_text = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,-",
    min_size=0,
    max_size=40,
)

# Query strings may even start with a dash; the CLI is driven with an
# explicit ``--`` end-of-options separator so such a query is still parsed
# as the positional argument.
_query = st.text(min_size=0, max_size=40)


@st.composite
def _suggestions(draw) -> list[dict]:
    """A list (possibly empty) of search-suggestion records.

    Mirrors the shape ``cdk_docs.search`` consumes: each record is a
    ``{"textExcerptSuggestion": {title, link, summary?, suggestionBody?}}``.
    Links are a mix of in-scope CDK reference URLs (which survive the
    CDK-reference filter) and non-CDK URLs (which are filtered out), so the
    generated inputs exercise the "results found", "no results", and
    mixed-filter branches.
    """
    n = draw(st.integers(min_value=0, max_value=6))
    records: list[dict] = []
    for i in range(n):
        is_cdk = draw(st.booleans())
        if is_cdk:
            link = f"{_CDK_LINK_PREFIX}/aws_cdk.aws_connect/Cfn{i}.html"
        else:
            link = f"{_NON_CDK_LINK}?n={i}"
        excerpt: dict = {"title": draw(_text), "link": link}
        summary = draw(_text)
        if summary:
            excerpt["summary"] = summary
        body = draw(_text)
        if body:
            excerpt["suggestionBody"] = body
        records.append({"textExcerptSuggestion": excerpt})
    return records


def _ok_post(suggestions: list[dict]) -> mock.Mock:
    """A ``requests.post`` mock returning a successful search response."""
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"suggestions": suggestions}
    return mock.Mock(return_value=resp)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=_query,
    limit=st.integers(min_value=0, max_value=30),
    suggestions=_suggestions(),
    backend_error=st.booleans(),
)
def test_property4_search_mcp_cli_parity(
    query: str,
    limit: int,
    suggestions: list[dict],
    backend_error: bool,
) -> None:
    """Feature: connect-iac-cdk, Property 4: MCP tool / CLI parity.

    For any (query, limit) lookup, the ``search_cdk_docs`` MCP tool, the
    ``cdk_search`` package function the CLI calls, and the ``cdk-docs-search``
    console-script output are all equivalent.

    Validates: Requirements 1.7
    """
    if backend_error:
        # Exercise the error-string branch: a transport failure makes
        # cdk_search return its "Error searching CDK docs: ..." string.
        post_mock: mock.Mock = mock.Mock(
            side_effect=requests.exceptions.ConnectionError("boom")
        )
    else:
        post_mock = _ok_post(suggestions)

    with mock.patch.object(search.requests, "post", new=post_mock):
        # 1) the MCP tool result
        mcp_result = server.search_cdk_docs(query, limit)
        # 2) the function the CLI delegates to
        fn_result = search.cdk_search(query, limit=limit)
        # 3) the CLI's printed output (``--`` ends option parsing so a
        #    leading-dash query is still treated as the positional arg)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.docs_main(["--limit", str(limit), "--", query])
        cli_out = buf.getvalue()

    # MCP tool == package function (the tool is a thin delegate).
    assert mcp_result == fn_result
    # CLI prints the package function's output verbatim (+ one newline).
    assert cli_out == fn_result + "\n"
    # Search always reports success at the process level.
    assert rc == 0


# ==========================================================================
# Construct parity
# ==========================================================================
# A fixed, structurally faithful Sphinx construct page. The parsed result's
# ``construct`` / ``library`` / ``url`` fields come from the *inputs* (not
# from this HTML), so a single fixture is enough to drive parity across all
# generated identifiers.
_SAMPLE_HTML = """
<html><body>
<section id="cfn">
<dl class="py class">
  <dt class="sig sig-object py" id="lib.Cfn">
    <span class="sig-name descname"><span class="pre">Cfn</span></span>
    <span class="sig-paren">(</span>
    <em class="sig-param"><span class="n"><span class="pre">scope</span></span></em>,
    <em class="sig-param"><span class="n"><span class="pre">id</span></span></em>,
    <em class="sig-param"><span class="o"><span class="pre">*</span></span></em>,
    <em class="sig-param"><span class="n"><span class="pre">attributes</span></span></em>,
    <em class="sig-param"><span class="n"><span class="pre">directory_id</span></span><span class="o"><span class="pre">=</span></span><span class="default_value"><span class="pre">None</span></span></em>,
    <span class="sig-paren">)</span>
  </dt>
  <dd>
    <p>Bases: <code>CfnResource</code></p>
    <p>A generated construct page for the parity property test.</p>
    <dl class="field-list simple">
      <dt class="field-odd">Parameters</dt>
      <dd class="field-odd"><ul class="simple">
        <li><p><strong>scope</strong> (<span class="sphinx_autodoc_typehints-type"><code><span class="pre">Construct</span></code></span>) \u2013 Scope in which this resource is defined.</p></li>
        <li><p><strong>id</strong> (<span class="sphinx_autodoc_typehints-type"><code><span class="pre">str</span></code></span>) \u2013 Construct identifier.</p></li>
        <li><p><strong>attributes</strong> (<span class="sphinx_autodoc_typehints-type"><code><span class="pre">Union</span></code></span>) \u2013 A toggle for an individual feature.</p></li>
        <li><p><strong>directory_id</strong> (<span class="sphinx_autodoc_typehints-type"><code><span class="pre">Optional</span></code></span>) \u2013 The identifier for the directory.</p></li>
      </ul></dd>
    </dl>
  </dd>
</dl>
</section>
</body></html>
"""

# Construct identifiers: realistic ``Cfn*`` names plus the empty/whitespace
# edge cases (which take the descriptive-error branch). Leading/odd chars are
# fine because the CLI is driven with a ``--`` end-of-options separator.
_construct_names = st.one_of(
    st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=1,
        max_size=20,
    ).map(lambda s: "Cfn" + s),
    st.sampled_from(["", "   ", "CfnInstance"]),
)

# Libraries: the four in-scope ones, ``None`` (try-all), and an out-of-scope
# value (the unknown-library error branch) — every branch must stay in parity.
_libraries = st.sampled_from([*sorted(fetch.LIBRARIES), None, "aws_cdk.aws_s3"])


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
    construct=_construct_names,
    library=_libraries,
    fetch_error=st.booleans(),
)
def test_property4_construct_mcp_cli_parity(
    construct: str,
    library: str | None,
    fetch_error: bool,
) -> None:
    """Feature: connect-iac-cdk, Property 4: MCP tool / CLI parity.

    For any (construct, library) lookup, the ``get_cdk_construct_doc`` MCP
    tool, the ``get_cdk_construct_doc`` package function the CLI calls, and
    the ``cdk-construct-doc`` console-script output are all equivalent (the
    CLI renders a dict result as pretty JSON and passes an error string
    through verbatim).

    Validates: Requirements 1.7
    """
    if fetch_error:
        # Exercise the descriptive-error branch: the fetch layer raises, so
        # get_cdk_construct_doc returns its "Could not retrieve ..." string.
        fetch_mock: mock.Mock = mock.Mock(
            side_effect=fetch.FetchError("https://example/Cfn.html", "HTTP 404")
        )
    else:
        fetch_mock = mock.Mock(return_value=_SAMPLE_HTML)

    with mock.patch.object(fetch, "fetch_page", new=fetch_mock):
        # 1) the MCP tool result
        mcp_result = server.get_cdk_construct_doc(construct, library)
        # 2) the function the CLI delegates to
        fn_result = construct_doc.get_cdk_construct_doc(construct, library=library)
        # 3) the CLI's printed output
        argv = ["--", construct] if library is None else ["--library", library, "--", construct]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.construct_main(argv)
        cli_out = buf.getvalue()

    # MCP tool == package function (the tool is a thin delegate).
    assert mcp_result == fn_result
    # CLI prints exactly what _render_construct_doc renders for that result.
    assert cli_out == cli._render_construct_doc(fn_result) + "\n"
    # The CLI signals an error result with a non-zero exit, success with 0.
    assert rc == (1 if isinstance(fn_result, str) else 0)


# ==========================================================================
# Concrete examples (defense in depth — pin the two output shapes).
# ==========================================================================
def test_search_parity_concrete_example() -> None:
    """Feature: connect-iac-cdk, Property 4: MCP tool / CLI parity.

    Validates: Requirements 1.7
    """
    suggestions = [
        {
            "textExcerptSuggestion": {
                "title": "CfnInstance",
                "link": f"{_CDK_LINK_PREFIX}/aws_cdk.aws_connect/CfnInstance.html",
                "summary": "The instance construct.",
            }
        }
    ]
    with mock.patch.object(search.requests, "post", new=_ok_post(suggestions)):
        mcp_result = server.search_cdk_docs("instance", 10)
        fn_result = search.cdk_search("instance", limit=10)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.docs_main(["--limit", "10", "--", "instance"])
        cli_out = buf.getvalue()
    assert mcp_result == fn_result
    assert "Title: CfnInstance" in fn_result
    assert cli_out == fn_result + "\n"


def test_construct_parity_concrete_example_dict_result() -> None:
    """A successful lookup: CLI renders the dict as pretty JSON.

    Feature: connect-iac-cdk, Property 4: MCP tool / CLI parity
    Validates: Requirements 1.7
    """
    import json

    with mock.patch.object(fetch, "fetch_page", new=mock.Mock(return_value=_SAMPLE_HTML)):
        mcp_result = server.get_cdk_construct_doc("CfnInstance", "aws_cdk.aws_connect")
        fn_result = construct_doc.get_cdk_construct_doc(
            "CfnInstance", library="aws_cdk.aws_connect"
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.construct_main(["--library", "aws_cdk.aws_connect", "--", "CfnInstance"])
        cli_out = buf.getvalue()
    assert mcp_result == fn_result
    assert isinstance(fn_result, dict)
    assert cli_out == json.dumps(fn_result, indent=2, ensure_ascii=False) + "\n"
    assert rc == 0


def test_construct_parity_concrete_example_error_result() -> None:
    """An error lookup: CLI passes the error string through verbatim.

    Feature: connect-iac-cdk, Property 4: MCP tool / CLI parity
    Validates: Requirements 1.7
    """
    mcp_result = server.get_cdk_construct_doc("CfnFoo", "aws_cdk.aws_s3")
    fn_result = construct_doc.get_cdk_construct_doc("CfnFoo", library="aws_cdk.aws_s3")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.construct_main(["--library", "aws_cdk.aws_s3", "--", "CfnFoo"])
    cli_out = buf.getvalue()
    assert mcp_result == fn_result
    assert isinstance(fn_result, str)
    assert cli_out == fn_result + "\n"
    assert rc == 1


if __name__ == "__main__":  # pragma: no cover
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
