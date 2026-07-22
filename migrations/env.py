"""Alembic migration environment configuration."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from backend.app.config import settings
from backend.app.tables import Base

configuration = context.config
if configuration.config_file_name:
    fileConfig(configuration.config_file_name)
if settings.database_url is None:
    raise RuntimeError("BLOG_DATABASE_URL is required to run migrations.")
database_url = settings.database_url.get_secret_value()
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    database_url = database_url.replace("+asyncpg", "+psycopg")
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a synchronous PostgreSQL connection."""
    connectable = create_engine(database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
