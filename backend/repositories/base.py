from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Generic repository interface for data access patterns."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Create a new entity."""

    @abstractmethod
    async def get_by_id(self, entity_id: int) -> T | None:
        """Retrieve an entity by primary key."""

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Update an existing entity."""

    @abstractmethod
    async def delete(self, entity_id: int) -> None:
        """Delete an entity by primary key."""


__all__ = ["BaseRepository"]
