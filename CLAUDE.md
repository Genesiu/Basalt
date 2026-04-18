# CLAUDE.md — Basalt AI 开发上下文

> 本文件供 Claude Code / Claude Desktop / Claude API 自动加载。
> 当开发者在本项目中使用 Claude 进行二次开发时，Claude 会自动读取此文件理解框架约束。

## 你正在操作的项目

Basalt 是一个符合 GB/T 22239-2019（等保三级）标准的 **安全微内核框架**。
技术栈：FastAPI + SQLAlchemy 2.0 (Async) + SQLite/PostgreSQL + Vue 3。
所有安全能力（鉴权、审计、加密、MAC）已内建于 `core/` 目录，**禁止修改 core/ 下的文件**。

## 强制规则（MUST）

### 1. 路由安全装饰器

**所有业务 API 必须挂载至少一个安全装饰器：**

```python
from core.auth import RequirePermission
from core.security_label import RequireSecurityClearance, SecurityLevel

# 最小示例
@router.get("/items", dependencies=[RequirePermission("item:view")])

# 完整示例（RBAC + MAC 双重控制）
@router.post("/items", dependencies=[
    RequirePermission("item:manage"),
    RequireSecurityClearance(SecurityLevel.SENSITIVE),
    Depends(ip_whitelist_checker)  # 仅管理接口需要
])
```

### 2. 审计日志

**所有写操作（POST/PUT/DELETE）必须调用审计：**

```python
from core.audit import create_audit_log

@router.post("/items")
async def create_item(request: Request, db: AsyncSession = Depends(get_db), ...):
    # ... 业务逻辑 ...
    await create_audit_log(
        db=db, request=request,
        action="CREATE_ITEM",        # 动作名：大写下划线
        status="SUCCESS",            # SUCCESS / FAILED / BLOCKED
        details={"key": "value"},    # 可序列化的上下文
        current_user_id=user.username
    )
```

**注意**：`create_audit_log` 是 **async** 函数，必须 `await` 调用。

### 3. 敏感数据加密

**涉及手机号、身份证、银行卡等 PII 数据，必须使用 AES-256-GCM：**

```python
from core.crypto import AESCipher
cipher = AESCipher()

encrypted = cipher.encrypt("13800138000")   # 加密
plaintext = cipher.decrypt(encrypted)        # 解密
```

### 4. 密码哈希

**禁止明文存储密码。使用框架提供的 bcrypt 封装：**

```python
from core.crypto import Hasher
hashed = Hasher.get_password_hash("MyP@ss123")
is_valid = Hasher.verify_password("MyP@ss123", hashed)
```

### 5. 安全标记（可选但推荐）

**业务 Model 继承 `SecurityLabelMixin` 即可获得数据密级字段：**

```python
from core.security_label import SecurityLabelMixin, SecurityLevel

class Document(Base, SecurityLabelMixin):
    __tablename__ = "documents"
    title = Column(String(200))
    # 自动获得 security_level 列（默认 INTERNAL）
```

安全等级使用企业术语（非国家秘密等级）：
- `SecurityLevel.PUBLIC` (0) = 公开
- `SecurityLevel.INTERNAL` (1) = 内部
- `SecurityLevel.SENSITIVE` (2) = 敏感
- `SecurityLevel.CORE` (3) = 核心

### 6. 权限节点命名规范

格式：`{模块}:{动作}`，全小写，冒号分隔。

```
contract:view      # 查看合同
contract:manage    # 增删改合同
contract:export    # 导出合同数据
report:generate    # 生成报表
```

## 禁止事项（MUST NOT）

1. ❌ 禁止修改 `core/` 目录下的任何文件
2. ❌ 禁止使用 `BackgroundTasks` 做审计日志（已改为同步）
3. ❌ 禁止明文存储密码或敏感数据
4. ❌ 禁止创建不挂 `RequirePermission` 的写入接口
5. ❌ 禁止在安全标记中使用"秘密""机密""绝密"等国家保密术语
6. ❌ 禁止将 `.env` 文件提交到 Git
7. ❌ 禁止直接操作 `audit_logs` 表的 UPDATE/DELETE

## 项目结构速查

```
basalt/
├── core/                   # 🔒 安全内核（只读）
│   ├── auth.py             # RequirePermission, get_current_user, JWT
│   ├── security_label.py   # RequireSecurityClearance, SecurityLabelMixin
│   ├── audit.py            # create_audit_log (async)
│   ├── crypto.py           # AESCipher, Hasher
│   ├── policy.py           # PasswordPolicyEngine
│   ├── ip_filter.py        # ip_whitelist_checker
│   └── database.py         # get_db, Base, AsyncSessionLocal
├── models/system.py        # User, Role, PasswordHistory, LoginAttempt
├── modules/                # 📦 业务模块目录
│   └── example_app/        # 示例（参考此结构）
└── main.py                 # 路由注册入口
```

## 新建业务模块标准流程

```
1. 创建 modules/my_module/
   ├── __init__.py
   ├── models.py       # SQLAlchemy 模型
   ├── schemas.py      # Pydantic 请求/响应模型
   └── api.py          # FastAPI 路由

2. 在 main.py 注册：
   from modules.my_module.api import router as my_router
   app.include_router(my_router, prefix="/api/v1")

3. 在角色管理中添加对应权限节点（如 "mymodule:view", "mymodule:manage"）
```

## 关键 API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | /api/v1/auth/login | 登录（OAuth2 表单） |
| POST | /api/v1/auth/reset-expired-password | 首登/过期改密 |
| PUT | /api/v1/auth/change-password | 已登录改密 |
| POST | /api/v1/auth/totp/setup | 绑定 TOTP |
| GET | /api/v1/users/me | 当前用户信息 + 权限树 |
| GET | /api/v1/roles/ | 角色列表 |
| GET | /api/v1/roles/security-levels | 安全等级选项 |
| GET | /api/v1/audit/ | 审计日志 |
| GET | /api/v1/audit/export/csv | 导出审计 CSV |

## 数据库

- 开发：SQLite (`basalt.db`)
- 生产：建议 PostgreSQL
- ORM：SQLAlchemy 2.0 Async
- 获取会话：`db: AsyncSession = Depends(get_db)`
