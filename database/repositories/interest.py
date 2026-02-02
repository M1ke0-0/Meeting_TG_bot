"""
Interest repository for managing interest reference data.
"""
from typing import List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Interest
from .base import AsyncRepository


class InterestRepository(AsyncRepository[Interest]):
    """Repository for Interest model operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Interest, session)
    
    async def get_all_names(self) -> List[str]:
        """Get all interest names ordered alphabetically."""
        result = await self.session.execute(
            select(Interest.name).order_by(Interest.name)
        )
        interests = [row[0] for row in result.all()]
        return interests if interests else ["Интересы пока не добавлены"]
    
    async def replace_all(self, interests: List[str]) -> None:
        """
        Replace all interests with new list.
        Deletes existing and inserts new ones.
        """
        # Delete all existing
        await self.session.execute(delete(Interest))
        
        # Insert new ones
        for name in interests:
            name = name.strip()
            if name:
                interest = Interest(name=name)
                self.session.add(interest)
        
        await self.session.flush()
