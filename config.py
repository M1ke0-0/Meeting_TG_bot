import os
import sys
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("Ошибка: переменная BOT_TOKEN не найдена в файле .env")
    print("Создайте файл .env и добавьте строку:")
    print("BOT_TOKEN=ваш_токен_от_BotFather")
    sys.exit(1)

DB_PATH = "bot.db"

_admin_phones_raw = os.getenv("ADMIN_PHONES", "")
ADMIN_PHONES = [p.strip() for p in _admin_phones_raw.split(",") if p.strip()]
