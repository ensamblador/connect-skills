"""Unit tests for ``connect_knowledge.blogs``.

Three layers, all offline (``requests.post`` and ``requests.get`` are
mocked):

* ``ranked_blog_search``, the aws.amazon.com ranked search: payload,
  blog filter, rank order kept, and the fuzzy-tail drop in lexical mode.
* ``directory_blog_search``, the directories API fallback, ported from
  ``agentcore-gateway-primitive/tests/unit/test_connect_tools.py``.
* ``aws_blog_search``, which picks between them and labels the fallback
  with a ``Note:`` line.

Run with (from ``connect_knowledge_mcp/``)::

    uv run --with pytest pytest connect_knowledge/test_blogs.py
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from connect_knowledge import blogs

CONNECT = {"contact-center"}


# ----- fixtures ------------------------------------------------------------------


def _ranked_item(title, url, description="", score=2.0, date="2026-01-01T00:00:00Z", chunks=None):
    """One ranked-search result in the shape the API returns."""
    return {
        "title": title,
        "url": url,
        "description": description,
        "relevantChunks": chunks if chunks is not None else [description],
        "metadata": {"isoTimestamp": date, "date": "January 1, 2026", "contributors": "x"},
        "provider": "blogs",
        "score": score,
        "globalRank": 1,
    }


def _post_response(status_code=200, json_data=None):
    """Build a mock ``requests.Response`` for the ranked search."""
    return _mock_blog_response(status_code, {"results": []} if json_data is None else json_data)


def _mock_blog_response(status_code=200, json_data=None):
    """Build a mock ``requests.Response`` whose ``raise_for_status`` raises on 4xx/5xx."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    if status_code >= 400:
        http_error = requests.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status = MagicMock(side_effect=http_error)
    else:
        mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _blog_item(title, link, excerpt="", created="2024-01-01T00:00:00Z"):
    """Build one directories API item in the shape the fallback parses."""
    return {
        "item": {
            "additionalFields": {
                "title": title,
                "link": link,
                "postExcerpt": excerpt,
                "createdDate": created,
            }
        },
        "tags": [],
    }


CC = "https://aws.amazon.com/blogs/contact-center/"


# ----- ranked search -------------------------------------------------------------


def test_ranked_sends_expected_payload():
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response()) as post:
        blogs.ranked_blog_search("amazon connect", CONNECT)

    args, kwargs = post.call_args
    assert args[0] == blogs.RANKED_SEARCH_URL
    body = kwargs["json"]
    assert body["providers"] == [{"name": "blogs"}]
    assert body["query"]["text"] == "amazon connect"
    assert body["query"]["locale"] == "en-US"
    assert body["query"]["pagination"] == {"offset": 0, "limit": blogs.RANKED_LIMIT}


def test_ranked_keeps_api_order_and_filters_blogs():
    items = [
        _ranked_item("Second best", CC + "b/", "about amazon connect"),
        _ranked_item("Other blog", "https://aws.amazon.com/blogs/compute/c/"),
        _ranked_item("Best last in alphabet", CC + "a/", "amazon connect"),
    ]
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response(json_data={"results": items})):
        hits = blogs.ranked_blog_search("amazon connect cases", CONNECT)

    assert [h["title"] for h in hits] == ["Second best", "Best last in alphabet"]
    assert hits[0]["date"] == "2026-01-01"


def test_ranked_lexical_mode_drops_fuzzy_tail():
    # Scores above LEXICAL_SCORE_FLOOR mean lexical mode; "while" is a
    # one-edit match for "chile" and never contains the query word.
    items = [
        _ranked_item("AWS South America (Chile) Region", CC + "chile/", "", score=6.4e9),
        _ranked_item("Dafiti in Brazil and Chile", CC + "dafiti/", "operating in Chile", score=8.4e6),
        _ranked_item("Cut costs while scaling", CC + "while/", "while", score=3.9e3),
        _ranked_item("Amazon Chime SDK costs", CC + "chime/", "Chime", score=3.5e3),
    ]
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response(json_data={"results": items})):
        hits = blogs.ranked_blog_search("chile", CONNECT)

    assert [h["link"] for h in hits] == [CC + "chile/", CC + "dafiti/"]


def test_ranked_lexical_mode_accepts_singular_and_plural():
    items = [
        _ranked_item("Automate case synchronization", CC + "sync/", "cases created in Amazon Connect", score=6e19),
        _ranked_item("Connected devices", CC + "iot/", "connectivity", score=2e19),
    ]
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response(json_data={"results": items})):
        hits = blogs.ranked_blog_search("Connect Cases", CONNECT)

    assert [h["link"] for h in hits] == [CC + "sync/"]


def test_ranked_semantic_mode_keeps_results_without_query_words():
    items = [
        _ranked_item("Rethinking the Case", CC + "rethinking/", "We are willing to be misunderstood", score=1.9),
        _ranked_item("Unrelated words", CC + "other/", "nothing in common", score=1.8),
    ]
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response(json_data={"results": items})):
        hits = blogs.ranked_blog_search("Amazon Connect Cases", CONNECT)

    assert len(hits) == 2


