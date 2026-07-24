from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config.settings import get_settings


class DatabaseSessionManager:
    """Manages async SQLAlchemy sessions and engine lifecycle."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, echo=False, future=True, pool_pre_ping=True)
        self._session_factory = async_sessionmaker(bind=self._engine, expire_on_commit=False)

    async def create_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._session_factory() as session:
            yield session

    async def dispose(self) -> None:
        await self._engine.dispose()


session_manager = DatabaseSessionManager(get_settings().database_url)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency helper for FastAPI routes."""
    async for session in session_manager.create_session():
        yield session


__all__ = ["DatabaseSessionManager", "get_session", "session_manager"]
