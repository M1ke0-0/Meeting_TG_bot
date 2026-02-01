import sqlite3
import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from aiogram.types import CallbackQuery
from config import DB_PATH, ADMIN_PHONES

class UserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        try:
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT tg_id, number, role, registered, name, surname, gender, age,
                        region, interests, photo_file_id, document_file_id, 
                        location_lat, location_lon
                    FROM users WHERE tg_id = ?
                """, (user_id,))
                row = c.fetchone()

            if row:
                columns = [
                    "tg_id", "number", "role", "registered", "name", "surname", "gender",
                    "age", "region", "interests", "photo_file_id", "document_file_id",
                    "location_lat", "location_lon"
                ]
                user_data = dict(zip(columns, row))
                user_data["registered"] = bool(user_data["registered"])
                
                if user_data["number"] in ADMIN_PHONES:
                    user_data["role"] = "admin"
                
                data["user"] = user_data
            else:
                data["user"] = None
        except Exception as e:
            logging.error(f"Middleware error for user {user_id}: {e}")
            data["user"] = None

        return await handler(event, data)
