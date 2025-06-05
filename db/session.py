from contextlib import contextmanager
from typing import Generator
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from core.dependencies import get_settings
from core.settings import Settings
from db.models import Base

# Global engine singleton
_engine = None


def get_engine(settings: Settings = Depends(get_settings)):
    """Get or create SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False, future=True)
    return _engine


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False)


def get_db(
    settings: Settings = Depends(get_settings),
) -> Generator[Session, None, None]:
    """FastAPI dependency that yields database sessions."""
    engine = get_engine(settings)
    SessionLocal.configure(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# For use in scripts and tests
@contextmanager
def get_session_context(settings: Settings = None) -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    if settings is None:
        settings = Settings()
    engine = get_engine(settings)
    SessionLocal.configure(bind=engine)
    with SessionLocal() as session:
        yield session


def init_db(settings: Settings) -> None:
    """Initialize database tables."""
    engine = get_engine(settings)
    Base.metadata.create_all(engine)


# Context manager for manual session management
@contextmanager
def manual_session(settings: Settings) -> Generator[Session, None, None]:
    """Context manager for manual session management."""
    engine = get_engine(settings)
    SessionLocal.configure(bind=engine)
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
