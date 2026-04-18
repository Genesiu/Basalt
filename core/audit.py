import json
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from models.audit_log import AuditLog
from core.ip_filter import get_real_ip


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
    
    Modified: 从 BackgroundTasks 异步模式改为同步 commit 模式。
    审计记录在 API 响应返回之前即已落盘（commit），即使进程在响应后崩溃，
    审计数据也不会丢失。对 SQLite 而言单次 INSERT 开销为亚毫秒级，零感知。
    
    调用方式变化：
      旧: create_audit_log(request=request, background_tasks=bg_tasks, action=..., ...)
      新: await create_audit_log(db=db, request=request, action=..., ...)
    """
    ip_address = get_real_ip(request)
    resource = str(request.url)

    details_str = ""
    if details:
        try:
            details_str = json.dumps(details, ensure_ascii=False)
        except Exception:
            details_str = str(details)

    log = AuditLog(
        user_id=current_user_id,
        ip_address=ip_address,
        action=action,
        resource=resource,
        status=status,
        details=details_str
    )

    # 使用独立会话写入，避免与业务事务耦合
    # 即使业务事务回滚，审计记录也必须保留（等保要求）
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as audit_session:
        audit_session.add(log)
        await audit_session.commit()
