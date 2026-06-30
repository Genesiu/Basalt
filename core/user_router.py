from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional

from core.database import get_db
from core.auth import get_current_user, RequirePermission
from core.ip_filter import ip_whitelist_checker
from core.crypto import Hasher
from core.policy import PasswordPolicyEngine
from core.audit import create_audit_log
from models.system import User, Role, PasswordHistory, SystemConfig
# Modified: [A-01] 使用公共密码服务模块替代本地重复函数
from core.password_service import get_config_int, record_password_history, check_password_reuse

router = APIRouter(tags=["用户管理"])


# ---------- Schemas ----------

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role_code: str = "ordinary"

class UserUpdateRequest(BaseModel):
    role_code: Optional[str] = None
    is_active: Optional[bool] = None

class ProfileUpdateRequest(BaseModel):
    old_password: Optional[str] = None
    new_password: Optional[str] = None


def _user_to_dict(u: User, role_name: str = None) -> dict:
    return {
        "id": u.id, "username": u.username, "role_code": u.role_code,
        "role_name": role_name or u.role_code, "is_active": u.is_active,
        "is_locked": u.is_locked, "totp_enabled": bool(u.totp_secret),
        "password_updated_at": u.password_updated_at.strftime("%Y-%m-%d %H:%M:%S") if u.password_updated_at else None,
        "last_login_at": u.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if u.last_login_at else "从未登录",
    }


# ---------- 辅助 ----------

# Modified: [A-01] _get_config_int, _record_password_history, _check_password_reuse
# 已移至 core/password_service.py 统一维护


# ============================
# /me 路由
# ============================

@router.get("/me")
async def get_my_profile(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Role).where(Role.code == current_user.role_code))
    role_obj = result.scalars().first()
    data = _user_to_dict(current_user, role_name=role_obj.name if role_obj else current_user.role_code)
    data["permissions"] = role_obj.permissions if role_obj else []
    data["totp_force_required"] = (current_user.role_code in ["sysadmin", "auditadmin"] and not current_user.totp_secret)
    return data

@router.put("/me")
async def update_my_profile(
    request: Request, body: ProfileUpdateRequest,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    if body.old_password and body.new_password:
        if not Hasher.verify_password(body.old_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="原密码错误。")
        PasswordPolicyEngine.validate_complexity(body.new_password, username=current_user.username)
        pwd_history_count = await get_config_int(db, "PWD_HISTORY_COUNT", 5)
        if await check_password_reuse(db, current_user.id, body.new_password, pwd_history_count):
            raise HTTPException(status_code=400, detail=f"新密码不得与近 {pwd_history_count} 次使用过的密码相同。")
        await record_password_history(db, current_user.id, current_user.hashed_password, pwd_history_count)
        current_user.hashed_password = Hasher.get_password_hash(body.new_password)
        current_user.password_updated_at = datetime.utcnow()
        await db.commit()
        # Added: [SEC-01] 改密后立即吊销旧 Token
        from core.auth import revoke_user_tokens
        revoke_user_tokens(current_user.username)
        await create_audit_log(db=db, request=request, action="CHANGE_PASSWORD_SELF", status="SUCCESS",
            details={}, current_user_id=current_user.username)
        return {"message": "密码修改成功，请重新登录。"}
    return {"message": "无变更。"}


# ============================
# 管理员接口
# ============================
ManagementDepends = [RequirePermission("user:manage"), Depends(ip_whitelist_checker)]

@router.get("/", dependencies=ManagementDepends)
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    roles_res = await db.execute(select(Role))
    roles = {r.code: r.name for r in roles_res.scalars().all()}
    return [_user_to_dict(u, roles.get(u.role_code)) for u in users]

@router.post("/", dependencies=ManagementDepends)
async def create_user(
    request: Request, body: UserCreateRequest,
    db: AsyncSession = Depends(get_db), admin_user: User = Depends(get_current_user)
):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail=f"用户名 '{body.username}' 已存在。")
    PasswordPolicyEngine.validate_complexity(body.password, username=body.username)
    role_res = await db.execute(select(Role).where(Role.code == body.role_code))
    if not role_res.scalars().first():
        raise HTTPException(status_code=400, detail=f"无此角色代号: {body.role_code}")
    new_user = User(username=body.username, hashed_password=Hasher.get_password_hash(body.password),
        role_code=body.role_code, password_updated_at=None)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    await create_audit_log(db=db, request=request, action="CREATE_USER", status="SUCCESS",
        details={"username": body.username, "role_code": body.role_code}, current_user_id=admin_user.username)
    return {"message": f"用户 '{body.username}' 创建成功（首次登录需修改密码）。", "user": _user_to_dict(new_user)}

@router.put("/{user_id}", dependencies=ManagementDepends)
async def update_user(
    user_id: int, request: Request, body: UserUpdateRequest,
    db: AsyncSession = Depends(get_db), admin_user: User = Depends(get_current_user)
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在。")
    changes = {}
    if body.role_code is not None:
        role_res = await db.execute(select(Role).where(Role.code == body.role_code))
        if not role_res.scalars().first():
            raise HTTPException(status_code=400, detail=f"无此角色代号: {body.role_code}")
        target.role_code = body.role_code
        changes["role_code"] = body.role_code
    if body.is_active is not None:
        target.is_active = body.is_active
        changes["is_active"] = body.is_active
        if body.is_active:
            target.is_locked = False
            target.lock_expires_at = None
    await db.commit()
    await create_audit_log(db=db, request=request, action="UPDATE_USER", status="SUCCESS",
        details={"target_user": target.username, **changes}, current_user_id=admin_user.username)
    return {"message": f"用户 '{target.username}' 已更新。", "user": _user_to_dict(target)}

@router.delete("/{user_id}", dependencies=ManagementDepends)
async def disable_user(
    user_id: int, request: Request,
    db: AsyncSession = Depends(get_db), admin_user: User = Depends(get_current_user)
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在。")
    if target.username == admin_user.username:
        raise HTTPException(status_code=400, detail="不可停用自己的账号。")
    target.is_active = False
    target.totp_secret = None
    target.encrypted_phone = None
    target.password_updated_at = datetime.utcnow()
    await db.commit()
    # Added: 立即吊销该用户所有已颁发的 JWT Token
    from core.auth import revoke_user_tokens
    revoke_user_tokens(target.username)
    await create_audit_log(db=db, request=request, action="DISABLE_USER", status="SUCCESS",
        details={"target_user": target.username, "data_erased": True, "tokens_revoked": True},
        current_user_id=admin_user.username)
    return {"message": f"用户 '{target.username}' 已停用，敏感数据已擦除，会话令牌已吊销。"}
