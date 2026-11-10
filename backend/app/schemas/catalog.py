"""Response schemas for catalog resources."""

from datetime import date, datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import EditionFormat, MetadataSource, WorkType

T = TypeVar("T")


class AuthorRead(BaseModel):
    """Public representation of a catalog author."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class GenreRead(BaseModel):
    """Public representation of a catalog genre."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str


class EditionRead(BaseModel):
    """Public representation of an edition and its catalog metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    isbn_10: str | None
    isbn_13: str | None
    publisher: str | None
    language: str
    format: EditionFormat
    volume_number: int | None
    publication_date: date | None
    page_count: int | None
    cover_url: str | None
    metadata_source: MetadataSource | None
    metadata_external_id: str | None
    metadata_updated_at: datetime | None


class WorkListItemRead(BaseModel):
    """Compact representation of a work for catalog listings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    subtitle: str | None
    work_type: WorkType
    original_language: str | None


class WorkDetailRead(WorkListItemRead):
    """Detailed representation of a work and its editions, authors, and genres."""

    description: str | None
    created_at: datetime
    updated_at: datetime
    editions: list[EditionRead]
    authors: list[AuthorRead]
    genres: list[GenreRead]


class PaginatedResponse(BaseModel, Generic[T]):
    """A page of typed results and its pagination metadata."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
