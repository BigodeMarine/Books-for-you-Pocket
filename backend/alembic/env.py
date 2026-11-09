"""Alembic environment configured from the application's central settings."""

from alembic import context
from app.core.config import get_settings
from app.core.database import Base, engine

settings = get_settings()

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations using a URL without creating a database connection."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using an SQLAlchemy engine and a live connection."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
