"""Unit tests for the Google Books HTTP adapter without network access."""

import asyncio
import json

import httpx
import pytest

from app.schemas.external_books import ExternalBookSearchQuery
from app.services.external_books.base import (
    BookProviderInvalidResponse,
    BookProviderQuotaExceeded,
    BookProviderTimeout,
    BookProviderTransportError,
)
from app.services.external_books.google_books import GoogleBooksProvider


def run_search(
    handler: httpx.MockTransport,
    query: ExternalBookSearchQuery | None = None,
    *,
    start_index: int = 0,
    max_results: int = 20,
):
    """Run one provider request through a transport that never uses the network."""

    async def search():
        async with httpx.AsyncClient(transport=handler) as client:
            provider = GoogleBooksProvider(client)
            return await provider.search(
                query or ExternalBookSearchQuery(title="Earthsea"),
                start_index=start_index,
                max_results=max_results,
            )

    return asyncio.run(search())


def test_search_normalizes_valid_volumes_and_skips_malformed_items() -> None:
    """A malformed item does not discard other usable volumes in the page."""
    body = {
        "totalItems": 3,
        "items": [
            {"id": "missing-title", "volumeInfo": {"authors": ["A"]}},
            "not-a-volume",
            {
                "id": "book-1",
                "volumeInfo": {
                    "title": "  Earthsea  ",
                    "authors": ["Ursula K. Le Guin", None, 4],
                    "publishedDate": "1968",
                    "industryIdentifiers": [
                        {"type": "ISBN_10", "identifier": "054792822X"},
                        {"type": "ISBN_13", "identifier": "9780547928227"},
                        {"type": [], "identifier": ["malformed"]},
                        None,
                    ],
                    "pageCount": "invalid",
                    "imageLinks": {"thumbnail": "https://images.test/book"},
                },
            },
            {"id": "partial", "volumeInfo": {"title": "Partial volume"}},
        ],
    }

    books, total = run_search(
        httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    )

    assert total == 3
    assert [book.provider_id for book in books] == ["book-1", "partial"]
    assert books[0].title == "Earthsea"
    assert books[0].authors == ["Ursula K. Le Guin"]
    assert books[0].isbn_10 == "054792822X"
    assert books[0].isbn_13 == "9780547928227"
    assert books[0].page_count is None
    assert books[0].thumbnail_url == "https://images.test/book"
    assert books[1].authors == []


@pytest.mark.parametrize(
    ("query", "expected_qualifier"),
    [
        (ExternalBookSearchQuery(title="Earthsea"), "intitle:Earthsea"),
        (ExternalBookSearchQuery(author="Octavia Butler"), "inauthor:Octavia Butler"),
        (ExternalBookSearchQuery(isbn="9780000000000"), "isbn:9780000000000"),
    ],
)
def test_search_uses_google_qualifiers_and_pagination_parameters(
    query: ExternalBookSearchQuery,
    expected_qualifier: str,
) -> None:
    """Each criterion and offset pagination map to Google's supported params."""
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.url.params)
        return httpx.Response(200, json={"totalItems": 0})

    result = run_search(
        httpx.MockTransport(handler),
        query,
        start_index=40,
        max_results=20,
    )

    assert result == ([], 0)
    assert captured[0]["q"] == expected_qualifier
    assert captured[0]["startIndex"] == "40"
    assert captured[0]["maxResults"] == "20"


def test_search_maps_timeout_and_transport_errors() -> None:
    """Timeout and connection failures become provider-specific exceptions."""

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private timeout detail", request=request)

    def connection_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private connection detail", request=request)

    with pytest.raises(BookProviderTimeout):
        run_search(httpx.MockTransport(timeout_handler))
    with pytest.raises(BookProviderTransportError):
        run_search(httpx.MockTransport(connection_handler))


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"error": {"message": "private quota detail"}}),
        httpx.Response(
            403,
            json={"error": {"errors": [{"reason": "userRateLimitExceeded"}]}},
        ),
    ],
)
def test_search_maps_quota_responses(response: httpx.Response) -> None:
    """HTTP 429 and Google quota reasons on HTTP 403 are recognized."""
    with pytest.raises(BookProviderQuotaExceeded):
        run_search(httpx.MockTransport(lambda request: response))


def test_search_maps_other_http_failures_without_exposing_provider_body() -> None:
    """Non-quota provider status errors become a generic transport failure."""
    with pytest.raises(BookProviderTransportError) as error:
        run_search(
            httpx.MockTransport(
                lambda request: httpx.Response(
                    500, json={"error": {"message": "private upstream detail"}}
                )
            )
        )

    assert "private upstream detail" not in str(error.value)


@pytest.mark.parametrize(
    "content",
    [b"not-json", json.dumps({"totalItems": "many", "items": []}).encode()],
)
def test_search_rejects_invalid_provider_payloads(content: bytes) -> None:
    """Invalid JSON and malformed top-level payloads fail as provider errors."""
    with pytest.raises(BookProviderInvalidResponse):
        run_search(
            httpx.MockTransport(lambda request: httpx.Response(200, content=content))
        )
