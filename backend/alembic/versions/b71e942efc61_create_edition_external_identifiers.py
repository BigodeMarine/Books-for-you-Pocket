"""create edition external identifiers

Revision ID: b71e942efc61
Revises: 10ad61f1f29a
Create Date: 2026-11-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b71e942efc61"
down_revision: str | None = "10ad61f1f29a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

external_identifier_source = postgresql.ENUM(
    "google_books",
    "open_library",
    name="external_identifier_source",
    create_type=False,
)


def upgrade() -> None:
    """Create the provider enum and edition identifier table."""
    bind = op.get_bind()
    external_identifier_source.create(bind, checkfirst=True)

    op.create_table(
        "edition_external_identifiers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("source", external_identifier_source, nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["edition_id"], ["editions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "external_id",
            name="uq_edition_external_identifiers_source_external_id",
        ),
    )
    op.create_index(
        "ix_edition_external_identifiers_edition_id",
        "edition_external_identifiers",
        ["edition_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the edition identifier table and its PostgreSQL enum type."""
    op.drop_index(
        "ix_edition_external_identifiers_edition_id",
        table_name="edition_external_identifiers",
    )
    op.drop_table("edition_external_identifiers")
    external_identifier_source.drop(op.get_bind(), checkfirst=True)
