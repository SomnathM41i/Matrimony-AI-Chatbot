from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
from app.core.logger import logger
import os

os.makedirs("storage", exist_ok=True)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_production is False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=settings.DB_POOL_SIZE,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.begin() as conn:
        def _migrate(sync_conn):
            for col in [
                ("role", "VARCHAR(32)", "'user'"),
                ("token_version", "INTEGER", "0"),
            ]:
                try:
                    sync_conn.execute(text(f"ALTER TABLE users ADD COLUMN {col[0]} {col[1]} DEFAULT {col[2]}"))
                    logger.info(f"Added {col[0]} column to users table")
                except Exception:
                    pass
        await conn.run_sync(_migrate)

    logger.info("Database tables created/verified")


async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            try:
                await session.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                await session.close()
            except Exception:
                pass


async def get_db_session():
    async for session in get_session():
        yield session
