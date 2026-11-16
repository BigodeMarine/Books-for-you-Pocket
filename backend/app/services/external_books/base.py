"""Provider contract and normalized errors for external book searches."""

from typing import Protocol

from app.schemas.external_books import ExternalBookRead, ExternalBookSearchQuery


class BookProviderError(Exception):
    """Base error for failures while querying a book provider."""


class BookProviderTimeout(BookProviderError):
    """The provider did not respond within the configured timeout."""


class BookProviderTransportError(BookProviderError):
    """The provider could not be reached or returned an unusable HTTP response."""


class BookProviderInvalidResponse(BookProviderError):
    """The provider response could not be interpreted safely."""


class BookProviderQuotaExceeded(BookProviderError):
    """The provider rejected a request because its quota was exceeded."""


class BookProvider(Protocol):
    """Async contract implemented by external book search providers."""

    async def search(
        self,
        query: ExternalBookSearchQuery,
        *,
        start_index: int,
        max_results: int,
    ) -> tuple[list[ExternalBookRead], int]:
        """Return normalized results and the provider's total result count."""
