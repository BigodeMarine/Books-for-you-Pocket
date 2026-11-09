"""Unit tests for database settings, engine setup, sessions, and Alembic."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import URL

from app.core import database
from app.core.config import PROJECT_ROOT, Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    """Keep cached settings isolated between tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_load_environment_and_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings load PostgreSQL values from the environment and apply defaults."""
    env_file = Settings.model_config["env_file"]
    assert env_file == PROJECT_ROOT / ".env"
    assert Path(env_file).is_absolute()

    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-secret")
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    settings = get_settings()

    assert settings.postgres_db == "test_db"
    assert settings.postgres_user == "test_user"
    assert settings.postgres_host == "localhost"
    assert settings.postgres_port == 5433
    assert str(settings.postgres_password) == "**********"


def test_database_url_uses_psycopg_and_hides_password() -> None:
    """The SQLAlchemy URL includes expected connection details but masks its secret."""
    settings = Settings(
        _env_file=None,
        postgres_db="catalog_db",
        postgres_user="catalog_user",
        postgres_password="top-secret",
        postgres_host="db.example.test",
        postgres_port=5544,
    )

    url = settings.database_url

    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg"
    assert url.render_as_string(hide_password=True) == (
        "postgresql+psycopg://catalog_user:***@db.example.test:5544/catalog_db"
    )
    assert "top-secret" not in str(url)
    assert "top-secret" not in repr(url)


def test_engine_has_pre_ping_without_connecting() -> None:
    """The global engine enables pre-ping without opening a database connection."""
    assert database.engine.pool._pre_ping is True
    assert database.engine.pool.checkedout() == 0
    assert database.SessionLocal.kw["autoflush"] is False
    assert database.SessionLocal.kw["autocommit"] is False


def test_get_db_closes_session_after_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The yielded session is closed even when the request raises an exception."""

    class FakeSession:
        closed = False

        def close(self) -> None:
            self.closed = True

    session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    dependency = database.get_db()

    assert next(dependency) is session
    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))
    assert session.closed is True


def test_alembic_configuration_uses_expected_script_directory() -> None:
    """Alembic can load its script directory and migration template."""
    backend_dir = PROJECT_ROOT / "backend"
    config = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert Path(script.dir) == backend_dir / "alembic"
    assert (backend_dir / "alembic" / "env.py").is_file()
    assert (backend_dir / "alembic" / "versions").is_dir()
    assert (backend_dir / "alembic" / "script.py.mako").is_file()
