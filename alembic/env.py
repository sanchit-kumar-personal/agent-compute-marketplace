from logging.config import fileConfig
import os

from alembic import context
from sqlmodel import SQLModel, create_engine

# Import settings with fallback
try:
    from core.settings import Settings

    settings = Settings()  # It's okay to create settings here since this is a CLI tool
except Exception:
    from pydantic_settings import BaseSettings

    class FallbackSettings(BaseSettings):
        DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./test.db")
        DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    settings = FallbackSettings()

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the database URL in the alembic.ini file
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Enable type comparison for better migrations
        compare_server_default=True,  # Enable server default comparison
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Create engine with appropriate configuration for database type
    if settings.DATABASE_URL.startswith("postgresql"):
        connectable = create_engine(
            settings.DATABASE_URL,
            echo=getattr(settings, "DEBUG", False),
            future=True,
            pool_pre_ping=True,
        )
    else:
        # SQLite fallback
        connectable = create_engine(
            settings.DATABASE_URL, echo=getattr(settings, "DEBUG", False), future=True
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Enable type comparison for better migrations
            compare_server_default=True,  # Enable server default comparison
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
