import os
from pathlib import Path

from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv_if_present() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _database_identity(url: str) -> tuple[str | None, str | None]:
    parsed = make_url(url)
    host = parsed.host.lower() if parsed.host else None
    if host:
        host = host.replace("-pooler.", ".")
    return host, parsed.database


def _configure_test_database() -> str:
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is required. Set it to a dedicated PostgreSQL test database; "
            "tests will not fall back to DATABASE_URL or SQLite."
        )

    try:
        test_database = make_url(test_url)
    except Exception as exc:
        raise RuntimeError("TEST_DATABASE_URL is not a valid database URL.") from exc

    if test_database.get_backend_name() != "postgresql":
        raise RuntimeError("TEST_DATABASE_URL must point to PostgreSQL.")

    production_url = os.getenv("DATABASE_URL")
    if production_url:
        try:
            if _database_identity(test_url) == _database_identity(production_url):
                raise RuntimeError(
                    "TEST_DATABASE_URL resolves to the same PostgreSQL host and database as DATABASE_URL."
                )
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError("DATABASE_URL could not be safely compared with TEST_DATABASE_URL.") from exc

    os.environ["DATABASE_URL"] = test_url
    os.environ["ENVIRONMENT"] = "production"
    os.environ["API_KEY"] = "test-api-key"
    return test_url


_load_dotenv_if_present()
_TEST_DATABASE_URL = _configure_test_database()
_TEST_DATABASE = make_url(_TEST_DATABASE_URL)

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.database import SessionLocal, engine, get_db
from app.main import app
from app.models import Booking, BookingAttempt, IdempotencyRecord, Slot


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_database():
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Tests require PostgreSQL; refusing to run against a non-PostgreSQL engine.")

    with engine.connect() as connection:
        actual_database = connection.exec_driver_sql("SELECT current_database()").scalar_one()
    if actual_database != _TEST_DATABASE.database:
        raise RuntimeError("Connected PostgreSQL database does not match TEST_DATABASE_URL.")

    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")


def _clear_test_data() -> None:
    with SessionLocal.begin() as session:
        session.execute(delete(BookingAttempt))
        session.execute(delete(IdempotencyRecord))
        session.execute(delete(Booking))
        session.execute(delete(Slot))


@pytest.fixture(autouse=True)
def _isolated_test_data(_migrate_test_database):
    _clear_test_data()
    try:
        yield
    finally:
        _clear_test_data()


@pytest.fixture()
def client():
    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
