import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from core.database import Base

class Role(Base):
    """
    动态 RBAC 角色表
    """
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    # JSON 数组，存储具备的 permission keys，如 ["user:manage", "policy:manage"]
    permissions = Column(JSON, default=list)
    # Added: 安全标记许可等级（等保 8.1.4.2g/h）
    # 0=公开 1=内部 2=敏感 3=核心，决定该角色能访问的最高数据密级
    max_clearance = Column(Integer, default=0, nullable=False)


class Employee(Base):
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    department = Column(String(50))
    # 模拟高敏业务数据，将在此列直接写入 AES-256-GCM 密文片段
    encrypted_phone = Column(String(255), nullable=False)


class SystemConfig(Base):
    """
    等保基线配置参数表，仅存储 key-value 对。
    """
    __tablename__ = "system_configs"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(String(500), nullable=False)
    description = Column(String(500), nullable=True)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    
    # 鉴别保密性要求: 不可逆单向加盐Hash
    hashed_password = Column(String(255), nullable=False)
    
    # 关联角色的 code
    role_code = Column(String(50), nullable=False, default="ordinary")
    
    # TOTP (双因素验证) 密钥
    totp_secret = Column(String(32), nullable=True)
    
    # 安全基线策略: 封禁、过期管控
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    lock_expires_at = Column(DateTime, nullable=True)
    # Added: password_updated_at 设为 None 表示首次登录须强制改密
    password_updated_at = Column(DateTime, nullable=True, default=None)

    # Added: 追踪最后登录时间，用于非活跃账号检测
    last_login_at = Column(DateTime, nullable=True)

    # 数据保密性与完整性: 拦截器封装的AES-256密文字段(这里做示例)
    encrypted_phone = Column(String(255), nullable=True)

class PasswordHistory(Base):
    """
    密码历史记录表（等保 8.1.4.1j）
    防止用户循环重复使用近 N 次密码。
    """
    __tablename__ = "password_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class LoginAttempt(Base):
    """
    轻量化防暴力破解存储凭证，不依赖 Redis
    """
    __tablename__ = "login_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    username = Column(String(50), nullable=True, index=True)
    success = Column(Boolean, default=False)
    attempt_time = Column(DateTime, default=datetime.utcnow)

class IPWhitelist(Base):
    """
    特定角色与路由级别的访问白名单
    """
    __tablename__ = "ip_whitelists"
    
    id = Column(Integer, primary_key=True, index=True)
    ip_network = Column(String(45), nullable=False) # 格式例: 192.168.1.0/24
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