def test_ranked_dedupes_unescapes_caps_and_skips_listing_pages():
    items = [
        _ranked_item("Q&amp;A with &#8220;Connect&#8221;", CC + "qa/"),
        _ranked_item("Duplicate", CC + "qa/"),
        _ranked_item("Author page", CC + "author/jane/"),
        _ranked_item("Third", CC + "third/"),
        _ranked_item("Fourth", CC + "fourth/"),
    ]
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response(json_data={"results": items})):
        hits = blogs.ranked_blog_search("connect", CONNECT, page_size=2)

    assert [h["title"] for h in hits] == ["Q&A with \u201cConnect\u201d", "Third"]


def test_ranked_empty_include_blogs_keeps_every_blog():
    items = [_ranked_item("Compute post", "https://aws.amazon.com/blogs/compute/c/")]
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response(json_data={"results": items})):
        hits = blogs.ranked_blog_search("lambda", set())

    assert len(hits) == 1


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (_post_response(400), "HTTP 400"),
        (_post_response(json_data={"message": "bad"}), "no 'results' list"),
    ],
)
def test_ranked_bad_responses_raise_unavailable(response, reason):
    with patch("connect_knowledge.blogs.requests.post", return_value=response):
        with pytest.raises(blogs.RankedSearchUnavailable, match=reason):
            blogs.ranked_blog_search("x", CONNECT)


def test_ranked_retries_retryable_status_then_raises():
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response(503)) as post, patch(
        "connect_knowledge.blogs.time.sleep"
    ):
        with pytest.raises(blogs.RankedSearchUnavailable, match="HTTP 503 after"):
            blogs.ranked_blog_search("x", CONNECT)
    assert post.call_count == blogs.RANKED_MAX_RETRIES


def test_ranked_transport_error_raises_unavailable():
    with patch(
        "connect_knowledge.blogs.requests.post",
        side_effect=requests.exceptions.ConnectionError("boom"),
    ):
        with pytest.raises(blogs.RankedSearchUnavailable, match="request failed"):
            blogs.ranked_blog_search("x", CONNECT)


# ----- aws_blog_search: choosing a backend ---------------------------------------


def test_aws_blog_search_formats_ranked_hits():
    items = [_ranked_item("Connect post", CC + "a/", "An Amazon Connect post", date="2026-06-09T10:00:00Z")]
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response(json_data={"results": items})), patch(
        "connect_knowledge.blogs.requests.get"
    ) as get:
        result = blogs.aws_blog_search("amazon connect callback")

    assert result == (
        "Title: Connect post\n"
        f"URL: {CC}a/\n"
        "Published: 2026-06-09\n"
        "Snippet: An Amazon Connect post"
    )
    get.assert_not_called()


def test_aws_blog_search_falls_back_with_note_when_ranked_fails():
    directory = {"items": [_blog_item("Connect post", CC + "a/", "amazon connect")]}
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response(400)), patch(
        "connect_knowledge.blogs.requests.get", return_value=_mock_blog_response(200, directory)
    ):
        result = blogs.aws_blog_search("amazon connect")

    note, _, body = result.partition("\n\n")
    assert note.startswith("Note: the ranked AWS search is unavailable (HTTP 400).")
    assert body.startswith("Title: Connect post")


def test_aws_blog_search_falls_back_when_no_ranked_hit_survives_the_filter():
    items = [_ranked_item("Compute post", "https://aws.amazon.com/blogs/compute/c/")]
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response(json_data={"results": items})), patch(
        "connect_knowledge.blogs.requests.get", return_value=_mock_blog_response(200, {"items": []})
    ):
        result = blogs.aws_blog_search("lambda")

    assert result.startswith("Note: the ranked AWS search kept no posts from these blogs in its top 30.")
    assert result.endswith("No AWS blog results found for: lambda")


def test_aws_blog_search_accepts_display_name_aliases():
    items = [
        _ranked_item("ML post", "https://aws.amazon.com/blogs/machine-learning/a/"),
        _ranked_item("Connect post", CC + "b/"),
    ]
    with patch("connect_knowledge.blogs.requests.post", return_value=_post_response(json_data={"results": items})):
        result = blogs.aws_blog_search("agents and models", blogs=["AWS Machine Learning Blog"])

    assert "ML post" in result
    assert "Connect post" not in result


def test_aws_blog_search_rejects_unknown_display_name_without_fetching():
    with patch("connect_knowledge.blogs.requests.post") as post, patch(
        "connect_knowledge.blogs.requests.get"
    ) as get:
        result = blogs.aws_blog_search("post", blogs=["AWS Compute Blog"])

    assert result.startswith("Error searching AWS blogs: unknown blog name(s)")
    assert "AWS Compute Blog" in result
    post.assert_not_called()
    get.assert_not_called()


