"""HTTP fetch for the AWS CDK (Python) reference pages.

Modeled on ``connect_knowledge/docs.py``: an HTTP GET with bounded
exponential back-off retries on transient failures, a fixed request
timeout, and a browser-like ``User-Agent`` (the CDK reference is served
from ``docs.aws.amazon.com`` — the same host ``page_doc.py`` fetches).

The in-scope construct libraries (Req 1.4) and their reference URLs are
declared here as a closed set (``LIBRARIES``).

On failure, ``fetch_page`` raises ``FetchError`` carrying the URL and a
human-readable reason so the construct-doc parser (``construct_doc.py``,
task 1.3) can turn it into a descriptive error result that names the
requested identifier and the reason (Req 1.6).
"""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)

# Browser-like UA — mirrors connect_knowledge/page_doc.py, which fetches
# from the same docs.aws.amazon.com host.
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Retry/back-off knobs — same names and values as connect_knowledge/docs.py.
MAX_RETRIES = 6
BACKOFF_BASE = 2
REQUEST_TIMEOUT = 30

# Transient HTTP status codes worth retrying — mirrors connect_knowledge/docs.py.
_RETRYABLE_STATUS = (400, 429, 500, 502, 503)

# Root of the AWS CDK (v2, Python) API reference.
_CDK_REF_ROOT = "https://docs.aws.amazon.com/cdk/api/v2/python"

# The closed set of in-scope construct libraries (Req 1.4) mapped to their
# CDK (v2, Python) reference URLs. Note ``aws_connect``'s reference lives
# under ``/README.html`` while the other three are flat ``.html`` pages.
LIBRARIES: dict[str, str] = {
    "aws_cdk.aws_connect": f"{_CDK_REF_ROOT}/aws_cdk.aws_connect/README.html",
    "aws_cdk.aws_lex": f"{_CDK_REF_ROOT}/aws_cdk.aws_lex.html",
    "aws_cdk.aws_wisdom": f"{_CDK_REF_ROOT}/aws_cdk.aws_wisdom.html",
    "aws_cdk.aws_bedrockagentcore": f"{_CDK_REF_ROOT}/aws_cdk.aws_bedrockagentcore.html",
}


class FetchError(RuntimeError):
    """Raised when a CDK reference page cannot be retrieved.

    Carries the ``url`` and a human-readable ``reason`` so callers can build
    a descriptive error result that names the requested identifier and the
    reason (Req 1.6), the same way ``aws_search`` surfaces
    ``"Error searching AWS docs: …"`` rather than leaking a raw traceback.
    """

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"Could not retrieve {url}: {reason}")


def library_url(library: str) -> str:
    """Return the CDK reference URL for an in-scope construct library.

    Args:
        library: One of the keys in ``LIBRARIES`` (e.g.
            ``aws_cdk.aws_connect``).

    Returns:
        The reference URL for that library.

    Raises:
        FetchError: If ``library`` is not one of the in-scope libraries.
    """
    try:
        return LIBRARIES[library]
    except KeyError:
        supported = ", ".join(sorted(LIBRARIES))
        raise FetchError(
            library,
            f"unknown construct library (in scope: {supported})",
        ) from None


def fetch_page(url: str, *, timeout: int = REQUEST_TIMEOUT) -> str:
    """GET ``url`` with bounded exponential back-off and return its text.

    Retries transient HTTP failures (status in ``_RETRYABLE_STATUS``) up to
    ``MAX_RETRIES`` times, waiting ``BACKOFF_BASE ** attempt`` seconds
    between attempts — the same retry policy as
    ``connect_knowledge/docs.py``.

    Args:
        url: The CDK reference page URL to fetch.
        timeout: Per-request timeout in seconds (default ``REQUEST_TIMEOUT``).

    Returns:
        The response body text.

    Raises:
        FetchError: On a non-retryable HTTP error, a transport error, or
            once retries are exhausted — carrying ``url`` and the reason.
    """
    last_reason: str | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
            )
            response.raise_for_status()
            return response.text

        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            last_reason = f"HTTP {status}" if status is not None else str(exc)
            if status in _RETRYABLE_STATUS:
                wait = BACKOFF_BASE**attempt
                logger.warning(
                    "fetch_page attempt %d/%d for %s got status %s, retrying in %ds",
                    attempt + 1,
                    MAX_RETRIES,
                    url,
                    status,
                    wait,
                )
                time.sleep(wait)
            else:
                raise FetchError(url, last_reason) from exc

        except requests.exceptions.RequestException as exc:
            raise FetchError(url, str(exc)) from exc

    raise FetchError(url, f"failed after {MAX_RETRIES} retries ({last_reason})")


def fetch_library(library: str, *, timeout: int = REQUEST_TIMEOUT) -> str:
    """Fetch the reference page for an in-scope construct ``library``.

    Convenience wrapper combining ``library_url`` and ``fetch_page``.

    Args:
        library: One of the keys in ``LIBRARIES``.
        timeout: Per-request timeout in seconds (default ``REQUEST_TIMEOUT``).

    Returns:
        The reference page body text.

    Raises:
        FetchError: If ``library`` is out of scope or the page cannot be
            fetched.
    """
    return fetch_page(library_url(library), timeout=timeout)
