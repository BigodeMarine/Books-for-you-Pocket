"""HTTP endpoints for importing external book metadata into the catalog."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.external_books import get_book_provider
from app.core.database import get_db
from app.schemas.catalog_imports import (
    GoogleBooksImportRequest,
    GoogleBooksImportResponse,
)
from app.services.external_books.base import (
    BookProvider,
    BookProviderError,
    BookProviderQuotaExceeded,
    BookProviderTimeout,
)
from app.services.google_books_import import (
    GoogleBooksVolumeNotFound,
    ImportDestinationConflict,
    ImportEditionFormatRequired,
    ImportLanguageRequired,
    ImportProviderIdInvalid,
    ImportProviderIdMismatch,
    ImportWorkNotFound,
    ensure_work_target_compatible,
    fetch_google_books_volume,
    find_edition_by_google_books_id,
    persist_google_books_import,
)

router = APIRouter(prefix="/api/v1/catalog/imports", tags=["catalog-imports"])


@router.post(
    "/google-books",
    response_model=GoogleBooksImportResponse,
    status_code=201,
)
async def import_google_books_volume(
    payload: GoogleBooksImportRequest,
    session: Annotated[Session, Depends(get_db)],
    provider: Annotated[BookProvider, Depends(get_book_provider)],
) -> GoogleBooksImportResponse:
    """Fetch a Google Books volume and persist it in the requested work."""
    try:
        volume = await fetch_google_books_volume(provider, payload.provider_id)
    except GoogleBooksVolumeNotFound:
        raise HTTPException(
            status_code=404, detail="Google Books volume not found"
        ) from None
    except ImportProviderIdInvalid:
        raise HTTPException(
            status_code=422, detail="Invalid Google Books provider ID"
        ) from None
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

    try:
        with session.begin():
            existing_edition = find_edition_by_google_books_id(
                session, payload.provider_id.strip()
            )
            if existing_edition is not None:
                ensure_work_target_compatible(payload.work_target, existing_edition)
            result = persist_google_books_import(session, payload, volume)
    except ImportWorkNotFound:
        raise HTTPException(status_code=404, detail="Work not found") from None
    except ImportDestinationConflict:
        raise HTTPException(
            status_code=409, detail="Import destination conflicts with existing edition"
        ) from None
    except (ImportEditionFormatRequired, ImportLanguageRequired):
        raise HTTPException(
            status_code=422, detail="Edition format and language are required"
        ) from None
    except (ImportProviderIdInvalid, ImportProviderIdMismatch):
        raise HTTPException(
            status_code=422, detail="Invalid Google Books provider ID"
        ) from None
    except Exception:  # noqa: BLE001 - the transaction must roll back for every persistence failure.
        raise HTTPException(status_code=500, detail="Catalog import failed") from None

    response = GoogleBooksImportResponse(
        work_id=result.work_id,
        edition_id=result.edition_id,
        work_created=result.work_created,
        edition_created=result.edition_created,
        warnings=list(result.warnings),
    )
    if result.work_created or result.edition_created:
        return response
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))
