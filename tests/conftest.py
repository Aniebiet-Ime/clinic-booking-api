import os

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_clinic.db")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, get_db
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    def override_get_db():
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)
