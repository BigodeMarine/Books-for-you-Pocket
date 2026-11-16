"""Schema and relationship tests for the catalog and offer models."""

from sqlalchemy import CheckConstraint, Numeric, UniqueConstraint, Uuid, inspect

from app.core.database import Base
from app.models import (
    Author,
    AvailabilityStatus,
    Edition,
    EditionExternalIdentifier,
    EditionFormat,
    ExternalIdentifierSource,
    Genre,
    MetadataSource,
    Offer,
    OfferCondition,
    PriceHistory,
    Seller,
    Work,
    WorkType,
)


def test_models_register_all_expected_tables() -> None:
    """Importing the model package registers all entity and association tables."""
    assert set(Base.metadata.tables) == {
        "works",
        "editions",
        "edition_external_identifiers",
        "authors",
        "genres",
        "sellers",
        "offers",
        "price_history",
        "work_authors",
        "work_genres",
    }


def test_relationships_have_expected_cardinality_and_ownership() -> None:
    """Relationships connect works to their editions, contributors, and offers."""
    assert inspect(Work).relationships["editions"].uselist is True
    assert inspect(Edition).relationships["work"].uselist is False
    assert inspect(Edition).relationships["external_identifiers"].uselist is True
    assert inspect(EditionExternalIdentifier).relationships["edition"].uselist is False
    assert inspect(Work).relationships["authors"].uselist is True
    assert inspect(Author).relationships["works"].uselist is True
    assert inspect(Work).relationships["genres"].uselist is True
    assert inspect(Genre).relationships["works"].uselist is True
    assert inspect(Edition).relationships["offers"].uselist is True
    assert inspect(Offer).relationships["edition"].uselist is False
    assert inspect(Seller).relationships["offers"].uselist is True
    assert inspect(Offer).relationships["seller"].uselist is False
    assert inspect(Offer).relationships["price_history"].uselist is True
    assert inspect(PriceHistory).relationships["offer"].uselist is False
    assert inspect(Offer).relationships["price_history"].passive_deletes == "all"
    assert inspect(Edition).relationships["offers"].passive_deletes == "all"
    assert (
        inspect(Edition).relationships["external_identifiers"].passive_deletes is True
    )
    assert inspect(Seller).relationships["offers"].passive_deletes == "all"
    assert inspect(Work).relationships["authors"].secondary.name == "work_authors"
    assert inspect(Work).relationships["genres"].secondary.name == "work_genres"
    assert "authors" not in inspect(Edition).relationships
    assert "genres" not in inspect(Edition).relationships


def test_model_primary_keys_use_uuid() -> None:
    """All entity primary keys use SQLAlchemy's UUID type."""
    for model in (
        Work,
        Edition,
        EditionExternalIdentifier,
        Author,
        Genre,
        Seller,
        Offer,
        PriceHistory,
    ):
        primary_key = next(iter(model.__table__.primary_key.columns))
        assert isinstance(primary_key.type, Uuid)


def test_price_fields_use_decimal_numeric_type() -> None:
    """Offer and history money fields use fixed-precision numeric columns."""
    for table, field in (
        (Offer.__table__, "price"),
        (Offer.__table__, "original_price"),
        (PriceHistory.__table__, "price"),
        (PriceHistory.__table__, "original_price"),
    ):
        column_type = table.c[field].type
        assert isinstance(column_type, Numeric)
        assert (column_type.precision, column_type.scale) == (10, 2)


