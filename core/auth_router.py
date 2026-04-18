from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc
from pydantic import BaseModel
from typing import Optional

from core.database import get_db
from models.system import User, LoginAttempt, SystemConfig, PasswordHistory
from core.crypto import Hasher
from core.auth import create_access_token, get_current_user
from core.policy import PasswordPolicyEngine
from core.ip_filter import get_real_ip
from core.audit import create_audit_log
from core.mfa_totp import TOTPManager

router = APIRouter(tags=["身份鉴别"])

ADMIN_ROLES_REQUIRE_TOTP = ["sysadmin", "auditadmin"]


# ---------- Schemas ----------

class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class TOTPSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    message: str


# ---------- 辅助 ----------

async def _get_config_int(db: AsyncSession, key: str, default: int) -> int:
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    cfg = result.scalars().first()
    return int(cfg.value) if cfg else default

async def _record_password_history(db: AsyncSession, user_id: int, hashed_password: str, keep_count: int = 5):
    entry = PasswordHistory(user_id=user_id, hashed_password=hashed_password)
    db.add(entry)
    await db.flush()
    stmt = select(PasswordHistory).where(PasswordHistory.user_id == user_id).order_by(desc(PasswordHistory.created_at))
    result = await db.execute(stmt)
    all_history = result.scalars().all()
    if len(all_history) > keep_count:
        for old in all_history[keep_count:]:
            await db.delete(old)

async def _check_password_reuse(db: AsyncSession, user_id: int, new_password: str, keep_count: int = 5) -> bool:
    stmt = select(PasswordHistory).where(PasswordHistory.user_id == user_id).order_by(desc(PasswordHistory.created_at)).limit(keep_count)
    result = await db.execute(stmt)
    history = result.scalars().all()
    return PasswordPolicyEngine.check_password_history(new_password, [h.hashed_password for h in history])


# ---------- 登录端点 ----------

