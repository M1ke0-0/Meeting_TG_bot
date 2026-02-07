Технологии

Python aiogram PostgreSQL asyncpg SQLAlchemy geopy openpyxl Docker

Для запуска
git clone https://github.com/M1ke0-0/Meeting_TG_bot.git
cd Meeting_TG_bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt


cp .env_sample .env
# Отредактировать .env — указать токен бота и подключение к БД

python3 run.py либо python run.py


В файле `.env` нужно указать:

```env
BOT_TOKEN=токен_от_BotFather
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/botdb
ADMIN_PHONES=+79001234567,+79007654321
```

Телефоны из `ADMIN_PHONES` получают доступ к админ-панели сразу после регистрации.

Структура проекта

database/           # Модели и репозитории SQLAlchemy
handlers/           # Обработчики команд бота
keyboards/          # Клавиатуры
middlewares/        # Загрузка пользователя, проверка роли
states/             # FSM-состояния
utils/              # Валидация, геокодинг, Excel-экспорт
run.py              # Точка входа
reset_db.py         # Сброс базы данных


Частые проблемы

Бот не отвечает — проверьте токен в `.env` и логи в консоли

Connection refused — убедитесь, что PostgreSQL запущен и DATABASE_URL корректный

Timeout при запуске — проблемы с интернетом, попробуйте запуск с VPN

