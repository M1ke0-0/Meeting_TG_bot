from typing import TypeVar, Generic, Any, Type, Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db_config import Base

T = TypeVar("T", bound=Base)


class AsyncRepository(Generic[T]):
    
    def __init__(self, model: Type[T], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def get(self, id: Any) -> Optional[T]:
        return await self.session.get(self.model, id)
    
    async def get_all(self) -> List[T]:
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())
    
    async def add(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity
    
    async def add_all(self, entities: List[T]) -> List[T]:
        self.session.add_all(entities)
        await self.session.flush()
        return entities
    
    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.flush()
    
    async def commit(self) -> None:
        await self.session.commit()
    
    async def rollback(self) -> None:
        await self.session.rollback()
