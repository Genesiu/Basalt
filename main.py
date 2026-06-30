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

from contextlib import asynccontextmanager  # Added: [L-07] lifespan 上下文
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


# ============================================================
# Modified: [L-07] 使用 lifespan 上下文管理器替代已废弃的 @app.on_event
# ============================================================

async def _setup_db_triggers(conn):
    """根据数据库类型自动部署审计防删改触发器（等保 8.1.4.3c）"""
    db_type = get_db_type()

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

    elif db_type == "mysql":
        # Modified: MySQL 审计触发器自动部署（不再需要手动执行 SQL）
        for trigger_name, op in [("audit_logs_no_update", "UPDATE"), ("audit_logs_no_delete", "DELETE")]:
            try:
                await conn.execute(text(f"DROP TRIGGER IF EXISTS {trigger_name}"))
                await conn.execute(text(f"""
                    CREATE TRIGGER {trigger_name}
                    BEFORE {op} ON audit_logs
                    FOR EACH ROW
                    BEGIN
                        SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = '等保安全策略：审计日志禁止修改或删除';
                    END
                """))
            except Exception as e:
                logging.warning(f"MySQL 审计触发器 {trigger_name} 部署异常: {e}")
        logging.info("[MySQL] 审计防删改触发器已自动部署。")

    elif db_type == "postgresql":
        # PostgreSQL 审计触发器自动部署
        try:
            await conn.execute(text("""
                CREATE OR REPLACE FUNCTION audit_logs_protect() RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION '等保安全策略：审计日志禁止修改或删除';
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql;
            """))
            for op in ["UPDATE", "DELETE"]:
                trigger_name = f"audit_logs_no_{op.lower()}"
                await conn.execute(text(f"DROP TRIGGER IF EXISTS {trigger_name} ON audit_logs"))
                await conn.execute(text(f"""
                    CREATE TRIGGER {trigger_name}
                    BEFORE {op} ON audit_logs
                    FOR EACH ROW EXECUTE FUNCTION audit_logs_protect();
                """))
        except Exception as e:
            logging.warning(f"PostgreSQL 审计触发器部署异常: {e}")
        logging.info("[PostgreSQL] 审计防删改触发器已自动部署。")


async def _seed_initial_data():
    """播种初创数据"""
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
                session.add(Role(**role_data))
        await session.commit()

        # 2. 初始化核心管理员（随机密码 + 首次登录强制改密）
        sysadmin_res = await session.execute(select(User).where(User.username == "sysadmin"))
        auditadmin_res = await session.execute(select(User).where(User.username == "auditadmin"))
        need_init = not sysadmin_res.scalars().first() or not auditadmin_res.scalars().first()

        if need_init:
            default_pwd = base64.b64encode(os.urandom(12)).decode()
            hashed = Hasher.get_password_hash(default_pwd)

            sysadmin_res2 = await session.execute(select(User).where(User.username == "sysadmin"))
            if not sysadmin_res2.scalars().first():
                session.add(User(username="sysadmin", hashed_password=hashed,
                    role_code="sysadmin", password_updated_at=None))
                
            auditadmin_res2 = await session.execute(select(User).where(User.username == "auditadmin"))
            if not auditadmin_res2.scalars().first():
                session.add(User(username="auditadmin", hashed_password=hashed,
                    role_code="auditadmin", password_updated_at=None))
            await session.commit()

            # Modified: [Q-03 安全修复] 初始密码写入临时文件而非日志流
            # 防止容器化部署中密码被日志收集系统（ELK/Splunk）永久捕获
            _pwd_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".initial_password")
            with open(_pwd_file, "w") as pf:
                pf.write(f"初始管理员密码: {default_pwd}\n")
                pf.write("⚠️ 请立即登录修改密码，然后删除此文件！\n")
            os.chmod(_pwd_file, 0o600)
            logging.warning(f"[SECURITY NOTICE] 初始管理员密码已写入 {_pwd_file}，请查阅后立即删除。")
            
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

        # 4. 初始化默认 IP 白名单（全放行，避免云服务器首次部署被锁死）
        res_wl = await session.execute(select(IPWhitelist))
        if not res_wl.scalars().first():
            session.add_all([
                IPWhitelist(ip_network="0.0.0.0/0", description="默认放行所有 IPv4（生产环境请通过管理后台收紧为管理网段）"),
                IPWhitelist(ip_network="::/0", description="默认放行所有 IPv6（生产环境请通过管理后台收紧为管理网段）"),
            ])
            await session.commit()
            logging.warning("[SECURITY NOTICE] 已植入默认 IP 白名单 (0.0.0.0/0 全放行)。生产环境请在管理后台「安全策略 → IP 白名单」中收紧为管理网段。")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modified: [L-07] FastAPI lifespan 上下文管理器 — 替代已废弃的 @app.on_event"""
    # ---- STARTUP ----
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Added: 自动迁移 — create_all 不会 ALTER 已存在的表，需手动补列
        if is_sqlite():
            try:
                await conn.execute(text("SELECT prev_hash FROM audit_logs LIMIT 1"))
            except Exception:
                await conn.execute(text("ALTER TABLE audit_logs ADD COLUMN prev_hash VARCHAR(64) DEFAULT 'GENESIS'"))
                logging.info("[迁移] 已为 audit_logs 表添加 prev_hash 列")
        await _setup_db_triggers(conn)
    
    await _seed_initial_data()

    # 启动定时任务调度器（备份 + LoginAttempt 清理）
    from core.scheduler import start_scheduler
    start_scheduler()

    yield  # ---- 应用运行中 ----

    # ---- SHUTDOWN ----
    from core.scheduler import stop_scheduler
    stop_scheduler()
    logging.info("[Basalt] 系统正常关闭。")


# ============================================================
# FastAPI 实例（使用 lifespan 替代 on_event）
# ============================================================
app = FastAPI(
    title="Basalt Framework — AI-Native Security Microkernel",
    description="Build on Basalt. Secure by default. | by Genesiu",
    version="2.4.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    lifespan=lifespan,
)

# Modified: [M-01 安全修复] CORS 生产模式拒绝通配符
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "*")
if _cors_origins_raw == "*":
    if _is_production:
        raise RuntimeError(
            "致命错误：生产模式下 CORS_ORIGINS 不可为 '*'。"
            "请在 .env 中设置 CORS_ORIGINS 为受信域名列表（逗号分隔）。"
        )
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

# Added: 内存级速率限制中间件（登录/验证码接口防爆破第一道防线）
from core.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware, rate_limit=20, window_seconds=60)


# ============================================================
# 安全响应头中间件（等保 8.1.3 + OWASP 推荐）
# ============================================================
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # Modified: [L-06] CSP 替代废弃的 X-XSS-Protection
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

app.add_middleware(SecurityHeadersMiddleware)


# ============================================================
# 全局异常处理 — 生产环境不泄露堆栈
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: StarletteRequest, exc: Exception):
    logging.error(f"[全局异常] {request.method} {request.url}: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": "内部服务错误，已记录。请联系管理员。"}
    )


# ============================================================
# 路由注册
# ============================================================
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(config_router, prefix="/api/v1/config")
app.include_router(audit_router, prefix="/api/v1/audit")
app.include_router(user_router, prefix="/api/v1/users")
app.include_router(role_router, prefix="/api/v1/roles")
app.include_router(compliance_router, prefix="/api/v1/compliance")
app.include_router(example_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "Basalt Framework Operating Normally", "db": get_db_type()}
