from contextlib import contextmanager
from typing import Generator

from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine

from core.settings import Settings
from main import get_settings

# Create SQLAlchemy engine
_engine = None


def get_engine(settings: Settings = Depends(get_settings)):
    """Get or create SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL)
    return _engine


def get_session(
    settings: Settings = Depends(get_settings),
) -> Generator[Session, None, None]:
    """Dependency that yields database sessions."""
    engine = get_engine(settings)
    with Session(engine) as session:
        yield session


# For use in scripts and tests
@contextmanager
def get_session_context(settings: Settings = None) -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    if settings is None:
        settings = Settings()
    engine = get_engine(settings)
    with Session(engine) as session:
        yield session


def init_db(settings: Settings) -> None:
    """Initialize database tables."""
    engine = get_engine(settings)
    SQLModel.metadata.create_all(engine)


# Context manager for manual session management
@contextmanager
def manual_session(settings: Settings) -> Generator[Session, None, None]:
    """Context manager for manual session management."""
    engine = get_engine(settings)
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
