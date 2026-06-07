"""Per-construct deep-dive parser for the AWS CDK (Python) reference.

Public entry point:

    get_cdk_construct_doc(construct, library=None)
        e.g. get_cdk_construct_doc("CfnInstance", "aws_cdk.aws_connect")

It fetches the construct's CDK reference page (Sphinx-generated HTML),
parses it into the ``ConstructDoc`` model (design M2):

    {
        "construct":    str,            # the requested identifier (verbatim)
        "library":      str,            # one of the four LIBRARIES
        "url":          str,            # source CDK doc page (verbatim)
        "properties":   list[Property], # [{name, type?, required?, description?}]
        "description":  str | None,
        "raw_sections": dict[str, str], # escape hatch, like page_doc.raw_sections
    }

Parse fidelity (Req 1.5): the requested construct name, the source URL,
and the property list (non-empty when the page documents any) survive
parsing intact.

Error handling (Req 1.6): nothing raises out of ``get_cdk_construct_doc``.
When a page cannot be retrieved or parsed, a descriptive error string is
returned that names the requested identifier and the reason — mirroring
how ``connect_knowledge.docs.aws_search`` returns an error string rather
than raising.

The HTTP GET and the closed set of in-scope construct libraries come from
``cdk_docs.fetch`` (task 1.2): the module-level ``LIBRARIES`` mapping
(module name -> reference URL) and ``fetch_page(url)`` which returns the
page text or raises ``FetchError`` on failure. The import is done lazily
inside the public function so this module imports cleanly even if
``fetch.py`` is briefly absent; a small set of fallback callable names
keeps the binding resilient to that module's exact public name.
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# Root of the AWS CDK v2 Python API reference. Every construct page lives at
# ``<root>/<library>/<Construct>.html`` regardless of whether the library's
# landing page is ``<library>/README.html`` or ``<library>.html``, so the
# per-construct URL is built from this stable root rather than from the
# (heterogeneous) library reference URLs in ``LIBRARIES``.
CDK_PYTHON_REF_ROOT = "https://docs.aws.amazon.com/cdk/api/v2/python/"

# Candidate attribute names for the fetch callable exposed by ``cdk_docs.fetch``
# (task 1.2). ``fetch_page`` is the real name; the rest are defensive
# fallbacks so construct_doc.py stays decoupled from that module's exact
# public name.
_FETCH_CALLABLE_NAMES = (
    "fetch_page",
    "fetch",
    "fetch_doc",
    "fetch_url",
    "fetch_cdk_page",
    "get",
    "http_get",
)

# Constructor parameters that are CDK plumbing, not resource properties.
_PLUMBING_PARAMS = {"scope", "id", "*", "/", ""}


# ----- fetch.py integration ----------------------------------------------


def _load_fetch_and_libraries() -> tuple[Any, dict[str, str]]:
    """Import ``cdk_docs.fetch`` and resolve its fetch callable + LIBRARIES.

    Returns a ``(fetch_callable, LIBRARIES)`` pair. Raises ImportError /
    AttributeError if fetch.py (task 1.2) is not yet available or does not
    expose the documented interface — callers convert these into a
    descriptive error result rather than propagating them.
    """
    from cdk_docs import fetch as fetch_mod  # lazy: fetch.py is task 1.2

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
    """Build the canonical CDK reference URL for a construct."""
    return f"{CDK_PYTHON_REF_ROOT}{library}/{construct}.html"


# ----- HTML parsing helpers ----------------------------------------------


def _pilcrow_strip(text: str) -> str:
    """Drop Sphinx's trailing headerlink pilcrow (\uf0c1) and whitespace."""
    return text.replace("\uf0c1", "").replace("\u00b6", "").strip()


def _find_class_dl(soup: BeautifulSoup) -> Tag | None:
    """Return the ``<dl class="py class">`` describing the construct, if any."""
    return soup.find("dl", class_="class")


def _parse_description(class_dd: Tag | None, soup: BeautifulSoup) -> str | None:
    """First meaningful paragraph of the construct's docstring.

    Skips the Sphinx ``Bases: ...`` line. Falls back to the first page-level
    paragraph if the class docstring has no usable lead paragraph.
    """
    if class_dd is not None:
        for p in class_dd.find_all("p", recursive=False):
            text = p.get_text(" ", strip=True)
            if text and not text.startswith("Bases:"):
                return text
    # Fallback: first non-empty, non-"Bases:" paragraph anywhere.
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if text and not text.startswith("Bases:"):
            return text
    return None


def _signature_param_requiredness(class_dl: Tag) -> dict[str, bool]:
    """Map constructor parameter name -> required (no default in signature)."""
    requiredness: dict[str, bool] = {}
    dt = class_dl.find("dt")
    if dt is None:
        return requiredness
    for em in dt.find_all("em", class_="sig-param"):
        token = em.get_text(strip=True)
        # token looks like "name", "name=None", or "name: Type = None"
        name = token.split("=")[0].split(":")[0].strip()
        if name in _PLUMBING_PARAMS:
            continue
        requiredness[name] = "=" not in token
    return requiredness