# ----- directory fallback --------------------------------------------------------


@pytest.mark.parametrize(
    "query,items",
    [
        (
            "amazon connect",
            [
                _blog_item("Amazon Connect routing", CC + "routing/", "Routing in Amazon Connect"),
                _blog_item("APN partner on Amazon Connect", "https://aws.amazon.com/blogs/apn/partner/", "Partner solution", "2024-02-01T00:00:00Z"),
            ],
        ),
        (
            "sms",
            [
                _blog_item("Two-way SMS", "https://aws.amazon.com/blogs/messaging-and-targeting/sms/", "SMS how-to"),
            ],
        ),
    ],
)
def test_directory_happy_path(query, items):
    with patch("connect_knowledge.blogs.requests.get", return_value=_mock_blog_response(200, {"items": items})):
        result = blogs.directory_blog_search(query, set(blogs.DEFAULT_BLOGS))

    assert "Title:" in result
    assert "URL:" in result
    assert "Published:" in result
    for item in items:
        assert item["item"]["additionalFields"]["title"] in result


def test_directory_sends_directories_api_params():
    with patch("connect_knowledge.blogs.requests.get", return_value=_mock_blog_response(200, {"items": []})) as get:
        blogs.directory_blog_search("amazon connect", CONNECT)

    args, kwargs = get.call_args
    assert args[0] == blogs.BLOGS_URL
    params = kwargs["params"]
    assert params["item.directoryId"] == "blog-posts"
    assert params["item.locale"] == "en_US"
    assert params["q"] == "amazon connect"
    assert params["q_operator"] == "AND"
    assert params["size"] == blogs.BLOG_POOL_SIZE_FILTERED


def test_directory_unfiltered_uses_smaller_pool():
    with patch("connect_knowledge.blogs.requests.get", return_value=_mock_blog_response(200, {"items": []})) as get:
        blogs.directory_blog_search("amazon connect", set())

    assert get.call_args.kwargs["params"]["size"] == blogs.BLOG_POOL_SIZE


def test_directory_keeps_only_include_blogs():
    items = [
        _blog_item("Connect post", CC + "a/"),
        _blog_item("Compute post", "https://aws.amazon.com/blogs/compute/b/"),
    ]
    with patch("connect_knowledge.blogs.requests.get", return_value=_mock_blog_response(200, {"items": items})):
        result = blogs.directory_blog_search("post", CONNECT)

    assert "Connect post" in result
    assert "Compute post" not in result


def test_directory_ranks_whole_word_matches_first():
    # API order is newest first; the loose "connecting" match comes first.
    items = [
        _blog_item("Connecting rural sites to Amazon VPC", "https://aws.amazon.com/blogs/apn/rural/", "", "2024-03-01T00:00:00Z"),
        _blog_item("Amazon Connect agent workspace", CC + "ws/", "Amazon Connect tips", "2024-01-01T00:00:00Z"),
    ]
    with patch("connect_knowledge.blogs.requests.get", return_value=_mock_blog_response(200, {"items": items})):
        result = blogs.directory_blog_search("amazon connect", set(blogs.DEFAULT_BLOGS))

    assert result.index("Amazon Connect agent workspace") < result.index("Connecting rural sites")


def test_directory_unescapes_html_entities():
    items = [_blog_item("Q&amp;A with &#8220;Connect&#8221;", CC + "qa/")]
    with patch("connect_knowledge.blogs.requests.get", return_value=_mock_blog_response(200, {"items": items})):
        result = blogs.directory_blog_search("connect", CONNECT)

    assert "Q&A with \u201cConnect\u201d" in result


def test_directory_empty_results():
    with patch("connect_knowledge.blogs.requests.get", return_value=_mock_blog_response(200, {"items": []})):
        result = blogs.directory_blog_search("nonexistent_blog_xyz", CONNECT)

    assert result.startswith("No AWS blog results found for:")


@pytest.mark.parametrize("status_code", [500, 502])
def test_directory_retries_then_error(status_code):
    with patch("connect_knowledge.blogs.requests.get", return_value=_mock_blog_response(status_code)) as get:
        with patch("connect_knowledge.blogs.time.sleep"):
            result = blogs.directory_blog_search("test query", CONNECT)

    assert result.startswith(f"Error after {blogs.MAX_RETRIES} retries:")
    assert get.call_count == blogs.MAX_RETRIES


def test_directory_filters_author_and_tag_pages():
    """Blog results with /author/ or /tag/ in the URL must be filtered out."""
    items = [
        _blog_item("Author Page", CC + "author/john/", "Author bio"),
        _blog_item("Tag Page", CC + "tag/serverless/", "Tag listing"),
    ]
    with patch("connect_knowledge.blogs.requests.get", return_value=_mock_blog_response(200, {"items": items})):
        result = blogs.directory_blog_search("test", CONNECT)

    assert result.startswith("No AWS blog results found for:")
