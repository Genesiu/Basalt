import os
import base64
import logging

# ============================================================
# 密钥持久化：首次启动自动生成 .env，后续重启自动加载（不再随机变化）
# ============================================================
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

def _load_or_create_env():
    """从 .env 文件加载密钥，不存在则自动生成并写入"""
    env_vars = {}
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    
    changed = False
    if "AES_ENCRYPTION_KEY_B64" not in env_vars:
        env_vars["AES_ENCRYPTION_KEY_B64"] = base64.b64encode(os.urandom(32)).decode()
        changed = True
    if "JWT_SECRET_KEY" not in env_vars:
        env_vars["JWT_SECRET_KEY"] = base64.b64encode(os.urandom(32)).decode()
        changed = True
    
    if changed:
        with open(_ENV_FILE, "w") as f:
            f.write("# Basalt 自动生成的密钥文件，请勿删除或手动修改（除非你知道后果）\n")
            f.write("# 生产环境建议使用 KMS 或 Vault 管理密钥\n")
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")
        os.chmod(_ENV_FILE, 0o600)  # 仅属主可读写
        logging.warning(f"[密钥初始化] 已自动生成 .env 文件: {_ENV_FILE}")
    
    # 注入环境变量
    for k, v in env_vars.items():
        if not os.environ.get(k):
            os.environ[k] = v

_load_or_create_env()

from fastapi import FastAPI
from core.database import engine, Base, AsyncSessionLocal
from sqlalchemy.future import select
from sqlalchemy import text
from models.system import User, Role, SystemConfig
from core.crypto import Hasher

from modules.example_app.api import router as example_router
from core.auth_router import router as auth_router
from core.config_router import router as config_router
from core.audit_router import router as audit_router
from core.user_router import router as user_router
from core.role_router import router as role_router

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Basalt Framework — AI-Native Security Microkernel",
    description="Build on Basalt. Secure by default. | by Genesiu",
    version="2.0.0"
)

# Modified: CORS 改为可配置白名单（等保 8.1.3a）
# 生产环境应通过环境变量 CORS_ORIGINS 配置为逗号分隔的域名列表
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "*")
if _cors_origins_raw == "*":
    _cors_origins = ["*"]
    logging.warning("[安全警告] CORS 允许所有来源（开发模式），生产环境请设置 CORS_ORIGINS 环境变量。")
else:
    _cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Password-Expired", "X-TOTP-Required"],
)

app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(config_router, prefix="/api/v1/config")
app.include_router(audit_router, prefix="/api/v1/audit")
app.include_router(user_router, prefix="/api/v1/users")
app.include_router(role_router, prefix="/api/v1/roles")
app.include_router(example_router, prefix="/api/v1")

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        # SQLite 快速建表
        await conn.run_sync(Base.metadata.create_all)

        # Added: 等保 8.1.4.3c — 审计日志表防删改保护（SQLite 触发器）
        # 禁止任何 UPDATE 或 DELETE 操作，确保 APPEND-ONLY
        try:
            await conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS audit_logs_no_update
                BEFORE UPDATE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, '等保安全策略：审计日志禁止修改');
                END;
            """))
            await conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete
                BEFORE DELETE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, '等保安全策略：审计日志禁止删除');
                END;
            """))
        except Exception as e:
            logging.info(f"审计触发器已存在或创建异常: {e}")
        
    # 播种初创数据
    async with AsyncSessionLocal() as session:
        # 1. 初始化预置角色
        default_roles = [
            {"code": "sysadmin", "name": "系统管理员", "permissions": ["policy:manage", "user:manage", "role:manage"], "max_clearance": 3},
            {"code": "auditadmin", "name": "审计管理员", "permissions": ["audit:view", "audit:export"], "max_clearance": 2},
            {"code": "ordinary", "name": "普通用户", "permissions": [], "max_clearance": 1}
        ]
        
        for role_data in default_roles:
            res = await session.execute(select(Role).where(Role.code == role_data["code"]))
            if not res.scalars().first():
                r = Role(**role_data)
                session.add(r)
        
        await session.commit()

        # 2. 初始化核心管理员
        # Modified: password_updated_at=None 触发首次登录强制改密（等保 8.1.4.2c）
        default_pwd = "Admin!@#123"
        hashed = Hasher.get_password_hash(default_pwd)
        
        sysadmin_res = await session.execute(select(User).where(User.username == "sysadmin"))
        if not sysadmin_res.scalars().first():
            new_sysadmin = User(
                username="sysadmin",
                hashed_password=hashed,
                role_code="sysadmin",
                password_updated_at=None  # Modified: 首次登录必须改密
            )
            session.add(new_sysadmin)
            
        auditadmin_res = await session.execute(select(User).where(User.username == "auditadmin"))
        if not auditadmin_res.scalars().first():
            new_auditadmin = User(
                username="auditadmin",
                hashed_password=hashed,
                role_code="auditadmin",
                password_updated_at=None  # Modified: 首次登录必须改密
            )
            session.add(new_auditadmin)

        await session.commit()
            
        # 3. 注入系统基线配置
        res_cfg = await session.execute(select(SystemConfig))
        if not res_cfg.scalars().first():
            defaults = [
                SystemConfig(key="LOGIN_MAX_FAILURES", value="5", description="最大容错值"),
                SystemConfig(key="LOGIN_LOCKOUT_MINUTES", value="30", description="惩罚隔离阈值"),
                SystemConfig(key="PWD_COMPLEXITY_ENFORCE", value="true", description="强制鉴别口令难度"),
                SystemConfig(key="SESSION_TIMEOUT_MINS", value="15", description="会话超时自动失效"),
                SystemConfig(key="PWD_MAX_AGE_DAYS", value="90", description="口令最长使用期限(天)"),
                SystemConfig(key="PWD_HISTORY_COUNT", value="5", description="密码历史记录数（禁止复用）"),
                SystemConfig(key="INACTIVE_DAYS_LIMIT", value="180", description="非活跃账号自动停用天数"),
            ]
            session.add_all(defaults)
            await session.commit()
            print("[SECURITY NOTICE] 等保基线及动态 RBAC 模型映射装载完毕。")

@app.get("/health")
def health_check():
    return {"status": "Safem System Operating Normally..."}
