"""SQLAlchemy model for a published edition of a work."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EditionFormat, MetadataSource, database_enum

if TYPE_CHECKING:
    from app.models.offer import Offer
    from app.models.work import Work


class Edition(Base):
    """A particular language, format, or volume of a work."""

    __tablename__ = "editions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    isbn_10: Mapped[str | None] = mapped_column(String(10), unique=True, name="isbn_10")
    isbn_13: Mapped[str | None] = mapped_column(String(13), unique=True, name="isbn_13")
    publisher: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(35), nullable=False)
    format: Mapped[EditionFormat] = mapped_column(
        database_enum(EditionFormat, "edition_format"), nullable=False
    )
    volume_number: Mapped[int | None] = mapped_column(Integer)
    publication_date: Mapped[date | None] = mapped_column(Date)
    page_count: Mapped[int | None] = mapped_column(Integer)
    cover_url: Mapped[str | None] = mapped_column(String(2048))
    metadata_source: Mapped[MetadataSource | None] = mapped_column(
        database_enum(MetadataSource, "metadata_source")
    )
    metadata_external_id: Mapped[str | None] = mapped_column(String(255))
    metadata_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    work: Mapped["Work"] = relationship(back_populates="editions")
    offers: Mapped[list["Offer"]] = relationship(back_populates="edition", passive_deletes="all")
