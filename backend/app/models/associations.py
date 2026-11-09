"""Association tables for work authors and genres."""

from sqlalchemy import Column, ForeignKey, Index, Table, Uuid

from app.core.database import Base

work_authors = Table(
    "work_authors",
    Base.metadata,
    Column("work_id", Uuid(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", Uuid(as_uuid=True), ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_work_authors_author_id", "author_id"),
)

work_genres = Table(
    "work_genres",
    Base.metadata,
    Column("work_id", Uuid(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", Uuid(as_uuid=True), ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_work_genres_genre_id", "genre_id"),
)
