# Basalt

**面向等保三级的安全微内核框架**

[![GB/T 22239-2019](https://img.shields.io/badge/等保三级-GB%2FT%2022239--2019-00b894)](https://www.gb688.cn/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Basalt 是一个安全基座框架。开发者只需专注业务逻辑，身份鉴别、访问控制、审计追踪、数据加密等等保三级合规能力已内建于框架。

## 核心特性

| 能力 | 实现 | 等保条款 |
|------|------|---------|
| 动态 RBAC | `RequirePermission` 装饰器 + 原子权限 | 8.1.4.2 |
| 安全标记 MAC | `RequireSecurityClearance` + `SecurityLabelMixin` | 8.1.4.2g/h |
| 三员分立 | sysadmin / auditadmin / ordinary | 8.1.5 |
| 多因素认证 | TOTP（管理员强制） | 8.1.4.1h |
| 全链路审计 | 同步写入 + 数据库触发器防删改 + 链式哈希防篡改 | 8.1.4.3 |
| 数据加密 | AES-256-GCM + bcrypt | 8.1.4.7-8 |
| 防暴力破解 | IP 级 + 账号级双维度锁定 | 8.1.4.1d/e |
| 密码策略 | 复杂度 + 历史 + 过期 + 首登改密 | 8.1.4.1 |
| IP 白名单 | CIDR 段级管理接口限制 | 8.1.4.4c |
| 数据备份 | APScheduler + WebUI 控制 + SHA-256 校验 | 8.1.4.9 |

## 快速启动

```bash
# 克隆
git clone https://github.com/Genesiu/Basalt.git && cd Basalt

# 环境
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 启动（无需任何额外配置）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 零配置自动初始化

克隆即用，无需手动创建任何文件。首次启动时，框架自动完成全部初始化：

```
uvicorn main:app 启动
  │
  ├─ 1. 检测 .env 不存在 → 自动生成密钥文件
  │     ├─ AES_ENCRYPTION_KEY_B64（数据加密密钥）
  │     ├─ JWT_SECRET_KEY（会话签名密钥）
  │     └─ chmod 600（仅属主可读）
  │
  ├─ 2. 检测数据库不存在 → 自动创建
  │     ├─ 创建全部表结构
  │     ├─ 注入审计日志防删改触发器
  │     └─ 播种等保基线配置参数
  │
  ├─ 3. 播种默认角色
  │     ├─ sysadmin  → 系统管理员（安全等级：核心）
  │     ├─ auditadmin → 审计管理员（安全等级：敏感）
  │     └─ ordinary  → 普通用户（安全等级：内部）
  │
  └─ 4. 播种默认管理员账号（随机密码 + 首次登录强制修改）
        ├─ sysadmin  / <见 .initial_password 文件>
        └─ auditadmin / <同上>
```

> `.env`、`basalt.db`、`.initial_password` 均被 `.gitignore` 排除，不会提交到 Git。
> 每个开发者克隆后首次启动都会自动生成独立的密钥和数据库。

### 默认账号

| 用户名 | 密码 | 角色 | 首次登录 |
|--------|------|------|----------|
| `sysadmin` | 见项目根目录 `.initial_password` | 系统管理员 | 强制改密 |
| `auditadmin` | 同上 | 审计管理员 | 强制改密 |

## 项目结构

```
basalt/
├── main.py                 # 应用入口、启动播种、中间件
├── core/                   # 框架安全内核
│   ├── auth.py             # JWT 签发/校验、RequirePermission
│   ├── auth_router.py      # 登录、改密、TOTP 绑定
│   ├── audit.py            # 同步审计写入引擎
│   ├── audit_router.py     # 审计日志查询 + CSV 导出
│   ├── config_router.py    # 等保基线参数配置
│   ├── user_router.py      # 用户 CRUD + 停用擦除
│   ├── role_router.py      # 角色管理 + 安全等级
│   ├── crypto.py           # AES-256-GCM + bcrypt
│   ├── policy.py           # 密码策略引擎
│   ├── password_service.py # 密码历史公共服务
│   ├── ip_filter.py        # IP 白名单网关
│   ├── mfa_totp.py         # TOTP 双因子认证
│   ├── security_label.py   # 安全标记 MAC 骨架
│   ├── rate_limit.py       # 内存级滑动窗口限流
│   ├── scheduler.py        # APScheduler 备份调度
│   ├── captcha.py          # 图形验证码
│   └── database.py         # SQLAlchemy Async 引擎
├── models/
│   ├── system.py           # User、Role、PasswordHistory 等
│   └── audit_log.py        # 审计日志表（含链式哈希）
├── modules/                # 业务模块放这里
│   └── example_app/        # 示例模块
├── frontend/               # Vue 3 管理后台界面
│   ├── src/views/
│   │   ├── LoginPage.vue
│   │   └── AdminDashboard.vue
│   ├── src/utils/request.js
│   └── vite.config.js
├── docs/
│   ├── API.md              # REST API 接口文档
│   ├── COMPLIANCE_GUIDE.md # 等保三级测评指引
│   ├── DEPLOY.md           # 生产环境部署指南
│   └── DEVELOPMENT.md      # 开发者手册
├── backups/                # 数据库备份目录（自动创建）
├── requirements.txt
└── .env                    # 自动生成的密钥（不提交 Git）
```

## 如何在 Basalt 上构建业务

三步接入：

```python
# 1. 创建业务 Model（可选：继承 SecurityLabelMixin 获得安全标记）
from core.database import Base
from core.security_label import SecurityLabelMixin
from sqlalchemy import Column, Integer, String

class Contract(Base, SecurityLabelMixin):
    __tablename__ = "contracts"
    id = Column(Integer, primary_key=True)
    title = Column(String(200))

# 2. 创建业务路由（挂载安全装饰器）
from fastapi import APIRouter, Depends, Request
from core.auth import RequirePermission
from core.security_label import RequireSecurityClearance, SecurityLevel
from core.audit import create_audit_log

router = APIRouter(prefix="/contracts", tags=["合同管理"])

@router.get("/", dependencies=[
    RequirePermission("contract:view"),
    RequireSecurityClearance(SecurityLevel.SENSITIVE)
])
async def list_contracts(db = Depends(get_db)):
    ...

# 3. 在 main.py 注册路由
app.include_router(contract_router, prefix="/api/v1")
```

身份鉴别、权限校验、审计日志、IP 限制全部由框架处理，业务代码不需要关心。

## 部署说明

框架默认使用 SQLite，适合单机部署和开发测试。生产环境支持切换到 PostgreSQL 或 MySQL，只需修改 `.env` 中的 `DATABASE_URL`。

当前版本仅支持单 Worker 部署（`uvicorn --workers 1`）。验证码、Token 黑名单、速率限制等机制使用进程内存缓存，多 Worker 下会不一致。如需水平扩展，需引入 Redis 作为共享存储层。

## 文档

- [API 接口文档](docs/API.md)
- [开发者手册](docs/DEVELOPMENT.md)
- [部署指南](docs/DEPLOY.md)
- [等保测评指引](docs/COMPLIANCE_GUIDE.md)

## 合规声明

本框架遵循 GB/T 22239-2019《信息安全技术 网络安全等级保护基本要求》第三级标准设计。框架内置的安全标记等级（公开/内部/敏感/核心）为企业数据分类术语，与《中华人民共和国保守国家秘密法》所定义的国家秘密等级无关。

## License

MIT
