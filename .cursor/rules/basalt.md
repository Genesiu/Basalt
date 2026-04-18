---
description: Basalt 安全框架开发规范
globs: ["**/*.py"]
alwaysApply: true
---

# Basalt Framework 开发规约

你正在 Basalt 安全微内核框架中工作。这是一个符合等保三级（GB/T 22239-2019）的安全基座。

## 核心规则

1. **绝不修改 `core/` 目录** — 这是安全内核，所有业务代码放在 `modules/` 中
2. **所有写入接口必须挂 `RequirePermission`** — 无例外
3. **所有写入操作必须记审计** — `await create_audit_log(db=db, request=request, ...)`
4. **PII 数据必须 AES 加密** — `cipher.encrypt(data)` 存储，`cipher.decrypt(data)` 读取
5. **安全标记术语** — 只用「公开/内部/敏感/核心」，禁用「秘密/机密/绝密」

## 代码模板

新建路由：
```python
from core.auth import RequirePermission, get_current_user
from core.audit import create_audit_log
from core.database import get_db

@router.post("/", dependencies=[RequirePermission("{module}:manage")])
async def create_item(request: Request, body: Schema, db = Depends(get_db), user = Depends(get_current_user)):
    # 业务逻辑...
    await create_audit_log(db=db, request=request, action="CREATE_ITEM", details={...}, current_user_id=user.username)
```

## 结构

- `core/auth.py` → RequirePermission, get_current_user
- `core/audit.py` → create_audit_log (async)
- `core/crypto.py` → AESCipher, Hasher
- `core/security_label.py` → SecurityLevel, SecurityLabelMixin, RequireSecurityClearance
- `core/database.py` → get_db, Base
