from typing import Optional

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import EventInvite
from .base import AsyncRepository


class InviteRepository(AsyncRepository[EventInvite]):
    
    def __init__(self, session: AsyncSession):
        super().__init__(EventInvite, session)
    
    async def create_invite(self, event_id: int, phone: str) -> bool:
        existing = await self.session.execute(
            select(EventInvite).where(
                and_(
                    EventInvite.event_id == event_id,
                    EventInvite.invited_phone == phone
                )
            )
        )
        if existing.scalar_one_or_none():
            return False
        
        try:
            invite = EventInvite(
                event_id=event_id,
                invited_phone=phone,
                status="pending"
            )
            await self.add(invite)
            return True
        except Exception:
            return False
    
    async def get_status(self, event_id: int, phone: str) -> Optional[str]:
        result = await self.session.execute(
            select(EventInvite.status).where(
                and_(
                    EventInvite.event_id == event_id,
                    EventInvite.invited_phone == phone
                )
            )
        )
        row = result.one_or_none()
        return row[0] if row else None
    
    async def update_status(self, event_id: int, phone: str, status: str) -> None:
        await self.session.execute(
            update(EventInvite)
            .where(
                and_(
                    EventInvite.event_id == event_id,
                    EventInvite.invited_phone == phone
                )
            )
            .values(status=status)
        )
