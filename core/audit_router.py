import csv
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from core.database import get_db
from core.auth import RequirePermission
from core.ip_filter import ip_whitelist_checker
from models.audit_log import AuditLog

# 等保核心：审计日志查询隔离于普通系统管理权限之外
router = APIRouter(
    tags=["安全审计"],
    dependencies=[RequirePermission("audit:view"), Depends(ip_whitelist_checker)]
)


def _log_to_dict(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "",
        "user_id": log.user_id,
        "ip_address": log.ip_address,
        "action": log.action,
        "resource": log.resource,
        "status": log.status,
        "details": log.details or ""
    }


@router.get("/")
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    limit: int = 200
):
    """查询审计日志，按时间倒序返回"""
    stmt = select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [_log_to_dict(log) for log in logs]


@router.get("/{log_id}")
async def get_audit_detail(
    log_id: int,
    db: AsyncSession = Depends(get_db)
):
    """查看单条审计日志完整详情"""
    result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
    log = result.scalars().first()
    if not log:
        raise HTTPException(status_code=404, detail="审计记录不存在。")
    return _log_to_dict(log)


# Added: 等保 8.1.5d — 审计日志 CSV 导出（审计管理员职能）
@router.get("/export/csv", dependencies=[RequirePermission("audit:export")])
async def export_audit_csv(
    db: AsyncSession = Depends(get_db),
    limit: int = 10000
):
    """
    导出审计日志为 CSV 文件。
    等保现场检查要求审计管理员能够导出审计报告数据。
    """
    stmt = select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    output = io.StringIO()
    # 写入 BOM 以确保 Excel 正确识别 UTF-8
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["ID", "时间", "操作人", "来源IP", "动作", "资源", "状态", "详情"])

    for log in logs:
        writer.writerow([
            log.id,
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "",
            log.user_id,
            log.ip_address,
            log.action,
            log.resource,
            log.status,
            log.details or ""
        ])

    output.seek(0)
    from datetime import datetime
    filename = f"audit_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