@router.post("/login")
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    等保三级完整登录流程：
    1. IP 防爆破  2. 密码验证  3. 账号锁定  4. 密码过期/首登改密
    5. 管理员 TOTP 强制  6. TOTP 验证  7. 审计 + last_login_at
    """
    ip_address = get_real_ip(request)
    max_failures = await _get_config_int(db, "LOGIN_MAX_FAILURES", 5)
    lock_mins = await _get_config_int(db, "LOGIN_LOCKOUT_MINUTES", 30)
    pwd_max_days = await _get_config_int(db, "PWD_MAX_AGE_DAYS", 90)

    # --- 1. 防爆破 ---
    time_threshold = datetime.utcnow() - timedelta(minutes=lock_mins)
    fail_stmt = select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.ip_address == ip_address,
        LoginAttempt.attempt_time >= time_threshold,
        LoginAttempt.success == False
    )
    fail_count = (await db.execute(fail_stmt)).scalar()

    if fail_count >= max_failures:
        await create_audit_log(db=db, request=request, action="LOGIN_BLOCKED", status="BLOCKED",
            details={"ip": ip_address, "reason": "暴力试探超限"}, current_user_id=form_data.username)
        raise HTTPException(status_code=403, detail=f"该 IP 因连续失败已被锁定 {lock_mins} 分钟。")

    # --- 2. 密码验证 ---
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalars().first()

    if not user or not Hasher.verify_password(form_data.password, user.hashed_password):
        attempt = LoginAttempt(ip_address=ip_address, username=form_data.username, success=False)
        db.add(attempt)
        await db.commit()
        remaining = max(0, max_failures - (fail_count + 1))
        if remaining <= 0 and user:
            user.is_locked = True
            user.lock_expires_at = datetime.utcnow() + timedelta(minutes=lock_mins)
            await db.commit()
        await create_audit_log(db=db, request=request, action="LOGIN_FAILED", status="FAILED",
            details={"ip": ip_address, "remaining": remaining}, current_user_id=form_data.username)
        raise HTTPException(status_code=401, detail=f"身份鉴别失败，剩余 {remaining} 次机会。",
            headers={"WWW-Authenticate": "Bearer"})

    # --- 3. 账号锁定 ---
    if user.is_locked:
        if PasswordPolicyEngine.check_lockout_status(user.is_locked, user.lock_expires_at):
            raise HTTPException(status_code=403, detail="账号处于锁定状态，请等待解锁或联系管理员。")
        else:
            user.is_locked = False
            user.lock_expires_at = None

    # --- 4. 密码过期 / 首登改密 ---
    if user.password_updated_at:
        days_since = (datetime.utcnow() - user.password_updated_at).days
        if days_since >= pwd_max_days:
            await create_audit_log(db=db, request=request, action="LOGIN_PWD_EXPIRED", status="BLOCKED",
                details={"days_since": days_since, "max_days": pwd_max_days}, current_user_id=user.username)
            raise HTTPException(status_code=403,
                detail=f"口令已过期（已使用 {days_since} 天，上限 {pwd_max_days} 天），请先修改密码。",
                headers={"X-Password-Expired": "true"})
    else:
        await create_audit_log(db=db, request=request, action="LOGIN_FIRST_TIME_PWD_CHANGE", status="BLOCKED",
            details={"reason": "默认密码首次登录强制修改"}, current_user_id=user.username)
        raise HTTPException(status_code=403, detail="首次登录或密码已被重置，请先设置新密码。",
            headers={"X-Password-Expired": "true"})

    # --- 5. 管理员 TOTP 强制 ---
    if user.role_code in ADMIN_ROLES_REQUIRE_TOTP and not user.totp_secret:
        pass  # 允许登录但会在响应中附带警告

    # --- 6. TOTP 验证 ---
    if user.totp_secret:
        totp_code = form_data.scopes[0] if form_data.scopes else None
        if not totp_code:
            raise HTTPException(status_code=401, detail="此账号已启用双因子认证，请提供动态验证码。",
                headers={"X-TOTP-Required": "true"})
        if not TOTPManager.verify_totp(user.totp_secret, totp_code):
            await create_audit_log(db=db, request=request, action="LOGIN_TOTP_FAILED", status="FAILED",
                details={"ip": ip_address}, current_user_id=user.username)
            raise HTTPException(status_code=401, detail="双因子验证码错误或已过期。")

    # --- 7. 登录成功 ---
    attempt = LoginAttempt(ip_address=ip_address, username=form_data.username, success=True)
    db.add(attempt)
    user.last_login_at = datetime.utcnow()
    await db.commit()

    await create_audit_log(db=db, request=request, action="LOGIN_SUCCESS", status="SUCCESS",
        details={"ip": ip_address}, current_user_id=user.username)

    access_token = create_access_token(data={"sub": user.username})
    response_data = {"access_token": access_token, "token_type": "bearer"}
    if user.role_code in ADMIN_ROLES_REQUIRE_TOTP and not user.totp_secret:
        response_data["totp_required_warning"] = "您的管理员角色要求绑定双因子认证，请立即前往个人中心完成 TOTP 绑定。"
    return response_data


# ---------- 修改密码（需登录态） ----------

@router.put("/change-password")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not Hasher.verify_password(body.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码验证失败。")
    PasswordPolicyEngine.validate_complexity(body.new_password, username=current_user.username)
    pwd_history_count = await _get_config_int(db, "PWD_HISTORY_COUNT", 5)
    if await _check_password_reuse(db, current_user.id, body.new_password, pwd_history_count):
        raise HTTPException(status_code=400, detail=f"新密码不得与近 {pwd_history_count} 次使用过的密码相同。")
    await _record_password_history(db, current_user.id, current_user.hashed_password, pwd_history_count)
    current_user.hashed_password = Hasher.get_password_hash(body.new_password)
    current_user.password_updated_at = datetime.utcnow()
    await db.commit()
    await create_audit_log(db=db, request=request, action="CHANGE_PASSWORD", status="SUCCESS",
        details={}, current_user_id=current_user.username)
    return {"message": "密码修改成功，请使用新密码重新登录。"}


# ---------- 密码过期/首登改密（无需 token） ----------

class ResetExpiredPasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str

@router.post("/reset-expired-password")
async def reset_expired_password(
    request: Request,
    body: ResetExpiredPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalars().first()
    if not user or not Hasher.verify_password(body.old_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="身份验证失败，用户名或原密码错误。")
    PasswordPolicyEngine.validate_complexity(body.new_password, username=user.username)
    pwd_history_count = await _get_config_int(db, "PWD_HISTORY_COUNT", 5)
    if await _check_password_reuse(db, user.id, body.new_password, pwd_history_count):
        raise HTTPException(status_code=400, detail=f"新密码不得与近 {pwd_history_count} 次使用过的密码相同。")
    await _record_password_history(db, user.id, user.hashed_password, pwd_history_count)
    user.hashed_password = Hasher.get_password_hash(body.new_password)
    user.password_updated_at = datetime.utcnow()
    await db.commit()
    await create_audit_log(db=db, request=request, action="RESET_EXPIRED_PASSWORD", status="SUCCESS",
        details={}, current_user_id=user.username)
    return {"message": "密码修改成功，请使用新密码登录。"}


# ---------- TOTP ----------

@router.post("/totp/setup")
async def setup_totp(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.totp_secret:
        raise HTTPException(status_code=400, detail="该账号已绑定双因子认证，如需重置请联系安全管理员。")
    secret = TOTPManager.generate_secret()
    uri = TOTPManager.get_provisioning_uri(secret, current_user.username)
    current_user.totp_secret = secret
    await db.commit()
    await create_audit_log(db=db, request=request, action="TOTP_BIND", status="SUCCESS",
        details={}, current_user_id=current_user.username)
    return TOTPSetupResponse(secret=secret, provisioning_uri=uri,
        message="请使用 Authenticator 应用扫描绑定，绑定后登录需提供动态验证码。")

@router.delete("/totp/cancel")
async def cancel_totp_setup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_user.totp_secret = None
    await db.commit()
    await create_audit_log(db=db, request=request, action="TOTP_BIND_CANCELLED", status="SUCCESS",
        details={}, current_user_id=current_user.username)
    return {"message": "TOTP 绑定已取消。"}
