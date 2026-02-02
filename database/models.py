"""
SQLAlchemy ORM models for the Telegram bot.

All models use declarative style with SQLAlchemy 2.x.
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Float, Text, DateTime, ForeignKey, 
    CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db_config import Base


class User(Base):
    """User model - registered bot users."""
    __tablename__ = "users"
    
    number: Mapped[str] = mapped_column(String(20), primary_key=True)
    role: Mapped[str] = mapped_column(
        String(10), 
        nullable=False,
        default="user"
    )
    registered: Mapped[int] = mapped_column(Integer, default=0)
    tg_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    surname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    interests: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    document_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    location_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    organized_events: Mapped[List["Event"]] = relationship(
        back_populates="organizer",
        foreign_keys="Event.organizer_phone"
    )
    
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="check_role"),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for handler compatibility."""
        return {
            "tg_id": self.tg_id,
            "number": self.number,
            "role": self.role,
            "registered": bool(self.registered),
            "name": self.name,
            "surname": self.surname,
            "gender": self.gender,
            "age": self.age,
            "region": self.region,
            "interests": self.interests,
            "photo_file_id": self.photo_file_id,
            "document_file_id": self.document_file_id,
            "location_lat": self.location_lat,
            "location_lon": self.location_lon,
        }


class Event(Base):
    """Event model - user-organized events."""
    __tablename__ = "events"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organizer_phone: Mapped[str] = mapped_column(
        String(20), 
        ForeignKey("users.number"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # DD.MM.YYYY
    time: Mapped[str] = mapped_column(String(5), nullable=False)   # HH:MM
    interests: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    document_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    organizer: Mapped["User"] = relationship(
        back_populates="organized_events",
        foreign_keys=[organizer_phone]
    )
    participants: Mapped[List["EventParticipant"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan"
    )
    invites: Mapped[List["EventInvite"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan"
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for handler compatibility."""
        return {
            "id": self.id,
            "organizer_phone": self.organizer_phone,
            "name": self.name,
            "date": self.date,
            "time": self.time,
            "interests": self.interests,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "description": self.description,
            "photo_file_id": self.photo_file_id,
            "document_file_id": self.document_file_id,
        }


class EventParticipant(Base):
    """Event participants - users who joined an event."""
    __tablename__ = "event_participants"
    
    event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True
    )
    participant_phone: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("users.number"),
        primary_key=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    event: Mapped["Event"] = relationship(back_populates="participants")
    participant: Mapped["User"] = relationship(foreign_keys=[participant_phone])


class EventInvite(Base):
    """Event invitations - track invite status."""
    __tablename__ = "event_invites"
    
    event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True
    )
    invited_phone: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("users.number"),
        primary_key=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False
    )  # pending, accepted, declined
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    event: Mapped["Event"] = relationship(back_populates="invites")
    invited_user: Mapped["User"] = relationship(foreign_keys=[invited_phone])


class Friend(Base):
    """Friend relationships between users."""
    __tablename__ = "friends"
    
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    friend_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )


class FriendRequest(Base):
    """Pending friend requests."""
    __tablename__ = "friend_requests"
    
    from_user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    to_user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )


class Interest(Base):
    """Interest reference table."""
    __tablename__ = "interests"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class Region(Base):
    """Region reference table."""
    __tablename__ = "regions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
