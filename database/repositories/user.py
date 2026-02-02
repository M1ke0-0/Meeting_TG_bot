"""
User repository for async database operations.

Replaces database/users.py with async SQLAlchemy operations.
"""
from typing import Optional, List

from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User, Friend, FriendRequest
from .base import AsyncRepository


class UserRepository(AsyncRepository[User]):
    """Repository for User model operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_phone(self, phone: str) -> Optional[User]:
        """Get user by phone number."""
        return await self.get(phone)
    
    async def get_by_tg_id(self, tg_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        return result.scalar_one_or_none()
    
    async def check_user_status(self, phone: str) -> dict:
        """
        Check user status by phone.
        Returns dict with exists, role, registered, tg_id, name.
        """
        user = await self.get_by_phone(phone)
        if user:
            return {
                "exists": True,
                "role": user.role,
                "registered": bool(user.registered),
                "tg_id": user.tg_id,
                "name": user.name
            }
        return {"exists": False}
    
    async def register_phone(self, phone: str, tg_id: int, role: str = "user") -> bool:
        """
        Register new user with phone and telegram ID.
        Returns True on success, False if user already exists.
        """
        existing = await self.get_by_phone(phone)
        if existing:
            return False
        
        user = User(
            number=phone,
            role=role,
            tg_id=tg_id,
            registered=0
        )
        await self.add(user)
        return True
    
    async def update_profile(self, phone: str, data: dict) -> bool:
        """Update user profile with provided data."""
        interests = data.get("interests", [])
        interests_str = ",".join(interests) if interests else None
        
        await self.session.execute(
            update(User)
            .where(User.number == phone)
            .values(
                name=data.get("name"),
                surname=data.get("surname"),
                gender=data.get("gender"),
                age=data.get("age"),
                region=data.get("region"),
                interests=interests_str,
                photo_file_id=data.get("photo_file_id"),
                document_file_id=data.get("document_file_id"),
                location_lat=data.get("location_lat"),
                location_lon=data.get("location_lon"),
                registered=1
            )
        )
        return True
    
    async def find_potential_friends(
        self, 
        organizer_phone: str, 
        interests: Optional[List[str]] = None
    ) -> List[dict]:
        """
        Find potential friends excluding current user.
        Optionally filter by interests and sort by interest overlap.
        """
        query = select(User).where(
            and_(
                User.number != organizer_phone,
                User.registered == 1,
                User.tg_id.isnot(None)
            )
        )
        
        # If interests provided, filter by matching interests
        if interests:
            interest_conditions = [
                User.interests.like(f"%{interest}%") 
                for interest in interests
            ]
            query = query.where(or_(*interest_conditions))
        
        result = await self.session.execute(query)
        users = result.scalars().all()
        
        friends = []
        for user in users:
            user_interests = user.interests.split(",") if user.interests else []
            friends.append({
                "phone": user.number,
                "tg_id": user.tg_id,
                "name": user.name or "—",
                "surname": user.surname or "",
                "age": user.age,
                "gender": user.gender,
                "region": user.region,
                "interests": user_interests
            })
        
        # Sort by interest overlap if interests provided
        if interests:
            interests_set = set(interests)
            friends.sort(
                key=lambda f: len(interests_set & set(f["interests"])),
                reverse=True
            )
        
        return friends[:20]
    
    async def search_users(
        self,
        current_phone: str,
        gender: Optional[str] = None,
        region: Optional[str] = None,
        age_range: Optional[str] = None,
        interests: Optional[List[str]] = None
    ) -> List[dict]:
        """
        Search users with filters. Used in communication.py perform_search.
        """
        query = select(User).where(
            and_(
                User.registered == 1,
                User.number != current_phone
            )
        )
        
        if gender:
            query = query.where(User.gender == gender)
        if region:
            query = query.where(User.region == region)
        if age_range and "-" in age_range:
            try:
                min_age, max_age = map(int, age_range.split("-"))
                if 0 < min_age <= max_age < 150:
                    query = query.where(
                        and_(User.age >= min_age, User.age <= max_age)
                    )
            except ValueError:
                pass
        
        result = await self.session.execute(query)
        users = result.scalars().all()
        
        user_interests = set(interests) if interests else set()
        results = []
        
        for user in users:
            u_interests = set(user.interests.split(",")) if user.interests else set()
            overlap = len(user_interests & u_interests) if user_interests else 0
            
            # Skip if interests required but no overlap
            if interests and overlap == 0:
                continue
            
            results.append({
                "tg_id": user.tg_id,
                "name": user.name,
                "surname": user.surname,
                "age": user.age,
                "gender": user.gender,
                "region": user.region,
                "interests": user.interests,
                "photo": user.photo_file_id,
                "score": overlap
            })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