def _split_param_description(full_text: str) -> str | None:
    """Pull the prose after the en/em-dash separator in a parameter <li>."""
    for sep in (" \u2013 ", " \u2014 ", " - "):
        if sep in full_text:
            return full_text.split(sep, 1)[1].strip() or None
    return None


def _parse_properties(class_dl: Tag) -> list[dict[str, Any]]:
    """Parse the constructor ``Parameters`` list into property records.

    Returns ``[{name, type?, required?, description?}]`` for every
    constructor parameter that is a resource property (CDK plumbing
    parameters ``scope`` / ``id`` are excluded).
    """
    class_dd = class_dl.find("dd")
    if class_dd is None:
        return []

    requiredness = _signature_param_requiredness(class_dl)

    params_dd: Tag | None = None
    for dt in class_dd.find_all("dt"):
        if dt.get_text(strip=True).startswith("Parameters"):
            params_dd = dt.find_next_sibling("dd")
            break
    if params_dd is None:
        return []

    properties: list[dict[str, Any]] = []
    for li in params_dd.find_all("li"):
        p = li.find("p")
        if p is None:
            continue
        strong = p.find("strong")
        if strong is None:
            continue
        name = strong.get_text(strip=True)
        if name in _PLUMBING_PARAMS:
            continue

        prop: dict[str, Any] = {"name": name}

        type_span = p.find("span", class_="sphinx_autodoc_typehints-type")
        if type_span is not None:
            type_text = type_span.get_text(" ", strip=True)
            # Collapse whitespace introduced by nested spans/links.
            type_text = " ".join(type_text.split())
            if type_text:
                prop["type"] = type_text

        if name in requiredness:
            prop["required"] = requiredness[name]

        description = _split_param_description(p.get_text(" ", strip=True))
        if description:
            prop["description"] = description

        properties.append(prop)

    return properties


def _parse_attributes(soup: BeautifulSoup) -> dict[str, str]:
    """Map attribute name -> its one-line description (the ``attr_*`` outputs)."""
    attributes: dict[str, str] = {}
    for dl in soup.find_all("dl", class_="attribute"):
        dt = dl.find("dt")
        dd = dl.find("dd")
        if dt is None:
            continue
        name_span = dt.find("span", class_="sig-name")
        name = name_span.get_text(strip=True) if name_span else None
        if not name:
            continue
        desc = dd.get_text(" ", strip=True) if dd else ""
        attributes[name] = " ".join(desc.split())
    return attributes


def _parse_methods(soup: BeautifulSoup) -> list[str]:
    """List the public method names documented on the page."""
    methods: list[str] = []
    for dl in soup.find_all("dl", class_="method"):
        dt = dl.find("dt")
        if dt is None:
            continue
        name_span = dt.find("span", class_="sig-name")
        name = name_span.get_text(strip=True) if name_span else None
        if name:
            methods.append(name)
    return methods


def _build_raw_sections(
    description: str | None,
    class_dl: Tag | None,
    soup: BeautifulSoup,
) -> dict[str, str]:
    """Build the escape-hatch ``raw_sections`` map (design M2 / page_doc parity)."""
    sections: dict[str, str] = {}

    if description:
        sections["Description"] = description

    if class_dl is not None:
        class_dd = class_dl.find("dd")
        if class_dd is not None:
            for dt in class_dd.find_all("dt"):
                if dt.get_text(strip=True).startswith("Parameters"):
                    params_dd = dt.find_next_sibling("dd")
                    if params_dd is not None:
                        raw = params_dd.get_text("\n", strip=True)
                        if raw:
                            sections["Parameters"] = raw
                    break

    attributes = _parse_attributes(soup)
    if attributes:
        sections["Attributes"] = "\n".join(
            f"{name}: {desc}" if desc else name for name, desc in attributes.items()
        )

    methods = _parse_methods(soup)
    if methods:
        sections["Methods"] = "\n".join(methods)

    return sections


def _parse_construct_page(html: str, construct: str, library: str, url: str) -> dict[str, Any]:
    """Parse construct reference HTML into the ConstructDoc dict (M2)."""
    soup = BeautifulSoup(html, "html.parser")

    class_dl = _find_class_dl(soup)
    class_dd = class_dl.find("dd") if class_dl is not None else None

    description = _parse_description(class_dd, soup)
    properties = _parse_properties(class_dl) if class_dl is not None else []
    raw_sections = _build_raw_sections(description, class_dl, soup)

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
        reason (Req 1.6) — this function never raises.
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

    # Determine which libraries to try.
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
        except Exception as exc:  # malformed page — report, do not raise
            errors.append(f"{lib}: failed to parse {url}: {exc}")
            continue

        return result

    # Nothing resolved — build a descriptive error naming the identifier.
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


__all__ = ["get_cdk_construct_doc", "CDK_PYTHON_REF_ROOT"]
