"""API tests for external book search using an injected provider."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes.external_books import get_book_provider
from app.main import app
from app.schemas.external_books import ExternalBookRead, ExternalBookSearchQuery
from app.services.external_books.base import (
    BookProviderError,
    BookProviderQuotaExceeded,
    BookProviderTimeout,
)


class FakeBookProvider:
    """Small deterministic provider used by route tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[ExternalBookSearchQuery, int, int]] = []
        self.error: BookProviderError | None = None

    async def search(
        self,
        query: ExternalBookSearchQuery,
        *,
        start_index: int,
        max_results: int,
    ) -> tuple[list[ExternalBookRead], int]:
        self.calls.append((query, start_index, max_results))
        if self.error is not None:
            raise self.error
        if query.isbn is not None:
            return [], 0
        return (
            [
                ExternalBookRead(
                    provider_id="volume-1",
                    title="Earthsea",
                    authors=["Ursula K. Le Guin"],
                )
            ],
            41,
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Provide an API client with an injected provider and no external network."""
    provider = FakeBookProvider()
    previous_override = app.dependency_overrides.get(get_book_provider)
    app.dependency_overrides[get_book_provider] = lambda: provider
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_book_provider, None)
        else:
            app.dependency_overrides[get_book_provider] = previous_override


def test_search_returns_normalized_books_and_pagination(client: TestClient) -> None:
    """Success response uses the application schema and requested pagination."""
    response = client.get(
        "/api/v1/external-books/search",
        params={"title": "Earthsea", "page": 2, "page_size": 20},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["provider_id"] == "volume-1"
    assert payload["items"][0]["title"] == "Earthsea"
    assert payload["total"] == 41
    assert payload["page"] == 2
    assert payload["page_size"] == 20
    assert payload["total_pages"] == 3
    provider = app.dependency_overrides[get_book_provider]()
    assert provider.calls[0][1:] == (20, 20)


def test_search_returns_empty_page(client: TestClient) -> None:
    """Empty provider results are a successful empty page."""
    response = client.get(
        "/api/v1/external-books/search", params={"isbn": "9780000000000"}
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0
    assert response.json()["total_pages"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"title": "Earthsea", "author": "Le Guin"},
        {"title": "  ", "author": "Le Guin"},
        {"title": "  "},
        {"isbn": "9780000000000", "page_size": 41},
        {"title": "Earthsea", "page": 0},
    ],
)
def test_search_rejects_invalid_criteria_and_pagination(
    client: TestClient, params: dict[str, Any]
) -> None:
    """Exactly one criterion and supported pagination bounds are enforced."""
    response = client.get("/api/v1/external-books/search", params=params)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("provider_error", "expected_status"),
    [
        (BookProviderTimeout(), 504),
        (BookProviderError("private provider detail"), 502),
        (BookProviderQuotaExceeded(), 503),
    ],
)
def test_search_maps_provider_errors_without_leaking_details(
    client: TestClient,
    provider_error: BookProviderError,
    expected_status: int,
) -> None:
    """Provider errors map to stable public statuses and generic details."""
    provider = app.dependency_overrides[get_book_provider]()
    provider.error = provider_error

    response = client.get("/api/v1/external-books/search", params={"title": "Earthsea"})

    assert response.status_code == expected_status
    assert "private provider detail" not in response.text
