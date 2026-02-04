"""
Friend repository for async database operations.

Handles friend relationships and friend requests.
"""
from typing import Optional, List

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User, Friend, FriendRequest
from .base import AsyncRepository


class FriendRepository(AsyncRepository[Friend]):
    """Repository for Friend model operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Friend, session)
    
    async def add_friend(self, user_id: int, friend_id: int) -> bool:
        """Add a friend relationship. Returns False if already exists."""
        # Check if already friends
        existing = await self.session.execute(
            select(Friend).where(
                and_(Friend.user_id == user_id, Friend.friend_id == friend_id)
            )
        )
        if existing.scalar_one_or_none():
            return False
        
        friend = Friend(user_id=user_id, friend_id=friend_id)
        await self.add(friend)
        return True
    
    async def get_friends(self, user_id: int) -> List[dict]:
        """Get all friends for a user with their details."""
        # Get friend IDs
        result = await self.session.execute(
            select(Friend.friend_id).where(Friend.user_id == user_id)
        )
        friend_ids = [row[0] for row in result.all()]
        
        if not friend_ids:
            return []
        
        # Get friend user details
        result = await self.session.execute(
            select(User).where(User.tg_id.in_(friend_ids))
        )
        users = result.scalars().all()
        
        friends = []
        for user in users:
            friends.append({
                "tg_id": user.tg_id,
                "name": user.name,
                "surname": user.surname,
                "age": user.age,
                "region": user.region,
                "interests": user.interests,
                "photo": user.photo_file_id
            })
        return friends
    
    async def is_friend(self, user_id: int, target_id: int) -> bool:
        """Check if target is a friend of user."""
        result = await self.session.execute(
            select(Friend).where(
                and_(Friend.user_id == user_id, Friend.friend_id == target_id)
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def delete_friend(self, user_id: int, friend_id: int) -> None:
        """Delete friend relationship (bidirectional)."""
        await self.session.execute(
            delete(Friend).where(
                and_(Friend.user_id == user_id, Friend.friend_id == friend_id)
            )
        )
        await self.session.execute(
            delete(Friend).where(
                and_(Friend.user_id == friend_id, Friend.friend_id == user_id)
            )
        )
    
    # Friend Requests
    
    async def send_request(self, from_user_id: int, to_user_id: int) -> str:
        """
        Send friend request.
        Returns: 'ok', 'already_friends', 'already_sent', 'error'
        """
        # Check if already friends
        if await self.is_friend(from_user_id, to_user_id):
            return "already_friends"
        
        # Check if request already sent
        existing = await self.session.execute(
            select(FriendRequest).where(
                and_(
                    FriendRequest.from_user_id == from_user_id,
                    FriendRequest.to_user_id == to_user_id
                )
            )
        )
        if existing.scalar_one_or_none():
            return "already_sent"
        
        try:
            request = FriendRequest(from_user_id=from_user_id, to_user_id=to_user_id)
            self.session.add(request)
            await self.session.flush()
            return "ok"
        except Exception:
            return "error"
    
    async def get_incoming_requests(self, user_id: int) -> List[dict]:
        """Get incoming friend requests with user details (excluding existing friends)."""
        # Get requester IDs
        result = await self.session.execute(
            select(FriendRequest.from_user_id).where(
                FriendRequest.to_user_id == user_id
            )
        )
        requester_ids = [row[0] for row in result.all()]
        
        if not requester_ids:
            return []
        
        # Get current friend IDs to filter them out
        friend_result = await self.session.execute(
            select(Friend.friend_id).where(Friend.user_id == user_id)
        )
        friend_ids = {row[0] for row in friend_result.all()}
        
        # Filter out requesters who are already friends
        requester_ids = [rid for rid in requester_ids if rid not in friend_ids]
        
        if not requester_ids:
            return []
        
        result = await self.session.execute(
            select(User).where(User.tg_id.in_(requester_ids))
        )
        users = result.scalars().all()
        
        requests = []
        for user in users:
            requests.append({
                "tg_id": user.tg_id,
                "name": user.name,
                "surname": user.surname,
                "age": user.age,
                "region": user.region,
                "interests": user.interests,
                "photo": user.photo_file_id
            })
        return requests
    
    async def update_request_message_id(self, from_user_id: int, to_user_id: int, message_id: int) -> bool:
        """Update the message_id for a sent friend request."""
        try:
            await self.session.execute(
                select(FriendRequest).where(
                    and_(
                        FriendRequest.from_user_id == from_user_id,
                        FriendRequest.to_user_id == to_user_id
                    )
                )
            )
            # Update specific row
            from sqlalchemy import update
            stmt = (
                update(FriendRequest)
                .where(
                    and_(
                        FriendRequest.from_user_id == from_user_id,
                        FriendRequest.to_user_id == to_user_id
                    )
                )
                .values(message_id=message_id)
            )
            await self.session.execute(stmt)
            await self.session.flush()
            return True
        except Exception:
            return False

    async def accept_request(self, user_id: int, requester_id: int) -> Optional[int]:
        """
        Accept friend request.
        Returns: 
        - None if failed
        - 0 if success but no reverse request found
        - message_id (>0) if reverse request found and we should delete its message
        """
        try:
            # 1. Add bidirectional friendship
            friend1 = Friend(user_id=user_id, friend_id=requester_id)
            friend2 = Friend(user_id=requester_id, friend_id=user_id)
            self.session.add(friend1)
            self.session.add(friend2)
            
            # 2. Delete the primary request (requester -> user)
            await self.session.execute(
                delete(FriendRequest).where(
                    and_(
                        FriendRequest.from_user_id == requester_id,
                        FriendRequest.to_user_id == user_id
                    )
                )
            )
            
            # 3. Check for reverse request (user -> requester) - Mutual Request Case
            reverse_req_result = await self.session.execute(
                select(FriendRequest.message_id).where(
                    and_(
                        FriendRequest.from_user_id == user_id,
                        FriendRequest.to_user_id == requester_id
                    )
                )
            )
            reverse_msg_id = reverse_req_result.scalar_one_or_none()
            
            if reverse_msg_id is not None:
                # Delete reverse request too
                await self.session.execute(
                    delete(FriendRequest).where(
                        and_(
                            FriendRequest.from_user_id == user_id,
                            FriendRequest.to_user_id == requester_id
                        )
                    )
                )
                await self.session.flush()
                return reverse_msg_id
            
            await self.session.flush()
            return 0
            
        except Exception:
            return None
    
    async def decline_request(self, user_id: int, requester_id: int) -> None:
        """Decline friend request by deleting it."""
        await self.session.execute(
            delete(FriendRequest).where(
                and_(
                    FriendRequest.from_user_id == requester_id,
                    FriendRequest.to_user_id == user_id
                )
            )
        )
