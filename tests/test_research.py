import pytest

import httpx

from app.assistant.research import ResearchError, WebResearcher


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        yield self.body.encode("utf-8")


class FakeClient:
    def __init__(self, body):
        self.body = body
        self.request = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def stream(self, method, url, *, params):
        self.request = method, url, params
        return FakeResponse(self.body)


def test_search_returns_bounded_source_links_and_query_is_encoded(monkeypatch):
    body = (
        '<a class="result__a" href="https://example.com/page">Example <b>source</b></a>'
        '<a class="result__snippet">A useful <b>summary</b>.</a>'
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fother">'
        "Second source</a>"
    )
    client = FakeClient(body)
    options = []

    def create_client(**kwargs):
        options.append(kwargs)
        return client

    monkeypatch.setattr("app.assistant.research.httpx.Client", create_client)
    results = WebResearcher().search("Jarvis research & browsers")

    assert client.request == (
        "GET",
        "https://html.duckduckgo.com/html/",
        {"q": "Jarvis research & browsers"},
    )
    assert options[0]["follow_redirects"] is False
    assert results[0].title == "Example source"
    assert results[0].url == "https://example.com/page"
    assert results[0].snippet == "A useful summary."
    assert results[1].url == "https://example.org/other"


def test_search_rejects_non_http_and_empty_results(monkeypatch):
    monkeypatch.setattr(
        "app.assistant.research.httpx.Client",
        lambda **_kwargs: FakeClient('<a class="result__a" href="javascript:alert(1)">bad</a>'),
    )
    with pytest.raises(ResearchError, match="no usable source"):
        WebResearcher().search("question")


def test_search_reports_network_failure(monkeypatch):
    class BrokenClient(FakeClient):
        def stream(self, *_args, **_kwargs):
            request = httpx.Request("GET", "https://html.duckduckgo.com/html/")
            raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr(
        "app.assistant.research.httpx.Client",
        lambda **_kwargs: BrokenClient(""),
    )
    with pytest.raises(ResearchError, match="couldn't reach"):
        WebResearcher().search("question")
