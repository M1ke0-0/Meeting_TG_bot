"""
Base repository class for async database operations.

Provides common CRUD operations for all repositories.
"""
from typing import TypeVar, Generic, Any, Type, Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db_config import Base

T = TypeVar("T", bound=Base)


class AsyncRepository(Generic[T]):
    """
    Base async repository with common database operations.
    
    Usage:
        class UserRepository(AsyncRepository[User]):
            def __init__(self, session: AsyncSession):
                super().__init__(User, session)
    """
    
    def __init__(self, model: Type[T], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def get(self, id: Any) -> Optional[T]:
        """Get entity by primary key."""
        return await self.session.get(self.model, id)
    
    async def get_all(self) -> List[T]:
        """Get all entities."""
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())
    
    async def add(self, entity: T) -> T:
        """Add new entity."""
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity
    
    async def add_all(self, entities: List[T]) -> List[T]:
        """Add multiple entities."""
        self.session.add_all(entities)
        await self.session.flush()
        return entities
    
    async def delete(self, entity: T) -> None:
        """Delete entity."""
        await self.session.delete(entity)
        await self.session.flush()
    
    async def commit(self) -> None:
        """Commit current transaction."""
        await self.session.commit()
    
    async def rollback(self) -> None:
        """Rollback current transaction."""
        await self.session.rollback()
