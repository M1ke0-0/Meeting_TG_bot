"""
Database module for PostgreSQL with async SQLAlchemy 2.x.

Usage:
    from database import get_session
    from database.repositories import UserRepository
    
    async with get_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_tg_id(tg_id)
"""
from .db_config import engine, Base, DATABASE_URL
from .session import get_session, async_session_maker
from .models import (
    User, Event, EventParticipant, EventInvite,
    Friend, FriendRequest, Interest, Region
)

__all__ = [
    "engine",
    "Base",
    "DATABASE_URL",
    "get_session",
    "async_session_maker",
    "User",
    "Event",
    "EventParticipant",
    "EventInvite",
    "Friend",
    "FriendRequest",
    "Interest",
    "Region",
]
