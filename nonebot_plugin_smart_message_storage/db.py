# python3
# -*- coding: utf-8 -*-

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import config
from .models import Base


def _async_db_url(url: str) -> str:
    if url.startswith("sqlite+"):
        return url
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url == "sqlite://":
        return "sqlite+aiosqlite://"
    return url


engine = create_async_engine(_async_db_url(config.message_db_url), echo=False, future=True)
SessionLocal = async_sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
