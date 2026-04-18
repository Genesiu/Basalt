# Basalt 开发者手册

## 一、架构设计

### 1.1 分层架构

```
┌─────────────────────────────────────────┐
│            前端 (Vue 3 SPA)             │
├─────────────────────────────────────────┤
│          Nginx / 宝塔 (TLS)             │
├─────────────────────────────────────────┤
│     FastAPI 应用层                       │
│  ┌─────────────┬──────────────────────┐ │
│  │  core/ 🔒   │    modules/ 📦       │ │
│  │  安全内核    │    业务模块           │ │
│  │  (不可修改)  │    (开发者的领地)     │ │
│  └─────────────┴──────────────────────┘ │
├─────────────────────────────────────────┤
│        SQLAlchemy 2.0 (Async ORM)       │
├─────────────────────────────────────────┤
│        SQLite / PostgreSQL              │
└─────────────────────────────────────────┘
```

### 1.2 安全边界

框架的核心理念：**业务代码不需要也不应该直接处理安全逻辑。**

安全能力通过 Python 装饰器和依赖注入自动生效：

| 安全能力 | 接入方式 | 业务代码改动 |
|---------|---------|------------|
| 身份认证 | `Depends(get_current_user)` | 0 行 |
| 权限控制 | `dependencies=[RequirePermission("x:y")]` | 1 行 |
| 安全标记 | `dependencies=[RequireSecurityClearance(Level)]` | 1 行 |
| IP 白名单 | `dependencies=[Depends(ip_whitelist_checker)]` | 1 行 |
| 审计日志 | `await create_audit_log(...)` | 5 行 |
| 数据加密 | `cipher.encrypt(data)` | 1 行 |

### 1.3 双控体系

```
RBAC（你能做什么） ──→ RequirePermission("contract:manage")
  │                          │
  │  并行校验                 │
  │                          │
MAC（你能看什么密级）──→ RequireSecurityClearance(SENSITIVE)
```

两套控制体系独立运行，互不替代。一个用户可能有 `contract:manage` 权限，但如果其角色的 `max_clearance < SENSITIVE`，仍会被拦截。

---

## 二、快速开发指南

### 2.1 创建业务模块（完整示例）

以"合同管理"为例：

#### Step 1: 规划权限

```
contract:view    → 查看合同
contract:manage  → 新建/编辑合同
contract:export  → 导出合同数据
```

#### Step 2: 创建模型

```python
# modules/contract/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from core.database import Base
from core.security_label import SecurityLabelMixin

class Contract(Base, SecurityLabelMixin):
    __tablename__ = "contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    party_a = Column(String(100))
    party_b = Column(String(100))
    amount = Column(Float, default=0)
    encrypted_contact_phone = Column(String(255))  # 联系人手机号（密文）
    status = Column(String(20), default="draft")
    created_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    # security_level 由 SecurityLabelMixin 自动提供
```

#### Step 3: 创建 Pydantic Schema

```python
# modules/contract/schemas.py
from pydantic import BaseModel
from typing import Optional

class ContractCreate(BaseModel):
    title: str
    party_a: str
    party_b: str
    amount: float = 0
    contact_phone: Optional[str] = None  # 明文输入
    security_level: int = 1  # 默认"内部"

class ContractUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    security_level: Optional[int] = None
```

#### Step 4: 创建 API 路由

