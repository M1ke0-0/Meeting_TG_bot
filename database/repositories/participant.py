"""
Participant repository for event participation operations.
"""
from typing import Optional, List, Tuple

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User, Event, EventParticipant, EventInvite
from .base import AsyncRepository


class ParticipantRepository(AsyncRepository[EventParticipant]):
    """Repository for EventParticipant model operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(EventParticipant, session)
    
    async def join_event(self, event_id: int, phone: str) -> Tuple[bool, Optional[str]]:
        """
        Join an event.
        Returns (success, error_message).
        """
        # Check if already participating
        existing = await self.session.execute(
            select(EventParticipant).where(
                and_(
                    EventParticipant.event_id == event_id,
                    EventParticipant.participant_phone == phone
                )
            )
        )
        if existing.scalar_one_or_none():
            return False, "already_joined"
        
        try:
            participant = EventParticipant(
                event_id=event_id,
                participant_phone=phone
            )
            await self.add(participant)
            
            # Update invite status if exists
            await self.session.execute(
                EventInvite.__table__.update()
                .where(
                    and_(
                        EventInvite.event_id == event_id,
                        EventInvite.invited_phone == phone
                    )
                )
                .values(status="accepted")
            )
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    async def leave_event(
        self, event_id: int, phone: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Leave an event.
        Returns (success, message, organizer_phone).
        """
        # Get event and organizer
        result = await self.session.execute(
            select(Event.organizer_phone).where(Event.id == event_id)
        )
        row = result.one_or_none()
        
        if not row:
            return False, "not_found", None
        
        organizer_phone = row[0]
        
        # Delete participation
        result = await self.session.execute(
            delete(EventParticipant).where(
                and_(
                    EventParticipant.event_id == event_id,
                    EventParticipant.participant_phone == phone
                )
            )
        )
        
        if result.rowcount == 0:
            return False, "not_participating", None
        
        # Update invite status
        await self.session.execute(
            EventInvite.__table__.update()
            .where(
                and_(
                    EventInvite.event_id == event_id,
                    EventInvite.invited_phone == phone
                )
            )
            .values(status="declined")
        )
        
        return True, "success", organizer_phone
    
    async def get_participants(self, event_id: int) -> List[Tuple[str, str, int]]:
        """Get list of participants: (name, surname, age)."""
        result = await self.session.execute(
            select(User.name, User.surname, User.age)
            .join(
                EventParticipant,
                EventParticipant.participant_phone == User.number
            )
            .where(EventParticipant.event_id == event_id)
            .order_by(User.name, User.surname)
        )
        return list(result.all())
    
    async def get_participant_ids(self, event_id: int) -> List[int]:
        """Get telegram IDs of all participants."""
        result = await self.session.execute(
            select(User.tg_id)
            .join(
                EventParticipant,
                EventParticipant.participant_phone == User.number
            )
            .where(EventParticipant.event_id == event_id)
        )
        return [row[0] for row in result.all() if row[0] is not None]
