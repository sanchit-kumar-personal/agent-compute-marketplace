from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from core.dependencies import get_settings
from core.settings import Settings
from db.models import Base

# Global engine singletons
_engine = None
_async_engine = None


def reset_engines():
    """Reset global engine singletons. Used for testing."""
    global _engine, _async_engine
    if _engine:
        _engine.dispose()
        _engine = None
    if _async_engine:
        _async_engine.dispose()
        _async_engine = None


def get_engine(settings: Settings = Depends(get_settings)):
    """Get or create SQLAlchemy engine for synchronous operations."""
    global _engine
    if _engine is None:
        # Configure engine based on database type
        if settings.DATABASE_URL.startswith("postgresql"):
            _engine = create_engine(
                settings.DATABASE_URL,
                future=True,
                poolclass=QueuePool,
                pool_size=settings.DATABASE_POOL_SIZE,
                max_overflow=settings.DATABASE_MAX_OVERFLOW,
                pool_timeout=settings.DATABASE_POOL_TIMEOUT,
                pool_recycle=settings.DATABASE_POOL_RECYCLE,
                pool_pre_ping=True,  # Verify connections before use
            )
        else:
            # SQLite fallback for tests
            from sqlalchemy.pool import StaticPool

            connect_args = (
                {"check_same_thread": False}
                if settings.DATABASE_URL.startswith("sqlite")
                else {}
            )
            _engine = create_engine(
                settings.DATABASE_URL,
                future=True,
                connect_args=connect_args,
                poolclass=(
                    StaticPool if settings.DATABASE_URL.startswith("sqlite") else None
                ),
            )
    return _engine


def get_async_engine(settings: Settings = Depends(get_settings)):
    """Get or create async SQLAlchemy engine for PostgreSQL."""
    global _async_engine
    if _async_engine is None and settings.DATABASE_URL.startswith("postgresql"):
        # Convert sync URL to async URL
        async_url = settings.DATABASE_URL.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        _async_engine = create_async_engine(
            async_url,
            future=True,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_pre_ping=True,
        )
    return _async_engine


# Session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False)
AsyncSessionLocal = async_sessionmaker(expire_on_commit=False)


def get_db():
    settings = Settings()
    engine = get_engine(settings)
    SessionLocal.configure(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_dependency():
    """Get database session and store in request state for middleware reuse."""
    settings = Settings()
    engine = get_engine(settings)
    SessionLocal.configure(bind=engine)
    db = SessionLocal()
    try:
        # Store in request state so middleware can reuse it
        yield db
    finally:
        db.close()


# Add this after db = SessionLocal() add:
def store_db_in_request_state(request, db):
    """Store database session in request state for middleware access."""
    request.state.db = db


async def get_async_db(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields async database sessions."""
    async_engine = get_async_engine(settings)
    if async_engine is None:
        raise RuntimeError(
            "Async engine not available. PostgreSQL required for async operations."
        )

    AsyncSessionLocal.configure(bind=async_engine)
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


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


@asynccontextmanager
async def get_async_session_context(
    settings: Settings = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database sessions."""
    if settings is None:
        settings = Settings()
    async_engine = get_async_engine(settings)
    if async_engine is None:
        raise RuntimeError(
            "Async engine not available. PostgreSQL required for async operations."
        )

    AsyncSessionLocal.configure(bind=async_engine)
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def init_db(settings: Settings) -> None:
    """Initialize database tables."""
    engine = get_engine(settings)
    Base.metadata.create_all(engine)


async def init_async_db(settings: Settings) -> None:
    """Initialize database tables asynchronously."""
    async_engine = get_async_engine(settings)
    if async_engine is None:
        # Fall back to sync initialization
        init_db(settings)
        return

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
