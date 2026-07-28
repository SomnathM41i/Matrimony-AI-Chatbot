from sqlalchemy import text, make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import settings
from app.core.logger import logger
import os

os.makedirs("storage", exist_ok=True)

_db_url = make_url(settings.DATABASE_URL)
if _db_url.drivername.startswith("sqlite"):
    _db_url = _db_url.set(query={
        "pragma": ("journal_mode(WAL)", "busy_timeout(5000)"),
        "check_same_thread": "False",
    })

engine = create_async_engine(
    _db_url,
    echo=settings.is_production is False,
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def create_tables():
    # Import every model before create_all so newly added modules are registered.
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.begin() as conn:
        def _migrate(sync_conn):
            for col in [
                ("last_activity", "DATETIME", "NULL"),
                ("role", "VARCHAR(32)", "'user'"),
                ("token_version", "INTEGER", "0"),
            ]:
                try:
                    sync_conn.execute(text(f"ALTER TABLE users ADD COLUMN {col[0]} {col[1]} DEFAULT {col[2]}"))
                    logger.info(f"Added {col[0]} column to users table")
                except Exception:
                    pass
            for col in [
                ("prompt_tokens", "INTEGER", "0"),
                ("completion_tokens", "INTEGER", "0"),
                ("total_tokens", "INTEGER", "0"),
            ]:
                try:
                    sync_conn.execute(text(f"ALTER TABLE chat_messages ADD COLUMN {col[0]} {col[1]} DEFAULT {col[2]}"))
                    logger.info(f"Added {col[0]} column to chat_messages table")
                except Exception:
                    pass
        await conn.run_sync(_migrate)

    from app.services.commercial_service import seed_commercial_defaults
    async with AsyncSessionLocal() as session:
        await seed_commercial_defaults(session)

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
