"""
等保合规与备份管理

提供：
1. 备份手动触发
2. 备份调度配置（开启/关闭/路径/周期）
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional

from core.auth import RequirePermission, get_current_user
from core.ip_filter import ip_whitelist_checker
from core.audit import create_audit_log
from core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from models.system import User

import os
import logging

router = APIRouter(
    tags=["等保合规与备份"],
    dependencies=[RequirePermission("policy:manage"), Depends(ip_whitelist_checker)]
)


class BackupConfig(BaseModel):
    enabled: Optional[bool] = None
    cron_hour: Optional[int] = None
    cron_minute: Optional[int] = None
    backup_dir: Optional[str] = None
    keep_days: Optional[int] = None


@router.get("/backup/status")
async def get_backup_status():
    """获取当前备份调度状态"""
    from core.scheduler import get_scheduler_status
    return get_scheduler_status()


@router.put("/backup/config")
async def update_backup_config(
    request: Request,
    body: BackupConfig,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """修改备份调度配置（开启/关闭/时间/路径/保留天数）"""
    from core.scheduler import update_scheduler_config
    result = update_scheduler_config(
        enabled=body.enabled,
        cron_hour=body.cron_hour,
        cron_minute=body.cron_minute,
        backup_dir=body.backup_dir,
        keep_days=body.keep_days
    )
    
    await create_audit_log(
        db=db, request=request,
        action="UPDATE_BACKUP_CONFIG", status="SUCCESS",
        details=body.dict(exclude_none=True),
        current_user_id=current_user.username
    )
    return result


@router.post("/backup/trigger")
async def trigger_manual_backup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动触发一次数据库备份"""
    from core.scheduler import trigger_backup_now
    result = trigger_backup_now()
    
    await create_audit_log(
        db=db, request=request,
        action="MANUAL_BACKUP_TRIGGER", status="SUCCESS",
        details={"result": result},
        current_user_id=current_user.username
    )
    return {"message": "备份执行完成", "result": result}
