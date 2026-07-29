import os
from collections.abc import Generator
from pathlib import Path

TEST_DB = Path("/tmp/medialens-test.db")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["MEDIALENS_DATABASE_URL"] = f"sqlite:///{TEST_DB}"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import SessionLocal, engine, get_db
from app.main import app


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
