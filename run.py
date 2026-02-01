import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database.core import init_db, init_admin_tables
from database.common import get_all_regions, get_all_interests
from middlewares.user_middleware import UserMiddleware
from handlers import user, admin, registration, events, communication

async def main():
    init_db()
    init_admin_tables()

    if not get_all_regions():
        print("ВНИМАНИЕ: таблица regions пуста! Загрузите Excel-файл через админ-панель.")
    if not get_all_interests():
        print("ВНИМАНИЕ: таблица interests пуста! Загрузите Excel-файл через админ-панель.")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Middleware
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    # Routers
    dp.include_router(user.router)
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(events.router)
    dp.include_router(communication.router)

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s | %(levelname)-8s | %(name)s → %(message)s",
    )

    print("Бот запускается...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
