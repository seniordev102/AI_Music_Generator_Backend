from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings

async_engine = create_async_engine(
    settings.DB_URL,
    echo=settings.DB_ECHO,
    future=True,
    connect_args={"server_settings": {"application_name": "IAH Backend API"}},
)

SessionLocal = sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()
