# Basalt

**生而合规的 AI-Native 安全微内核框架**

[![GB/T 22239-2019](https://img.shields.io/badge/等保三级-GB%2FT%2022239--2019-00b894)](https://www.gb688.cn/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Basalt 是一个面向 **AI Vibecoding** 的安全基座框架。开发者（或 AI 编码助手）只需专注业务逻辑，身份鉴别、访问控制、审计追踪、数据加密等等保三级合规能力**已内建于框架**。

## ✨ 核心特性

| 能力 | 实现 | 等保条款 |
|------|------|---------|
| 🔐 动态 RBAC | `RequirePermission` 装饰器 + 原子权限 | 8.1.4.2 |
| 🏷️ 安全标记 MAC | `RequireSecurityClearance` + `SecurityLabelMixin` | 8.1.4.2g/h |
| 🛡️ 三员分立 | sysadmin / auditadmin / ordinary | 8.1.5 |
| 🔑 多因素认证 | TOTP（管理员强制） | 8.1.4.1h |
| 📝 全链路审计 | 同步写入 + SQLite 触发器防删改 | 8.1.4.3 |
| 🔒 数据加密 | AES-256-GCM + bcrypt | 8.1.4.7-8 |
| 🚫 防暴力破解 | IP 级 + 账号级双维度锁定 | 8.1.4.1d/e |
| 📋 密码策略 | 复杂度 + 历史 + 过期 + 首登改密 | 8.1.4.1 |
| 🌐 IP 白名单 | CIDR 段级管理接口限制 | 8.1.4.4c |
| 💾 数据备份 | APScheduler + WebUI 控制 + SHA-256 校验 | 8.1.4.9 |

## 🚀 5 分钟快速启动

```bash
# 1. 克隆
git clone https://github.com/Genesiu/Basalt.git && cd Basalt

# 2. 环境
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. 启动（无需任何额外配置）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 零配置自动初始化

**克隆即用，无需手动创建任何文件。** 首次 `uvicorn main:app` 启动时，框架会自动完成全部初始化：

```
uvicorn main:app 启动
  │
  ├─ 1. 检测 .env 不存在 → 自动生成密钥文件
  │     ├─ AES_ENCRYPTION_KEY_B64（数据加密密钥）
  │     ├─ JWT_SECRET_KEY（会话签名密钥）
  │     └─ chmod 600（仅属主可读）
  │
  ├─ 2. 检测 basalt.db 不存在 → 自动创建数据库
  │     ├─ 创建全部表结构（User/Role/AuditLog/...）
  │     ├─ 注入审计日志防删改触发器
  │     └─ 播种等保基线配置参数
  │
  ├─ 3. 播种默认角色
  │     ├─ sysadmin  → 系统管理员（安全等级：核心）
  │     ├─ auditadmin → 审计管理员（安全等级：敏感）
  │     └─ ordinary  → 普通用户（安全等级：内部）
  │
  └─ 4. 播种默认管理员账号（密码首次登录强制修改）
        ├─ sysadmin / Admin!@#123
        └─ auditadmin / Admin!@#123
```

> **注意**：`.env` 和 `basalt.db` 被 `.gitignore` 排除，不会提交到 Git。
> 每个开发者克隆后首次启动都会自动生成自己的独立密钥和数据库，**互不影响**。

### 默认账号

| 用户名 | 密码 | 角色 | 首次登录 |
|--------|------|------|---------|
| `sysadmin` | `Admin!@#123` | 系统管理员 | 强制改密 |
| `auditadmin` | `Admin!@#123` | 审计管理员 | 强制改密 |

## 📁 项目结构

```
basalt/
├── main.py                 # 应用入口、启动播种、CORS、审计触发器
├── core/                   # 框架安全内核（不可修改）
│   ├── auth.py             # JWT 签发/校验、RequirePermission
│   ├── auth_router.py      # 登录、改密、TOTP 绑定
│   ├── audit.py            # 同步审计写入引擎
│   ├── audit_router.py     # 审计日志查询 + CSV 导出
│   ├── config_router.py    # 等保基线参数配置
│   ├── user_router.py      # 用户 CRUD + 停用擦除
│   ├── role_router.py      # 角色管理 + 安全等级
│   ├── crypto.py           # AES-256-GCM + bcrypt (双层加密)
│   ├── policy.py           # 密码策略引擎
│   ├── ip_filter.py        # IP 白名单网关
│   ├── mfa_totp.py         # TOTP 双因子认证
│   ├── security_label.py   # 安全标记 MAC 骨架
│   ├── scheduler.py        # APScheduler 备份调度
│   └── database.py         # SQLAlchemy Async 引擎
├── models/
│   ├── system.py           # User、Role、PasswordHistory 等
│   └── audit_log.py        # 审计日志表
├── modules/                # ⬇️ 你的业务模块放这里
│   └── example_app/        # 示例模块
├── frontend/               # 🖥️ Vue 3 管理后台界面
│   ├── src/views/
│   │   ├── LoginPage.vue   # 登录页（含 TOTP 验证码）
│   │   └── AdminDashboard.vue  # 管控平台主界面
│   ├── src/utils/request.js    # Axios 封装
│   └── vite.config.js      # Vite 构建配置
├── docs/                   # 📖 文档
│   ├── API.md              # REST API 接口文档
│   ├── COMPLIANCE_GUIDE.md # 等保三级测评指引
│   ├── DEPLOY.md           # 生产环境部署指南
│   └── DEVELOPMENT.md      # 开发者手册
├── backups/                # 数据库备份目录（自动创建）
├── requirements.txt        # Python 依赖
└── .env                    # 自动生成的密钥（不提交 Git）
```

## 🏗️ 如何在 Basalt 上构建业务

**3 步接入：**

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

**就这么简单。** 身份鉴别、权限校验、审计日志、IP 限制全部由框架自动处理。

## 🤖 AI 辅助开发

Basalt 是 **AI-Native** 框架。项目内置了 AI 编码助手的上下文文件：

- **`CLAUDE.md`** — Claude Code / Claude 桌面版自动加载
- **`.cursor/rules/basalt.md`** — Cursor 编辑器自动加载

用 AI 开发业务只需要说：

> "帮我在 Basalt 框架上创建一个合同管理模块，包含 CRUD 接口，敏感数据加密，需要 contract:view 和 contract:manage 两个权限节点。"

AI 会自动遵循框架规范生成合规代码。

## 📖 文档

- [API 接口文档](docs/API.md) — 全部 REST API 详细说明
- [开发者手册](docs/DEVELOPMENT.md) — 架构设计、扩展指南、安全约束
- [部署指南](docs/DEPLOY.md) — 生产环境部署、Nginx 配置、备份策略
- [等保测评指引](docs/COMPLIANCE_GUIDE.md) — GB/T 22239 条款到功能的可验证映射

## 📜 合规声明

本框架遵循 **GB/T 22239-2019《信息安全技术 网络安全等级保护基本要求》** 第三级标准设计。框架内置的安全标记等级（公开/内部/敏感/核心）为**企业数据分类术语**，与《中华人民共和国保守国家秘密法》所定义的国家秘密等级无关。

## License

MIT
