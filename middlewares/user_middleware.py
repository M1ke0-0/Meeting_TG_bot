"""
User middleware for loading user data from database.

Injects 'user' dict into handler data for every message/callback.
"""
import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import ADMIN_PHONES
from database import get_session
from database.repositories import UserRepository


class UserMiddleware(BaseMiddleware):
    """Middleware that loads user data from PostgreSQL for each request."""
    
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        try:
            async with get_session() as session:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_tg_id(user_id)
                
                if user:
                    user_data = user.to_dict()
                    
                    # Override role if in ADMIN_PHONES
                    if user_data["number"] in ADMIN_PHONES:
                        user_data["role"] = "admin"
                    
                    data["user"] = user_data
                else:
                    data["user"] = None
                    
        except Exception as e:
            logging.error(f"Middleware error for user {user_id}: {e}")
            data["user"] = None

        return await handler(event, data)
