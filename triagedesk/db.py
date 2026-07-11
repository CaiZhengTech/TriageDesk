from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from triagedesk.config import settings


def _driver_url(url: str) -> str:
    # Neon hands out postgresql://; force the psycopg3 driver.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def make_engine(url: str):
    return create_engine(_driver_url(url), pool_pre_ping=True)


engine = make_engine(settings.database_url) if settings.database_url else None
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False) if engine else None


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
