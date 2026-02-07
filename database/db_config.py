import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set.\n"
        "Add to .env: DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/botdb"
    )

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  
    future=True,
)


class Base(AsyncAttrs, DeclarativeBase):
    pass
