"""Google Books API adapter."""

from typing import Any
from urllib.parse import quote

import httpx

from app.schemas.external_books import ExternalBookRead, ExternalBookSearchQuery
from app.services.external_books.base import (
    BookProviderInvalidResponse,
    BookProviderQuotaExceeded,
    BookProviderTimeout,
    BookProviderTransportError,
)

GOOGLE_BOOKS_VOLUMES_URL = "https://www.googleapis.com/books/v1/volumes"
QUOTA_ERROR_REASONS = {
    "dailyLimitExceeded",
    "quotaExceeded",
    "rateLimitExceeded",
    "userRateLimitExceeded",
}


class GoogleBooksProvider:
    """Search Google Books and normalize its volume records."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(
        self,
        query: ExternalBookSearchQuery,
        *,
        start_index: int,
        max_results: int,
    ) -> tuple[list[ExternalBookRead], int]:
        """Fetch one page and retain valid volumes with a usable title."""
        search_value = query.title or query.author or query.isbn
        if query.title is not None:
            google_query = f"intitle:{search_value}"
        elif query.author is not None:
            google_query = f"inauthor:{search_value}"
        else:
            google_query = f"isbn:{search_value}"

        try:
            response = await self._client.get(
                GOOGLE_BOOKS_VOLUMES_URL,
                params={
                    "q": google_query,
                    "startIndex": start_index,
                    "maxResults": max_results,
                },
            )
        except httpx.TimeoutException as exc:
            raise BookProviderTimeout from exc
        except httpx.RequestError as exc:
            raise BookProviderTransportError from exc

        if response.status_code == 429 or self._is_quota_response(response):
            raise BookProviderQuotaExceeded
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BookProviderTransportError from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BookProviderInvalidResponse from exc
        if not isinstance(payload, dict):
            raise BookProviderInvalidResponse

        total_items = payload.get("totalItems")
        raw_items = payload.get("items", [])
        if (
            not isinstance(total_items, int)
            or isinstance(total_items, bool)
            or total_items < 0
            or not isinstance(raw_items, list)
        ):
            raise BookProviderInvalidResponse

        books = [
            book
            for raw_item in raw_items
            if (book := self._normalize_volume(raw_item)) is not None
        ]
        return books, total_items

    async def get_by_id(self, provider_id: str) -> ExternalBookRead | None:
        """Fetch and normalize one volume, returning None only for HTTP 404."""
        try:
            response = await self._client.get(
                f"{GOOGLE_BOOKS_VOLUMES_URL}/{quote(provider_id, safe='')}"
            )
        except httpx.TimeoutException as exc:
            raise BookProviderTimeout from exc
        except httpx.RequestError as exc:
            raise BookProviderTransportError from exc

        if response.status_code == 404:
            return None
        if response.status_code == 429 or self._is_quota_response(response):
            raise BookProviderQuotaExceeded
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BookProviderTransportError from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BookProviderInvalidResponse from exc
        if not isinstance(payload, dict):
            raise BookProviderInvalidResponse

        book = self._normalize_volume(payload)
        if book is None or book.provider_id != provider_id:
            raise BookProviderInvalidResponse
        return book

    @staticmethod
    def _is_quota_response(response: httpx.Response) -> bool:
        """Recognize quota errors that Google may report with HTTP 403."""
        if response.status_code != 403:
            return False
        try:
            payload = response.json()
        except ValueError:
            return False
        if not isinstance(payload, dict):
            return False
        error = payload.get("error")
        reasons = []
        if isinstance(error, dict):
            entries = error.get("errors", [])
            if isinstance(entries, list):
                reasons = [
                    entry.get("reason") for entry in entries if isinstance(entry, dict)
                ]
        return any(
            isinstance(reason, str) and reason in QUOTA_ERROR_REASONS
            for reason in reasons
        )

    @classmethod
    def _normalize_volume(cls, item: Any) -> ExternalBookRead | None:
        """Convert a partially populated volume, skipping unusable records."""
        if not isinstance(item, dict):
            return None
        provider_id = cls._text(item.get("id"))
        volume_info = item.get("volumeInfo")
        if provider_id is None or not isinstance(volume_info, dict):
            return None

        title = cls._text(volume_info.get("title"))
        if title is None:
            return None

        identifiers = volume_info.get("industryIdentifiers")
        identifier_map = {}
        if isinstance(identifiers, list):
            for identifier in identifiers:
                if isinstance(identifier, dict):
                    kind = identifier.get("type")
                    value = cls._text(identifier.get("identifier"))
                    if (
                        isinstance(kind, str)
                        and kind in {"ISBN_10", "ISBN_13"}
                        and value is not None
                    ):
                        identifier_map.setdefault(kind, value)

        image_links = volume_info.get("imageLinks")
        if not isinstance(image_links, dict):
            image_links = {}
        page_count = volume_info.get("pageCount")
        if (
            not isinstance(page_count, int)
            or isinstance(page_count, bool)
            or page_count < 0
        ):
            page_count = None

        return ExternalBookRead(
            provider_id=provider_id,
            title=title,
            authors=cls._text_list(volume_info.get("authors")),
            publisher=cls._text(volume_info.get("publisher")),
            published_date=cls._text(volume_info.get("publishedDate")),
            description=cls._text(volume_info.get("description")),
            isbn_10=identifier_map.get("ISBN_10"),
            isbn_13=identifier_map.get("ISBN_13"),
            page_count=page_count,
            categories=cls._text_list(volume_info.get("categories")),
            language=cls._text(volume_info.get("language")),
            thumbnail_url=cls._text(image_links.get("thumbnail")),
            info_link=cls._text(volume_info.get("infoLink")),
            preview_link=cls._text(volume_info.get("previewLink")),
        )

    @staticmethod
    def _text(value: Any) -> str | None:
        """Return a non-empty trimmed string, or None for malformed values."""
        return value.strip() if isinstance(value, str) and value.strip() else None

    @classmethod
    def _text_list(cls, value: Any) -> list[str]:
        """Keep valid non-empty strings from an optionally malformed list."""
        if not isinstance(value, list):
            return []
        return [text for item in value if (text := cls._text(item)) is not None]
