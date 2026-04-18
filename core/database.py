import os
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# 等保要求: 隔离层网关。默认使用SQLite，仅通过修改此配置即可极速迁移至MySQL等。
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./basalt.db")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends 依赖注入函数"""
    async with AsyncSessionLocal() as session:
        yield session
