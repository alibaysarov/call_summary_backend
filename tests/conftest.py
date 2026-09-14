import os

import pytest
from sqlalchemy import create_engine


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL must point to a migrated PostgreSQL database")
    engine = create_engine(url)
    assert engine.dialect.name == "postgresql"
    yield engine
    engine.dispose()


@pytest.fixture
def conn(engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()
