"""Asynchronous PostgreSQL engine and request-scoped sessions."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings


def _async_database_url(url: str) -> str:
    """Normalize a standard PostgreSQL URL for SQLAlchemy's asyncpg driver."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


_session_factory: async_sessionmaker[AsyncSession] | None = None
if settings.database_url is not None:
    _engine = create_async_engine(
        _async_database_url(settings.database_url.get_secret_value()),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"statement_cache_size": 0},
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when database-backed work is attempted without a URL."""


@asynccontextmanager
async def database_session() -> AsyncIterator[AsyncSession]:
    """Yield a transaction-scoped session for HTTP, MCP, and maintenance jobs."""
    if _session_factory is None:
        raise DatabaseNotConfiguredError("Database persistence is not configured.")
    async with _session_factory() as session, session.begin():
        yield session


async def get_database_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session or report missing configuration."""
    try:
        async with database_session() as session:
            yield session
    except DatabaseNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]
