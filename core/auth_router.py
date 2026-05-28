from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc
from pydantic import BaseModel
from typing import Optional, Tuple
import json
import time
import logging

from core.database import get_db
from models.system import User, LoginAttempt, SystemConfig, PasswordHistory
from core.crypto import Hasher, RSACipher
from core.auth import create_access_token, get_current_user
from core.policy import PasswordPolicyEngine
from core.ip_filter import get_real_ip
from core.audit import create_audit_log
from core.mfa_totp import TOTPManager
from core.captcha import generate_captcha, verify_captcha

router = APIRouter(tags=["身份鉴别"])

ADMIN_ROLES_REQUIRE_TOTP = ["sysadmin", "auditadmin"]


# ---------- Schemas ----------

class EncryptedLoginRequest(BaseModel):
    """前端 RSA 加密后的登录请求"""
    encrypted_payload: str  # RSA(公钥, JSON{username, password, totp_code?})
    captcha_id: str = ""
    captcha_code: str = ""

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ResetExpiredPasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str

class EncryptedResetPasswordRequest(BaseModel):
    """加密的过期改密请求"""
    encrypted_payload: str  # RSA(公钥, JSON{username, old_password, new_password})

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

def _decrypt_payload(encrypted_payload: str) -> dict:
    """用 RSA 私钥解密前端加密的 JSON 载荷"""
    try:
        rsa_cipher = RSACipher.get_instance()
        decrypted_json = rsa_cipher.decrypt(encrypted_payload)
        return json.loads(decrypted_json)
    except Exception as e:
        logging.warning(f"[安全] RSA 解密失败: {type(e).__name__}")
        raise HTTPException(status_code=400, detail="凭据解密失败，请刷新页面重试。")


# ---------- 公钥端点 ----------

@router.get("/public-key")
async def get_public_key():
    """
    返回 RSA 公钥 PEM，供前端加密登录凭据使用。
    此接口无需认证。
    """
    rsa_cipher = RSACipher.get_instance()
    return {"public_key": rsa_cipher.get_public_key_pem()}


# ---------- 验证码端点 ----------

@router.get("/captcha")
async def get_captcha():
    """
    生成图形验证码，返回 captcha_id 和 Base64 编码的 SVG 图片。
    此接口无需认证。
    """
    return generate_captcha()


# ---------- 登录端点（加密版） ----------

