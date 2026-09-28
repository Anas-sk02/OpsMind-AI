import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Import OpsMind app settings, Base, and all models
from app.core.config import settings
from app.core.database import Base
import app.models  # Ensures all ORM models are registered on Base.metadata

config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set model metadata for autogenerate support
target_metadata = Base.metadata

# Override sqlalchemy.url with dynamic app settings (escaping % for configparser interpolation)
escaped_url = settings.SQLALCHEMY_DATABASE_URI.replace("%", "%%")
config.set_main_option("sqlalchemy.url", escaped_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.SQLALCHEMY_DATABASE_URI
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' async mode."""
    engine_kwargs = {
        "poolclass": pool.NullPool,
    }

    # Add SSL connect_args for Supabase PostgreSQL
    if not settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        if "supabase" in settings.SQLALCHEMY_DATABASE_URI:
            engine_kwargs["connect_args"] = {"ssl": True}

    connectable = create_async_engine(
        settings.SQLALCHEMY_DATABASE_URI,
        **engine_kwargs,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
