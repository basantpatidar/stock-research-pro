from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_optional():
    """Like get_db but yields None instead of raising if the DB is unreachable.

    Use this for endpoints where DB is only needed for caching — the endpoint
    still works without a DB connection, just without cache reads/writes.
    """
    yielded = False
    try:
        async with AsyncSessionLocal() as session:
            try:
                yielded = True
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except Exception:
        if not yielded:
            # DB connection failed before we ever yielded — safe to yield None
            yield None
