from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
from pydantic import BaseModel

from core.database import get_db
from models.system import SystemConfig, IPWhitelist
from core.auth import RequirePermission, get_current_user
from core.ip_filter import ip_whitelist_checker
from models.system import User
from core.audit import create_audit_log

# 全局挂载权限检查和 IP 白名单拦截
router = APIRouter(
    tags=["基线引擎"],
    dependencies=[RequirePermission("policy:manage"), Depends(ip_whitelist_checker)]
)


# ---------- 等保基线参数 ----------

@router.get("/")
async def get_all_configs(db: AsyncSession = Depends(get_db)):
    """已授权用户可查看当前等保基线参数"""
    result = await db.execute(select(SystemConfig))
    configs = result.scalars().all()
    return {c.key: c.value for c in configs}


@router.put("/")
async def update_configs(
    request: Request,
    payload: Dict[str, str],
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_user)
):
    """有权限的管理员可修改等保基线参数，操作写入审计日志"""
    # Added: [SEC-03] 仅允许修改已知的配置键
    ALLOWED_KEYS = {
        "LOGIN_MAX_FAILURES", "LOGIN_LOCKOUT_MINUTES", "PWD_COMPLEXITY_ENFORCE",
        "SESSION_TIMEOUT_MINS", "PWD_MAX_AGE_DAYS", "PWD_HISTORY_COUNT",
        "INACTIVE_DAYS_LIMIT",
    }
    invalid_keys = set(payload.keys()) - ALLOWED_KEYS
    if invalid_keys:
        raise HTTPException(status_code=400,
            detail=f"不允许修改或新增以下配置键: {', '.join(invalid_keys)}")

    changed = {}
    for k, v in payload.items():
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == k))
        config_obj = result.scalars().first()
        if config_obj:
            old_val = config_obj.value
            config_obj.value = str(v)
            db.add(config_obj)
            changed[k] = {"old": old_val, "new": str(v)}
    await db.commit()

    # Modified: 同步审计写入
    await create_audit_log(
        db=db, request=request,
        action="UPDATE_SYSTEM_CONFIG", status="SUCCESS",
        details=changed,
        current_user_id=admin_user.username
    )
    return {"message": "等保基线参数已更新并生效"}


# ---------- IP 白名单管理 ----------

class IPWhitelistCreate(BaseModel):
    ip_network: str
    description: str = ""


@router.get("/whitelist")
async def list_whitelist(db: AsyncSession = Depends(get_db)):
    """查看当前 IP 白名单"""
    result = await db.execute(select(IPWhitelist))
    items = result.scalars().all()
    return [
        {"id": w.id, "ip_network": w.ip_network, "description": w.description or ""}
        for w in items
    ]


@router.post("/whitelist")
async def add_whitelist(
    request: Request,
    body: IPWhitelistCreate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_user)
):
    """添加 IP 白名单规则"""
    # Added: [SEC-02] 校验 CIDR 格式合法性
    import ipaddress
    try:
        ipaddress.ip_network(body.ip_network, strict=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"无效的 IP/CIDR 格式: {body.ip_network} ({e})")

    entry = IPWhitelist(ip_network=body.ip_network, description=body.description)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    await create_audit_log(
        db=db, request=request,
        action="ADD_IP_WHITELIST", status="SUCCESS",
        details={"ip_network": body.ip_network},
        current_user_id=admin_user.username
    )
    return {"message": f"已添加白名单规则: {body.ip_network}", "id": entry.id}


@router.delete("/whitelist/{item_id}")
async def delete_whitelist(
    item_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_user)
):
    """删除 IP 白名单规则"""
    result = await db.execute(select(IPWhitelist).where(IPWhitelist.id == item_id))
    entry = result.scalars().first()
    if not entry:
        raise HTTPException(status_code=404, detail="白名单规则不存在")

    ip_net = entry.ip_network
    await db.delete(entry)
    await db.commit()

    await create_audit_log(
        db=db, request=request,
        action="DELETE_IP_WHITELIST", status="SUCCESS",
        details={"ip_network": ip_net, "id": item_id},
        current_user_id=admin_user.username
    )
    return {"message": f"已删除白名单规则: {ip_net}"}
