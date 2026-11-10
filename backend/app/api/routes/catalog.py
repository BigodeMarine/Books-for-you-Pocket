"""HTTP endpoints for catalog queries."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import WorkType
from app.schemas.catalog import PaginatedResponse, WorkDetailRead, WorkListItemRead
from app.services.catalog import get_work_by_id, list_works

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/works", response_model=PaginatedResponse[WorkListItemRead])
def read_works(
    session: Annotated[Session, Depends(get_db)],
    q: str | None = None,
    author_id: UUID | None = None,
    genre_id: UUID | None = None,
    work_type: WorkType | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[WorkListItemRead]:
    """Return a filtered and paginated list of works."""
    works, total = list_works(
        session,
        q=q,
        author_id=author_id,
        genre_id=genre_id,
        work_type=work_type,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse[WorkListItemRead](
        items=works,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/works/{work_id}", response_model=WorkDetailRead)
def read_work(
    work_id: UUID, session: Annotated[Session, Depends(get_db)]
) -> WorkDetailRead:
    """Return one work with its editions, authors, and genres."""
    work = get_work_by_id(session, work_id)
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    return WorkDetailRead.model_validate(work)
