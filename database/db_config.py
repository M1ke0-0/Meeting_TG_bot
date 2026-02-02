"""
Database configuration for PostgreSQL with async SQLAlchemy 2.x

TODO: Add Alembic migrations for production deployments
TODO: Add connection pooling configuration for high load
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

# Load DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set.\n"
        "Add to .env: DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/botdb"
    )

# Create async engine
# TODO: Configure pool_size, max_overflow for production
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    future=True,
)


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass
