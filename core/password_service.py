"""
密码服务公共模块

Modified: [A-01 架构修复] 从 auth_router.py 和 user_router.py 中提取的重复代码，
消除 DRY 违规，确保 bug 修复只需在一处进行。
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from models.system import PasswordHistory, SystemConfig
from core.policy import PasswordPolicyEngine


async def get_config_int(db: AsyncSession, key: str, default: int) -> int:
    """从 SystemConfig 表读取整型配置值"""
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    cfg = result.scalars().first()
    return int(cfg.value) if cfg else default


async def record_password_history(
    db: AsyncSession, user_id: int, hashed_password: str, keep_count: int = 5
):
    """记录密码历史，并淘汰超出保留数的旧记录"""
    entry = PasswordHistory(user_id=user_id, hashed_password=hashed_password)
    db.add(entry)
    await db.flush()
    stmt = (
        select(PasswordHistory)
        .where(PasswordHistory.user_id == user_id)
        .order_by(desc(PasswordHistory.created_at))
    )
    result = await db.execute(stmt)
    all_history = result.scalars().all()
    if len(all_history) > keep_count:
        for old in all_history[keep_count:]:
            await db.delete(old)


async def check_password_reuse(
    db: AsyncSession, user_id: int, new_password: str, keep_count: int = 5
) -> bool:
    """
    检查新密码是否与近 N 次历史密码重复。
    返回 True 表示密码重复（不合规），False 表示可用。
    """
    stmt = (
        select(PasswordHistory)
        .where(PasswordHistory.user_id == user_id)
        .order_by(desc(PasswordHistory.created_at))
        .limit(keep_count)
    )
    result = await db.execute(stmt)
    history = result.scalars().all()
    return PasswordPolicyEngine.check_password_history(
        new_password, [h.hashed_password for h in history]
    )
