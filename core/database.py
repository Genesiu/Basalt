"""
数据库引擎工厂

支持通过 .env 中的 DATABASE_URL 切换数据库后端：
  - SQLite（默认）：sqlite+aiosqlite:///./basalt.db
  - PostgreSQL：  postgresql+asyncpg://user:pass@host:5432/basalt
  - MySQL：       mysql+aiomysql://user:pass@host:3306/basalt

切换数据库只需修改 .env 中的 DATABASE_URL，无需改动任何业务代码。
"""

import os
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./basalt.db")

# 根据数据库类型自动调整连接参数
_connect_args = {}
if "sqlite" in DATABASE_URL:
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args=_connect_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


def is_sqlite() -> bool:
    """判断当前是否使用 SQLite（用于条件性应用触发器等 SQLite 专属特性）"""
    return "sqlite" in DATABASE_URL


def get_db_type() -> str:
    """获取当前数据库类型标识"""
    if "sqlite" in DATABASE_URL:
        return "sqlite"
    elif "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
        return "postgresql"
    elif "mysql" in DATABASE_URL:
        return "mysql"
    return "unknown"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends 依赖注入函数"""
    async with AsyncSessionLocal() as session:
        yield session
