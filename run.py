"""
Main bot entry point with async database initialization.

TODO: Add Alembic migrations for production deployments
TODO: Add database connection health checks
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import engine, Base, get_session
from database.repositories import RegionRepository, InterestRepository
from middlewares.user_middleware import UserMiddleware
from handlers import user, admin, registration, events, communication


async def init_database():
    """Initialize database tables."""
    async with engine.begin() as conn:
        # TODO: Replace with Alembic migrations in production
        await conn.run_sync(Base.metadata.create_all)
    logging.info("Database tables initialized")


async def check_reference_data():
    """Check if regions and interests tables have data."""
    async with get_session() as session:
        region_repo = RegionRepository(session)
        interest_repo = InterestRepository(session)
        
        regions = await region_repo.get_all_names()
        interests = await interest_repo.get_all_names()
        
        if not regions:
            print("ВНИМАНИЕ: таблица regions пуста! Загрузите Excel-файл через админ-панель.")
        if not interests:
            print("ВНИМАНИЕ: таблица interests пуста! Загрузите Excel-файл через админ-панель.")


async def close_database():
    """Close database connections."""
    await engine.dispose()
    logging.info("Database connections closed")


async def main():
    # Initialize database
    await init_database()
    await check_reference_data()

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
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), skip_updates=True)
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(main())
