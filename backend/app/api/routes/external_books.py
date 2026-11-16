"""HTTP endpoint for searching external book catalogs."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.schemas.catalog import PaginatedResponse
from app.schemas.external_books import ExternalBookRead, ExternalBookSearchQuery
from app.services.external_books.base import (
    BookProvider,
    BookProviderError,
    BookProviderQuotaExceeded,
    BookProviderTimeout,
)
from app.services.external_books.google_books import GoogleBooksProvider

router = APIRouter(prefix="/api/v1/external-books", tags=["external-books"])


def get_book_provider(request: Request) -> BookProvider:
    """Build the configured provider around the lifespan-managed HTTP client."""
    client: httpx.AsyncClient = request.app.state.google_books_client
    return GoogleBooksProvider(client)


@router.get("/search", response_model=PaginatedResponse[ExternalBookRead])
async def search_external_books(
    query: Annotated[ExternalBookSearchQuery, Query()],
    provider: Annotated[BookProvider, Depends(get_book_provider)],
) -> PaginatedResponse[ExternalBookRead]:
    """Search Google Books by exactly one criterion and return normalized results."""
    start_index = (query.page - 1) * query.page_size
    try:
        books, total = await provider.search(
            query,
            start_index=start_index,
            max_results=query.page_size,
        )
    except BookProviderTimeout:
        raise HTTPException(status_code=504, detail="Book provider timed out") from None
    except BookProviderQuotaExceeded:
        raise HTTPException(
            status_code=503, detail="Book provider quota exceeded"
        ) from None
    except BookProviderError:
        raise HTTPException(
            status_code=502, detail="Book provider request failed"
        ) from None

    total_pages = (total + query.page_size - 1) // query.page_size if total else 0
    return PaginatedResponse[ExternalBookRead](
        items=books,
        total=total,
        page=query.page,
        page_size=query.page_size,
        total_pages=total_pages,
    )
