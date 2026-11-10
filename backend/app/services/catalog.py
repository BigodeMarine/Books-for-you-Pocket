"""Database queries for catalog resources."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Author, Genre, Work, WorkType


def list_works(
    session: Session,
    q: str | None = None,
    author_id: UUID | None = None,
    genre_id: UUID | None = None,
    work_type: WorkType | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Work], int]:
    """List a page of works matching the supplied filters and total count."""
    filters = []
    query = q.strip() if q else ""
    if query:
        filters.append(Work.title.ilike(f"%{query}%"))
    if author_id is not None:
        filters.append(Work.authors.any(Author.id == author_id))
    if genre_id is not None:
        filters.append(Work.genres.any(Genre.id == genre_id))
    if work_type is not None:
        filters.append(Work.work_type == work_type)

    total = session.scalar(select(func.count()).select_from(Work).where(*filters)) or 0
    statement = (
        select(Work)
        .where(*filters)
        .order_by(Work.title.asc(), Work.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    works = list(session.scalars(statement).all())
    return works, total


def get_work_by_id(session: Session, work_id: UUID) -> Work | None:
    """Return a work with its catalog relationships loaded, if it exists."""
    statement = (
        select(Work)
        .where(Work.id == work_id)
        .options(
            selectinload(Work.authors),
            selectinload(Work.genres),
            selectinload(Work.editions),
        )
    )
    return session.scalar(statement)