def test_enum_values_match_the_catalog_contract() -> None:
    """Enums expose the expected stable values and use validated check constraints."""
    assert {member.value for member in WorkType} == {"book", "manga", "comic"}
    assert {member.value for member in EditionFormat} == {
        "paperback",
        "hardcover",
        "ebook",
        "audiobook",
        "digital",
        "other",
    }
    assert {member.value for member in MetadataSource} == {
        "google_books",
        "open_library",
        "manual",
    }
    assert {member.value for member in ExternalIdentifierSource} == {
        "google_books",
        "open_library",
    }
    assert "manual" not in {member.value for member in ExternalIdentifierSource}
    assert {member.value for member in OfferCondition} == {"new", "used"}
    assert {member.value for member in AvailabilityStatus} == {
        "in_stock",
        "out_of_stock",
        "preorder",
        "unknown",
    }

    for table, field in (
        (Work.__table__, "work_type"),
        (Edition.__table__, "format"),
        (Edition.__table__, "metadata_source"),
        (Offer.__table__, "condition"),
        (Offer.__table__, "availability_status"),
        (PriceHistory.__table__, "availability_status"),
    ):
        enum_type = table.c[field].type
        assert enum_type.native_enum is False
        assert enum_type.create_constraint is True
        assert enum_type.validate_strings is True

    external_source_type = EditionExternalIdentifier.__table__.c.source.type
    assert external_source_type.native_enum is True
    assert external_source_type.name == "external_identifier_source"
    assert external_source_type.create_constraint is True
    assert external_source_type.validate_strings is True


def test_unique_constraints_cover_isbns_and_slugs() -> None:
    """ISBNs and public slugs have database uniqueness constraints."""
    assert _unique_constraint_exists(Edition, "isbn_10")
    assert _unique_constraint_exists(Edition, "isbn_13")
    assert _unique_constraint_exists(EditionExternalIdentifier, "source", "external_id")
    assert _unique_constraint_exists(Genre, "slug")
    assert _unique_constraint_exists(Seller, "slug")


def test_money_constraints_reject_negative_values() -> None:
    """Offer and history tables constrain prices to nonnegative values."""
    for table in (Offer.__table__, PriceHistory.__table__):
        constraints = [
            constraint
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        ]
        expressions = {str(constraint.sqltext) for constraint in constraints}
        assert "price >= 0" in expressions
        assert "original_price IS NULL OR original_price >= 0" in expressions


def test_indexes_and_foreign_keys_cover_common_joins() -> None:
    """Foreign key joins and price history lookup have supporting indexes."""
    assert "ix_editions_work_id" in {index.name for index in Edition.__table__.indexes}
    assert "ix_offers_edition_id" in {index.name for index in Offer.__table__.indexes}
    assert "ix_offers_seller_id" in {index.name for index in Offer.__table__.indexes}
    assert "ix_price_history_offer_captured_at" in {
        index.name for index in PriceHistory.__table__.indexes
    }
    assert {
        column.name
        for column in Base.metadata.tables["work_authors"].primary_key.columns
    } == {"work_id", "author_id"}
    assert {
        column.name
        for column in Base.metadata.tables["work_genres"].primary_key.columns
    } == {"work_id", "genre_id"}

    edition_work_fk = next(iter(Edition.__table__.c.work_id.foreign_keys))
    assert edition_work_fk.target_fullname == "works.id"
    assert edition_work_fk.ondelete == "CASCADE"

    for field, target in (("edition_id", "editions.id"), ("seller_id", "sellers.id")):
        foreign_key = next(iter(Offer.__table__.c[field].foreign_keys))
        assert foreign_key.target_fullname == target
        assert foreign_key.ondelete == "RESTRICT"

    history_offer_fk = next(iter(PriceHistory.__table__.c.offer_id.foreign_keys))
    assert history_offer_fk.target_fullname == "offers.id"
    assert history_offer_fk.ondelete == "RESTRICT"

    external_identifier_edition_fk = next(
        iter(EditionExternalIdentifier.__table__.c.edition_id.foreign_keys)
    )
    assert external_identifier_edition_fk.target_fullname == "editions.id"
    assert external_identifier_edition_fk.ondelete == "CASCADE"
    assert "ix_edition_external_identifiers_edition_id" in {
        index.name for index in EditionExternalIdentifier.__table__.indexes
    }


def test_edition_stores_optional_cover_and_metadata_provenance() -> None:
    """Edition cover and external metadata fields remain optional and edition-scoped."""
    for field in (
        "cover_url",
        "metadata_source",
        "metadata_external_id",
        "metadata_updated_at",
    ):
        assert Edition.__table__.c[field].nullable is True


def _unique_constraint_exists(model: type, *fields: str) -> bool:
    """Return whether a mapped model declares a unique constraint for columns."""
    return any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == set(fields)
        for constraint in model.__table__.constraints
    )
