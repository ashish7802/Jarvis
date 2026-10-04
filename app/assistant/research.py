"""Bounded live web search with source URLs for user-requested research."""
from dataclasses import dataclass
from html.parser import HTMLParser
import logging
import re
from urllib.parse import parse_qs, urlsplit

import httpx

log = logging.getLogger("jarvis.research")
SEARCH_URL = "https://html.duckduckgo.com/html/"
MAX_RESPONSE_BYTES = 1_000_000
MAX_RESULTS = 5


class ResearchError(RuntimeError):
    """A live research request could not return trustworthy source links."""


@dataclass(frozen=True)
class ResearchResult:
    title: str
    url: str
    snippet: str


class _ResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.snippets: list[str] = []
        self._capture: str | None = None
        self._capture_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if self._capture is not None:
            self._capture_depth += 1
        elif tag == "a" and "result__a" in classes:
            self._capture = "title"
            self._capture_depth = 1
            self._parts = []
            self._href = values.get("href", "")
        elif "result__snippet" in classes:
            self._capture = "snippet"
            self._capture_depth = 1
            self._parts = []

    def handle_endtag(self, _tag):
        if self._capture is None:
            return
        self._capture_depth -= 1
        if self._capture_depth > 0:
            return
        value = re.sub(r"\s+([.,!?;:])", r"\1", " ".join(" ".join(self._parts).split()))
        if value and self._capture == "title":
            self.links.append((value[:300], self._href))
        elif value and self._capture == "snippet":
            self.snippets.append(value[:800])
        self._capture = None
        self._capture_depth = 0
        self._parts = []

    def handle_data(self, data):
        if self._capture is not None:
            self._parts.append(data)


class WebResearcher:
    """Search DuckDuckGo's HTML endpoint; redirects and result-page fetching are disabled."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def search(self, query: str) -> list[ResearchResult]:
        query = query.strip()
        if not query or len(query) > 300 or any(ord(char) < 32 for char in query):
            raise ResearchError("Give me a clear research question under 300 characters.")
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=False,
                headers={"User-Agent": "JARVIS/1.0 (user-requested web search)"},
            ) as client:
                with client.stream("GET", SEARCH_URL, params={"q": query}) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise ResearchError("The search provider returned an oversized page.")
            page = bytes(body).decode("utf-8", errors="replace")
        except httpx.HTTPStatusError as exc:
            log.warning("Search provider returned HTTP %d", exc.response.status_code)
            raise ResearchError(
                "The web search provider couldn't complete that search. Try again later."
            ) from exc
        except ResearchError:
            raise
        except httpx.HTTPError as exc:
            log.warning("Live search failed (%s)", type(exc).__name__)
            raise ResearchError(
                "I couldn't reach the web search provider. Check your connection and try again."
            ) from exc

        parser = _ResultsParser()
        parser.feed(page)
        results = []
        for index, (title, href) in enumerate(parser.links[:MAX_RESULTS]):
            url = self._result_url(href)
            if url is None:
                continue
            snippet = parser.snippets[index] if index < len(parser.snippets) else ""
            results.append(ResearchResult(title, url, snippet))
        if not results:
            raise ResearchError("The web search returned no usable source links.")
        log.info("Search returned %d source(s) for a user request", len(results))
        return results

    @staticmethod
    def _result_url(href: str) -> str | None:
        try:
            parts = urlsplit(href)
            if parts.hostname and (
                parts.hostname == "duckduckgo.com"
                or parts.hostname.endswith(".duckduckgo.com")
            ):
                target = parse_qs(parts.query).get("uddg", [""])[0]
                parts = urlsplit(target)
            if (parts.scheme not in {"https", "http"} or not parts.hostname
                    or parts.username or parts.password):
                return None
            return parts.geturl()[:2048]
        except ValueError:
            return None
