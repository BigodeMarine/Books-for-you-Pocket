"""SQLAlchemy model for external provider identifiers of an edition."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ExternalIdentifierSource, database_native_enum

if TYPE_CHECKING:
    from app.models.edition import Edition


class EditionExternalIdentifier(Base):
    """An external provider identifier associated with a catalog edition."""

    __tablename__ = "edition_external_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_id",
            name="uq_edition_external_identifiers_source_external_id",
        ),
        Index("ix_edition_external_identifiers_edition_id", "edition_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    edition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("editions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[ExternalIdentifierSource] = mapped_column(
        database_native_enum(ExternalIdentifierSource, "external_identifier_source"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    edition: Mapped["Edition"] = relationship(back_populates="external_identifiers")
