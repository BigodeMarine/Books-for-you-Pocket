"""SQLAlchemy model for intellectual works in the catalog."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.associations import work_authors, work_genres
from app.models.enums import WorkType, database_enum

if TYPE_CHECKING:
    from app.models.author import Author
    from app.models.edition import Edition
    from app.models.genre import Genre


class Work(Base):
    """An intellectual work, independent of any particular edition."""

    __tablename__ = "works"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    work_type: Mapped[WorkType] = mapped_column(database_enum(WorkType, "work_type"), nullable=False)
    original_language: Mapped[str | None] = mapped_column(String(35))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    editions: Mapped[list["Edition"]] = relationship(
        back_populates="work", cascade="all, delete-orphan", passive_deletes=True
    )
    authors: Mapped[list["Author"]] = relationship(
        secondary=work_authors, back_populates="works"
    )
    genres: Mapped[list["Genre"]] = relationship(
        secondary=work_genres, back_populates="works"
    )
