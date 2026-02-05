"""
Event repository for async database operations.

Replaces database/events.py with async SQLAlchemy operations.
"""
from typing import Optional, List, Tuple

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User, Event, EventParticipant, Friend
from .base import AsyncRepository


class EventRepository(AsyncRepository[Event]):
    """Repository for Event model operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Event, session)
    
    async def create(self, organizer_phone: str, data: dict) -> Optional[int]:
        """
        Create new event and add organizer as participant.
        Returns event ID on success, None on failure.
        """
        try:
            interests = data.get("interests", [])
            interests_str = ",".join(interests) if interests else None
            
            event = Event(
                organizer_phone=organizer_phone,
                name=data.get("name"),
                date=data.get("date"),
                time=data.get("time"),
                interests=interests_str,
                address=data.get("address"),
                latitude=data.get("latitude"),
                longitude=data.get("longitude"),
                description=data.get("description"),
                photo_file_id=data.get("photo_file_id"),
                document_file_id=data.get("document_file_id"),
            )
            await self.add(event)
            
            participant = EventParticipant(
                event_id=event.id,
                participant_phone=organizer_phone
            )
            self.session.add(participant)
            await self.session.flush()
            
            return event.id
        except Exception:
            return None
    
    async def get_by_id(self, event_id: int) -> Optional[dict]:
        """Get event by ID with organizer's tg_id."""
        result = await self.session.execute(
            select(Event, User.tg_id)
            .outerjoin(User, Event.organizer_phone == User.number)
            .where(Event.id == event_id)
        )
        row = result.one_or_none()
        
        if not row:
            return None
        
        event, organizer_tg_id = row
        event_dict = event.to_dict()
        event_dict["organizer_tg_id"] = organizer_tg_id
        return event_dict
    
    async def get_friends_events(self, user_phone: str) -> List[Tuple]:
        """
        Get events from friends (not user's own events).
        Returns list of tuples matching original format.
        """
        result = await self.session.execute(
            select(User.tg_id).where(User.number == user_phone)
        )
        user_tg_id_row = result.one_or_none()
        if not user_tg_id_row:
            return []
        user_tg_id = user_tg_id_row[0]
        
        result = await self.session.execute(
            select(Friend.friend_id).where(Friend.user_id == user_tg_id)
        )
        friend_ids_1 = [row[0] for row in result.all()]
        
        result = await self.session.execute(
            select(Friend.user_id).where(Friend.friend_id == user_tg_id)
        )
        friend_ids_2 = [row[0] for row in result.all()]
        
        friend_tg_ids = set(friend_ids_1 + friend_ids_2)
        
        if not friend_tg_ids:
            return []
        
        result = await self.session.execute(
            select(
                Event.id, Event.name, Event.date, Event.time,
                Event.address, Event.interests, Event.description,
                Event.organizer_phone, Event.latitude, Event.longitude
            )
            .join(User, Event.organizer_phone == User.number)
            .where(
                and_(
                    Event.organizer_phone != user_phone,
                    User.tg_id.in_(friend_tg_ids)
                )
            )
            .order_by(Event.date, Event.time)
        )
        events = result.all()
        
        events_with_participation = []
        for event in events:
            event_id = event[0]
            part_result = await self.session.execute(
                select(EventParticipant).where(
                    and_(
                        EventParticipant.event_id == event_id,
                        EventParticipant.participant_phone == user_phone
                    )
                )
            )
            is_participant = 1 if part_result.scalar_one_or_none() else 0
            events_with_participation.append((*event, is_participant))
        
        return events_with_participation
    
    async def get_my_events(self, user_phone: str) -> Tuple[List, List]:
        """
        Get user's events: organized and participated.
        Returns (organized_events, participated_events) in original format.
        """
        result = await self.session.execute(
            select(
                Event.id, Event.name, Event.date, Event.time,
                Event.address, Event.interests, Event.description,
                Event.organizer_phone, Event.latitude, Event.longitude
            )
            .where(Event.organizer_phone == user_phone)
            .order_by(Event.created_at.desc())
        )
        organized_raw = result.all()
        organized = [(*e, 1, 0) for e in organized_raw]  
        
        result = await self.session.execute(
            select(
                Event.id, Event.name, Event.date, Event.time,
                Event.address, Event.interests, Event.description,
                Event.organizer_phone, Event.latitude, Event.longitude
            )
            .join(EventParticipant, Event.id == EventParticipant.event_id)
            .where(
                and_(
                    EventParticipant.participant_phone == user_phone,
                    Event.organizer_phone != user_phone
                )
            )
            .order_by(Event.created_at.desc())
        )
        participated_raw = result.all()
        participated = [(*e, 0, 1) for e in participated_raw]  
        
        return organized, participated
