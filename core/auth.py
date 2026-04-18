import os
from typing import Optional
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.database import get_db
from models.system import User, Role

# 满足 RFC 7518 标准，至少 32 字节
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "basalt-framework-dev-fallback-secret-key-32bytes") 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # 等保要求强制会话闲置越界超时限制（30分钟）

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """生成 JWT 会话令牌"""
    to_encode = data.copy()
    now = datetime.utcnow()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 注入 iat 以备解牌时比对密码更新时间，实现全线旧 Token 退化
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    """核心防线：验证 token 并提取当前实体，检查封锁/过期状态"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证凭据无效或会话已超时释放",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        iat: int = payload.get("iat")
        if username is None or iat is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    
    if user is None or not user.is_active:
        raise credentials_exception

    # [防线一：防改密后旧 Token 挤占]
    if user.password_updated_at:
        # 如果 JWT 颁发时间早于密码最近更新时间，直接暴毙
        if iat < int(user.password_updated_at.timestamp()):
            raise credentials_exception
        
    # [防线二：防近期封禁]
    if user.is_locked:
        from core.policy import PasswordPolicyEngine
        if PasswordPolicyEngine.check_lockout_status(user.is_locked, user.lock_expires_at):
            raise HTTPException(status_code=403, detail="该账号因触发安全策略（如暴力试探）现处于锁定态，请联络安全管理员。")
            
    return user


def RequirePermission(permission: str):
    """
    动态 RBAC 权限切面守护神
    取代原先的死板 RequireSysAdmin，基于 role_code 到库里映射 json permissions。
    """
    async def _permission_checker(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Role).where(Role.code == current_user.role_code))
        role_obj = result.scalars().first()
        
        if not role_obj:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您的身份角色已被系统剥离，禁止访问。"
            )
            
        if permission not in role_obj.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"越权阻断：您的角色 [{role_obj.name}] 缺少特权指令要求 [{permission}]。"
            )
        return current_user
    return Depends(_permission_checker)
