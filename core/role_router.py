from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from core.database import get_db
from models.system import Role, User
from core.auth import RequirePermission, get_current_user
from core.ip_filter import ip_whitelist_checker
from core.audit import create_audit_log
from core.security_label import SecurityLevel

router = APIRouter(
    tags=["角色与权限"],
    dependencies=[RequirePermission("role:manage"), Depends(ip_whitelist_checker)]
)

class RoleCreateUpdate(BaseModel):
    code: str
    name: str
    permissions: List[str]
    max_clearance: Optional[int] = 0  # Added: 安全标记许可等级

@router.get("/")
async def list_roles(db: AsyncSession = Depends(get_db)):
    """获取全站所有角色清单及其权限和安全等级"""
    res = await db.execute(select(Role).order_by(Role.id))
    roles = res.scalars().all()
    return [{
        "id": r.id, "code": r.code, "name": r.name,
        "permissions": r.permissions,
        "max_clearance": r.max_clearance,
        "max_clearance_label": SecurityLevel.label(r.max_clearance)
    } for r in roles]


# Added: 安全等级选项 API，供前端渲染下拉框
@router.get("/security-levels")
async def get_security_levels():
    """获取系统支持的数据安全等级列表"""
    return SecurityLevel.all_choices()


@router.post("/")
async def create_role(
    request: Request,
    body: RoleCreateUpdate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_user)
):
    """新建动态系统角色"""
    res = await db.execute(select(Role).where(Role.code == body.code))
    if res.scalars().first():
        raise HTTPException(status_code=400, detail=f"角色代码 {body.code} 已被占用。")

    new_role = Role(code=body.code, name=body.name, permissions=body.permissions, max_clearance=body.max_clearance)
    db.add(new_role)
    await db.commit()
    await db.refresh(new_role)

    await create_audit_log(
        db=db, request=request,
        action="CREATE_ROLE", status="SUCCESS",
        details={"code": body.code, "permissions": body.permissions, "max_clearance": body.max_clearance},
        current_user_id=admin_user.username
    )
    return {"message": "新建角色成功", "role": {"id": new_role.id, "code": new_role.code}}


@router.put("/{role_id}")
async def update_role(
    role_id: int,
    request: Request,
    body: RoleCreateUpdate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_user)
):
    """修改既有角色的权限节点和安全等级"""
    res = await db.execute(select(Role).where(Role.id == role_id))
    target_role = res.scalars().first()
    if not target_role:
        raise HTTPException(status_code=404, detail="未找到该角色")
    
    # Modified: [SEC-04] 预置角色代码、权限、安全等级均不可篡改
    if target_role.code in ["sysadmin", "auditadmin"]:
        if body.code != target_role.code:
            raise HTTPException(status_code=403, detail="系统预置管理员代号禁止篡改。")
        if body.permissions != target_role.permissions:
            raise HTTPException(status_code=403, detail="系统预置管理员权限禁止修改，请通过数据库直接操作。")
        if body.max_clearance != target_role.max_clearance:
            raise HTTPException(status_code=403, detail="系统预置管理员安全等级禁止修改。")
        
    old_perms = target_role.permissions
    old_clearance = target_role.max_clearance
    target_role.code = body.code
    target_role.name = body.name
    target_role.permissions = body.permissions
    target_role.max_clearance = body.max_clearance
    await db.commit()

    await create_audit_log(
        db=db, request=request,
        action="UPDATE_ROLE", status="SUCCESS",
        details={
            "code": body.code,
            "old_perms": old_perms, "new_perms": body.permissions,
            "old_clearance": old_clearance, "new_clearance": body.max_clearance
        },
        current_user_id=admin_user.username
    )
    return {"message": "角色配置已经更新"}
