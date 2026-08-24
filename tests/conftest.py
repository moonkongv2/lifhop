from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import app
from app.models.base import Base


TEST_DATABASE_URL = (
    "postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test"
)

test_engine = create_engine(TEST_DATABASE_URL)


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()

    session = Session(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(
    db_session: Session,
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
