import os
import base64
import logging
import traceback

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
    # Added: 数据库 URL（默认 SQLite，可切换 PostgreSQL/MySQL）
    if "DATABASE_URL" not in env_vars:
        env_vars["DATABASE_URL"] = "sqlite+aiosqlite:///./basalt.db"
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
from core.database import engine, Base, AsyncSessionLocal, is_sqlite, get_db_type
from sqlalchemy.future import select
from sqlalchemy import text
from models.system import User, Role, SystemConfig, IPWhitelist
from core.crypto import Hasher

from modules.example_app.api import router as example_router
from core.auth_router import router as auth_router
from core.config_router import router as config_router
from core.audit_router import router as audit_router
from core.user_router import router as user_router
from core.role_router import router as role_router
from core.compliance_router import router as compliance_router

from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse

# 生产模式下隐藏交互式文档（通过环境变量 PRODUCTION=true 启用）
_is_production = os.environ.get("PRODUCTION", "").lower() in ("true", "1", "yes")

app = FastAPI(
    title="Basalt Framework — AI-Native Security Microkernel",
    description="Build on Basalt. Secure by default. | by Genesiu",
    version="2.3.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
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
    expose_headers=["X-Password-Expired", "X-TOTP-Required", "X-Captcha-Required"],
)


# ============================================================
# 安全响应头中间件（等保 8.1.3 + OWASP 推荐）
# ============================================================
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # API 响应禁止缓存（防止敏感数据被浏览器缓存）
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

app.add_middleware(SecurityHeadersMiddleware)


# ============================================================
# 全局异常处理器（隐藏堆栈跟踪，防止信息泄露）
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: StarletteRequest, exc: Exception):
    """捕获所有未处理异常，生产环境不暴露堆栈信息"""
    logging.error(f"[未捕获异常] {request.method} {request.url.path}: {type(exc).__name__}: {exc}")
    if not _is_production:
        logging.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请联系管理员。"},
    )

app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(config_router, prefix="/api/v1/config")
app.include_router(audit_router, prefix="/api/v1/audit")
app.include_router(user_router, prefix="/api/v1/users")
app.include_router(role_router, prefix="/api/v1/roles")
app.include_router(compliance_router, prefix="/api/v1/compliance")
app.include_router(example_router, prefix="/api/v1")

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # 等保 8.1.4.3c — 审计日志防删改触发器（按数据库类型条件执行）
        if is_sqlite():
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
        else:
            # PostgreSQL/MySQL: 需手动部署对应触发器，参见 docs/DEPLOY.md
            logging.info(f"[{get_db_type()}] 非 SQLite 环境，请手动部署审计防删改触发器。")
        
    # 播种初创数据
    async with AsyncSessionLocal() as session:
        # 1. 初始化预置角色
        default_roles = [
            {"code": "sysadmin", "name": "系统管理员", "permissions": ["policy:manage", "user:manage", "role:manage", "audit:view", "audit:export"], "max_clearance": 3},
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
            print(f"[SECURITY NOTICE] 等保基线及动态 RBAC 模型映射装载完毕。[DB: {get_db_type()}]")

        # 4. 初始化默认 IP 白名单（避免首次部署被锁死）
        res_wl = await session.execute(select(IPWhitelist))
        if not res_wl.scalars().first():
            default_whitelist = [
                IPWhitelist(ip_network="0.0.0.0/0", description="默认放行所有 IPv4（生产环境请收紧为管理网段）"),
                IPWhitelist(ip_network="::/0", description="默认放行所有 IPv6（生产环境请收紧为管理网段）"),
            ]
            session.add_all(default_whitelist)
            await session.commit()
            print("[SECURITY NOTICE] 已植入默认 IP 白名单 (0.0.0.0/0)，生产环境请在管理后台「安全策略」中收紧。")

    # Added: 内置定时备份调度器（替代 crontab）
    from core.scheduler import start_scheduler
    start_scheduler()

@app.get("/health")
def health_check():
    return {"status": "Basalt Framework Operating Normally", "db": get_db_type()}