```python
# modules/contract/api.py
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_db
from core.auth import RequirePermission, get_current_user
from core.audit import create_audit_log
from core.crypto import AESCipher
from core.security_label import RequireSecurityClearance, SecurityLevel
from models.system import User
from .models import Contract
from .schemas import ContractCreate, ContractUpdate

router = APIRouter(tags=["合同管理"])
cipher = AESCipher()

def _mask_phone(phone: str) -> str:
    return phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else "****"

def _contract_to_dict(c: Contract) -> dict:
    return {
        "id": c.id, "title": c.title,
        "party_a": c.party_a, "party_b": c.party_b,
        "amount": c.amount, "status": c.status,
        "phone_masked": _mask_phone(cipher.decrypt(c.encrypted_contact_phone)) 
            if c.encrypted_contact_phone else None,
        "security_level": c.security_level,
        "security_label": SecurityLevel.label(c.security_level),
        "created_by": c.created_by,
    }


@router.get("/", dependencies=[RequirePermission("contract:view")])
async def list_contracts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contract).order_by(Contract.id.desc()))
    return [_contract_to_dict(c) for c in result.scalars().all()]


@router.post("/", dependencies=[
    RequirePermission("contract:manage"),
    RequireSecurityClearance(SecurityLevel.INTERNAL)
])
async def create_contract(
    request: Request, body: ContractCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_contract = Contract(
        title=body.title, party_a=body.party_a, party_b=body.party_b,
        amount=body.amount, created_by=current_user.username,
        security_level=body.security_level,
        encrypted_contact_phone=cipher.encrypt(body.contact_phone) if body.contact_phone else None,
    )
    db.add(new_contract)
    await db.commit()
    await db.refresh(new_contract)

    await create_audit_log(
        db=db, request=request,
        action="CREATE_CONTRACT", status="SUCCESS",
        details={"title": body.title, "amount": body.amount},
        current_user_id=current_user.username
    )
    return {"message": "合同创建成功", "id": new_contract.id}
```

#### Step 5: 注册路由

```python
# main.py 添加：
from modules.contract.api import router as contract_router
app.include_router(contract_router, prefix="/api/v1/contracts")
```

#### Step 6: 分配权限

通过管理后台给角色添加 `contract:view` / `contract:manage` 权限。

---

## 三、安全约束清单

### 3.1 绝对禁止

| 编号 | 禁止行为 | 原因 |
|------|---------|------|
| S-01 | 修改 `core/` 目录 | 破坏安全基线 |
| S-02 | 明文存储 PII | 等保 8.1.4.7 |
| S-03 | 不挂权限的写接口 | 等保 8.1.4.2 |
| S-04 | 跳过审计日志 | 等保 8.1.4.3 |
| S-05 | 拼接 raw SQL | 注入风险 |
| S-06 | 在日志中打印密码/Token | 信息泄露 |
| S-07 | 使用国家保密术语 | 法律风险 |
| S-08 | 提交 `.env` 到 Git | 密钥泄露 |

### 3.2 推荐实践

| 编号 | 实践 | 说明 |
|------|------|------|
| R-01 | 业务 Model 继承 SecurityLabelMixin | 获得安全标记能力 |
| R-02 | 敏感 API 同时挂 RBAC + MAC | 双重访问控制 |
| R-03 | 查询返回脱敏数据 | 手机号: 138****8000 |
| R-04 | 使用 Pydantic Schema 做输入校验 | 防止非法输入 |
| R-05 | 管理接口加 `ip_whitelist_checker` | 网络边界控制 |

---

## 四、环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `AES_ENCRYPTION_KEY_B64` | ✅ | AES-256 加密密钥（Base64）。首次启动自动生成到 `.env` |
| `JWT_SECRET_KEY` | ✅ | JWT 签名密钥。首次启动自动生成到 `.env` |
| `CORS_ORIGINS` | 生产必需 | CORS 白名单，逗号分隔。如：`https://app.example.com,https://admin.example.com` |

---

## 五、数据库迁移

开发环境使用 SQLite，生产建议 PostgreSQL。

### 切换到 PostgreSQL

1. 修改 `core/database.py`：
```python
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://user:pass@host/basalt")
```

2. 安装驱动：
```bash
pip install asyncpg
```

3. `main.py` 中移除 SQLite 触发器代码（PostgreSQL 需使用原生触发器）。

---

## 六、备份策略

```bash
# 添加到 crontab（每天 2:00 执行）
0 2 * * * /path/to/basalt/backup.sh

# 备份脚本功能：
# 1. sqlite3 .dump → SQL 文件
# 2. gzip 压缩
# 3. SHA-256 校验码
# 4. 自动清理 30 天前的备份
```

---

## 七、等保测评材料准备

框架可直接输出以下测评材料：

| 材料 | 来源 |
|------|------|
| 用户列表与权限矩阵 | `GET /api/v1/users/` + `GET /api/v1/roles/` |
| 操作审计日志 | `GET /api/v1/audit/export/csv` |
| 密码策略配置 | `GET /api/v1/config/` |
| IP 白名单 | `GET /api/v1/config/whitelist` |
| 安全等级定义 | `GET /api/v1/roles/security-levels` |
| 数据备份记录 | `backup.sh` 输出日志 |
