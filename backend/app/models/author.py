"""SQLAlchemy model for authors associated with catalog works."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.associations import work_authors

if TYPE_CHECKING:
    from app.models.work import Work


class Author(Base):
    """An author associated with one or more works."""

    __tablename__ = "authors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    works: Mapped[list["Work"]] = relationship(secondary=work_authors, back_populates="authors")
