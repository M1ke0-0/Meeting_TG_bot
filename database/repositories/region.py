"""
Region repository for managing region reference data.
"""
from typing import List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Region
from .base import AsyncRepository


class RegionRepository(AsyncRepository[Region]):
    """Repository for Region model operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Region, session)
    
    async def get_all_names(self) -> List[str]:
        """Get all region names ordered alphabetically."""
        result = await self.session.execute(
            select(Region.name).order_by(Region.name)
        )
        regions = [row[0] for row in result.all()]
        return regions
    
    async def replace_all(self, regions: List[str]) -> None:
        """
        Replace all regions with new list.
        Deletes existing and inserts new ones.
        """
        await self.session.execute(delete(Region))
        
        
        for name in regions:
            name = name.strip()
            if name:
                region = Region(name=name)
                self.session.add(region)
        
        await self.session.flush()
