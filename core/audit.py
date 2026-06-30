import json
import hashlib
import asyncio
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from models.audit_log import AuditLog
from core.ip_filter import get_real_ip

# Added: [S-02 修复] 全局锁保护链式哈希的原子性，防止并发写入产生相同 prev_hash
_audit_chain_lock = asyncio.Lock()


def _compute_log_hash(log: AuditLog) -> str:
    """计算单条审计日志的 SHA-256 指纹（用于链式校验）"""
    data = f"{log.id}|{log.timestamp}|{log.user_id}|{log.action}|{log.resource}|{log.status}|{log.details or ''}"
    return hashlib.sha256(data.encode()).hexdigest()


async def create_audit_log(
    db: AsyncSession,
    request: Request,
    action: str,
    status: str = "SUCCESS",
    details: dict = None,
    current_user_id: str = "SYSTEM_OR_ANONYMOUS"
):
    """
    等保三级审计进程保护（8.1.4.3d）：同步内联写入。
    
    Modified: 增加链式哈希（prev_hash），每条日志包含前一条的 SHA-256，
    攻击者即使绕过触发器直接操作 .db 文件篡改某条记录，
    后续记录的 prev_hash 也会对不上，使篡改可被检测。
    
    Modified: [S-02 修复] 使用 asyncio.Lock 保护"读取最后日志 → 计算哈希 → 写入新日志"
    的完整操作为原子事务，防止并发请求产生相同的 prev_hash 而破坏证据链。
    """
    ip_address = get_real_ip(request)
    resource = str(request.url)

    details_str = ""
    if details:
        try:
            details_str = json.dumps(details, ensure_ascii=False)
        except Exception:
            details_str = str(details)

    # 使用独立会话写入，避免与业务事务耦合
    from core.database import AsyncSessionLocal

    # Modified: [S-02] 加锁保护链式哈希的原子性
    async with _audit_chain_lock:
        async with AsyncSessionLocal() as audit_session:
            # 获取最后一条日志的哈希，形成链式校验
            last_log_result = await audit_session.execute(
                select(AuditLog).order_by(desc(AuditLog.id)).limit(1)
            )
            last_log = last_log_result.scalars().first()
            prev_hash = _compute_log_hash(last_log) if last_log else "GENESIS"

            log = AuditLog(
                user_id=current_user_id,
                ip_address=ip_address,
                action=action,
                resource=resource,
                status=status,
                details=details_str,
                prev_hash=prev_hash,
            )
            audit_session.add(log)
            await audit_session.commit()