@router.post("/login")
async def login_for_access_token(
    request: Request,
    body: EncryptedLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    等保三级完整登录流程（JSON 加密模式）：
    1. 验证码校验  2. IP 防爆破  3. 密码验证  4. 账号锁定
    5. 密码过期/首登改密  6. 管理员 TOTP 强制  7. TOTP 验证  8. 审计
    """
    ip_address = get_real_ip(request)
    
    # RSA 解密登录凭据
    payload = _decrypt_payload(body.encrypted_payload)
    username = payload.get("username", "")
    password_plain = payload.get("password", "")
    totp_code = payload.get("totp_code")
    captcha_id = body.captcha_id
    captcha_code = body.captcha_code
    
    max_failures = await _get_config_int(db, "LOGIN_MAX_FAILURES", 5)
    lock_mins = await _get_config_int(db, "LOGIN_LOCKOUT_MINUTES", 30)
    pwd_max_days = await _get_config_int(db, "PWD_MAX_AGE_DAYS", 90)

    # --- 0. 验证码校验 ---
    # 当 IP 已有失败记录时强制要求验证码
    time_threshold = datetime.utcnow() - timedelta(minutes=lock_mins)
    ip_fail_stmt = select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.ip_address == ip_address,
        LoginAttempt.attempt_time >= time_threshold,
        LoginAttempt.success == False
    )
    ip_fail_count = (await db.execute(ip_fail_stmt)).scalar()
    
    # 同时检查账号维度的失败次数
    username_fail_stmt = select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.username == username,
        LoginAttempt.attempt_time >= time_threshold,
        LoginAttempt.success == False
    )
    username_fail_count = (await db.execute(username_fail_stmt)).scalar()
    
    # 取 IP 和账号两个维度的较大值
    fail_count = max(ip_fail_count, username_fail_count)
    
    # Modified: [H-02 安全修复] 有过失败记录时强制验证码，不传 captcha_id 也必须拦截
    if fail_count >= 1:
        if not captcha_id or not verify_captcha(captcha_id, captcha_code):
            raise HTTPException(status_code=400,
                detail="需要验证码。请完成验证码校验后重试。",
                headers={"X-Captcha-Required": "true"})

    # --- 1. 防爆破（IP + 账号双维度） ---
    if fail_count >= max_failures:
        await create_audit_log(db=db, request=request, action="LOGIN_BLOCKED", status="BLOCKED",
            details={"ip": ip_address, "reason": "暴力试探超限"}, current_user_id=username)
        raise HTTPException(status_code=403, detail=f"因连续认证失败，登录已被锁定 {lock_mins} 分钟。")

    # --- 2. 密码验证（模糊化错误信息，不暴露用户是否存在） ---
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()

    if not user or not Hasher.verify_password(password_plain, user.hashed_password):
        attempt = LoginAttempt(ip_address=ip_address, username=username, success=False)
        db.add(attempt)
        await db.commit()
        remaining = max(0, max_failures - (fail_count + 1))
        if remaining <= 0 and user:
            user.is_locked = True
            user.lock_expires_at = datetime.utcnow() + timedelta(minutes=lock_mins)
            await db.commit()
        await create_audit_log(db=db, request=request, action="LOGIN_FAILED", status="FAILED",
            details={"ip": ip_address, "remaining": remaining}, current_user_id=username)
        # Modified: 模糊化错误信息，不暴露「用户名不存在」vs「密码错误」
        error_detail = "用户名或密码错误。"
        if remaining > 0:
            error_detail += f"剩余 {remaining} 次机会。"
        # 如果已有失败记录，告知前端需要验证码
        captcha_headers = {"X-Captcha-Required": "true"} if fail_count >= 0 else {}
        raise HTTPException(status_code=401, detail=error_detail,
            headers={**captcha_headers, "WWW-Authenticate": "Bearer"})

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
        if not totp_code:
            raise HTTPException(status_code=401, detail="此账号已启用双因子认证，请提供动态验证码。",
                headers={"X-TOTP-Required": "true"})
        if not TOTPManager.verify_totp(user.totp_secret, totp_code):
            await create_audit_log(db=db, request=request, action="LOGIN_TOTP_FAILED", status="FAILED",
                details={"ip": ip_address}, current_user_id=user.username)
            raise HTTPException(status_code=401, detail="双因子验证码错误或已过期。")

    # --- 7. 登录成功 ---
    attempt = LoginAttempt(ip_address=ip_address, username=username, success=True)
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
    # Added: [SEC-01] 改密后立即吊销旧 Token
    from core.auth import revoke_user_tokens
    revoke_user_tokens(current_user.username)
    await create_audit_log(db=db, request=request, action="CHANGE_PASSWORD", status="SUCCESS",
        details={}, current_user_id=current_user.username)
    return {"message": "密码修改成功，请使用新密码重新登录。"}


# ---------- 密码过期/首登改密（无需 token，加密传输） ----------

@router.post("/reset-expired-password")
async def reset_expired_password(
    request: Request,
    body: EncryptedResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    # RSA 解密改密参数
    payload = _decrypt_payload(body.encrypted_payload)
    username = payload.get("username", "")
    old_password = payload.get("old_password", "")
    new_password = payload.get("new_password", "")
    
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if not user or not Hasher.verify_password(old_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="身份验证失败，用户名或原密码错误。")
    PasswordPolicyEngine.validate_complexity(new_password, username=user.username)
    pwd_history_count = await _get_config_int(db, "PWD_HISTORY_COUNT", 5)
    if await _check_password_reuse(db, user.id, new_password, pwd_history_count):
        raise HTTPException(status_code=400, detail=f"新密码不得与近 {pwd_history_count} 次使用过的密码相同。")
    await _record_password_history(db, user.id, user.hashed_password, pwd_history_count)
    user.hashed_password = Hasher.get_password_hash(new_password)
    user.password_updated_at = datetime.utcnow()
    await db.commit()
    # Added: [SEC-01] 改密后立即吊销旧 Token
    from core.auth import revoke_user_tokens
    revoke_user_tokens(user.username)
    await create_audit_log(db=db, request=request, action="RESET_EXPIRED_PASSWORD", status="SUCCESS",
        details={}, current_user_id=user.username)
    return {"message": "密码修改成功，请使用新密码登录。"}


# ---------- TOTP ----------

# Modified: [C-02 安全修复] 服务端临时缓存待绑定的 TOTP secret，防止客户端注入
_pending_totp: dict[int, Tuple[str, float]] = {}  # {user_id: (secret, expire_ts)}
_TOTP_SETUP_EXPIRE = 300  # 5 分钟有效期

@router.post("/totp/setup")
async def setup_totp(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    第一步：生成 TOTP 密钥和 QR 码 URI。
    secret 存储在服务端内存中，用户通过 /totp/verify 验证后才正式绑定。
    """
    if current_user.totp_secret:
        raise HTTPException(status_code=400, detail="该账号已绑定双因子认证，如需重置请联系安全管理员。")
    secret = TOTPManager.generate_secret()
    _pending_totp[current_user.id] = (secret, time.time() + _TOTP_SETUP_EXPIRE)
    uri = TOTPManager.get_provisioning_uri(secret, current_user.username)
    return TOTPSetupResponse(secret=secret, provisioning_uri=uri,
        message="请使用 Authenticator 应用扫描二维码，然后输入 6 位验证码完成绑定。")


class TOTPVerifyRequest(BaseModel):
    code: str  # Modified: [C-02] 移除 secret 字段，仅需验证码


@router.post("/totp/verify")
async def verify_and_bind_totp(
    body: TOTPVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    第二步：用户输入 Authenticator 上的 6 位验证码。
    Modified: [C-02] secret 从服务端缓存取出，而非客户端传入。
    """
    if current_user.totp_secret:
        raise HTTPException(status_code=400, detail="该账号已绑定双因子认证。")
    
    # Modified: [C-02] 从服务端临时缓存获取 secret
    pending = _pending_totp.pop(current_user.id, None)
    if not pending or time.time() > pending[1]:
        raise HTTPException(status_code=400, detail="TOTP 绑定会话已过期或不存在，请重新发起 /totp/setup。")
    server_secret = pending[0]
    
    if not TOTPManager.verify_totp(server_secret, body.code):
        # 验证失败后重新放回缓存（允许用户重试，但不延长过期时间）
        _pending_totp[current_user.id] = pending
        await create_audit_log(db=db, request=request, action="TOTP_VERIFY_FAILED", status="FAILED",
            details={"reason": "验证码错误"}, current_user_id=current_user.username)
        raise HTTPException(status_code=400, detail="验证码错误，请检查 Authenticator 上的当前代码后重试。")
    
    current_user.totp_secret = server_secret  # Modified: [C-02] 使用服务端的 secret
    await db.commit()
    await create_audit_log(db=db, request=request, action="TOTP_BIND", status="SUCCESS",
        details={}, current_user_id=current_user.username)
    return {"message": "双因子认证绑定成功！下次登录将需要输入动态验证码。"}


@router.delete("/totp/cancel")
async def cancel_totp_setup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Modified: [H-03 安全修复] 管理员角色不可自行取消 TOTP
    if current_user.role_code in ADMIN_ROLES_REQUIRE_TOTP and current_user.totp_secret:
        raise HTTPException(status_code=403,
            detail="管理员角色的双因子认证不可自行取消，请联系安全管理员重置。")
    # 清除待绑定缓存（如果有的话）
    _pending_totp.pop(current_user.id, None)
    current_user.totp_secret = None
    await db.commit()
    await create_audit_log(db=db, request=request, action="TOTP_BIND_CANCELLED", status="SUCCESS",
        details={}, current_user_id=current_user.username)
    return {"message": "TOTP 绑定已取消。"}
