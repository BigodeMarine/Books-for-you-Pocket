"""SQLAlchemy model for catalog genres."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.associations import work_genres

if TYPE_CHECKING:
    from app.models.work import Work


class Genre(Base):
    """A genre that can be assigned to multiple works."""

    __tablename__ = "genres"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    works: Mapped[list["Work"]] = relationship(secondary=work_genres, back_populates="genres")
