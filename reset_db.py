import asyncio
import sys

from dotenv import load_dotenv
load_dotenv()

from database.db_config import engine, Base
from database.models import (
    User, Event, EventParticipant, EventInvite,
    Friend, FriendRequest, Interest, Region
)


async def reset_database():
    print("⚠️  ВНИМАНИЕ: Все данные будут удалены!")
    
    confirm = input("Введите 'yes' для подтверждения: ")
    if confirm.lower() != 'yes':
        print("❌ Отменено.")
        sys.exit(0)
    
    print("\n🗑️  Удаление всех таблиц...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    print("✅ Таблицы удалены.")
    
    print("🔨 Создание таблиц заново...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Таблицы созданы.")
    print("\n🎉 База данных успешно сброшена!")


if __name__ == "__main__":
    asyncio.run(reset_database())
