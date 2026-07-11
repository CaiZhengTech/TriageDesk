import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from triagedesk.config import settings

integration = pytest.mark.skipif(
    not settings.test_database_url, reason="TEST_DATABASE_URL not set"
)


@pytest.fixture()
def test_db():
    from triagedesk.db import make_engine

    engine = make_engine(settings.test_database_url)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestSession()
    yield session
    session.rollback()
    # keep the shared test branch clean between tests
    session.execute(text("TRUNCATE spans, runs, kb_docs, tickets RESTART IDENTITY CASCADE"))
    session.commit()
    session.close()
    engine.dispose()
