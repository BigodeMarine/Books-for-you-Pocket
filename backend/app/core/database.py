"""SQLAlchemy engine, declarative base, and session dependency."""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

engine: Engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for future SQLAlchemy models."""


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and always close it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
