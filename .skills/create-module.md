---
trigger: create_module
description: 在 Basalt 框架上创建新的业务模块
globs: ["modules/**/*.py"]
alwaysApply: false
---

# Skill: 创建 Basalt 业务模块

当用户要求创建新的业务模块时，严格按以下流程执行。

## 前置检查

1. 确认模块名称和业务需求
2. 确认需要的权限节点（格式：`模块名:动作`）
3. 确认是否需要安全标记（SecurityLabelMixin）
4. 确认是否涉及敏感数据加密（AESCipher）

## 执行步骤

### Step 1: 创建模块目录结构

```
modules/{module_name}/
├── __init__.py       # 空文件
├── models.py         # SQLAlchemy 数据模型
├── schemas.py        # Pydantic 请求/响应模式
└── api.py            # FastAPI 路由（核心）
```

### Step 2: 编写 models.py

```python
from sqlalchemy import Column, Integer, String, DateTime, Float
from datetime import datetime
from core.database import Base
from core.security_label import SecurityLabelMixin  # 按需继承

class {ModelName}(Base, SecurityLabelMixin):  # SecurityLabelMixin 可选
    __tablename__ = "{table_name}"
    
    id = Column(Integer, primary_key=True, index=True)
    # ... 业务字段 ...
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Step 3: 编写 schemas.py

```python
from pydantic import BaseModel
from typing import Optional

class {ModelName}Create(BaseModel):
    # 创建时的必填字段
    pass

class {ModelName}Update(BaseModel):
    # 更新时的可选字段
    pass
```

### Step 4: 编写 api.py（关键）

**必须遵循的安全约束：**

```python
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.database import get_db
from core.auth import RequirePermission, get_current_user
from core.audit import create_audit_log
from core.security_label import RequireSecurityClearance, SecurityLevel
from models.system import User

router = APIRouter(tags=["{模块中文名}"])

# 查询：挂载读权限
@router.get("/", dependencies=[RequirePermission("{module}:view")])
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select({Model}).order_by({Model}.id.desc()))
    items = result.scalars().all()
    return [_to_dict(item) for item in items]

# 创建：挂载写权限 + 审计日志
@router.post("/", dependencies=[RequirePermission("{module}:manage")])
async def create_item(
    request: Request, body: {Schema},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_item = {Model}(**body.dict())
    db.add(new_item)
    await db.commit()
    await db.refresh(new_item)

    # 必须：审计日志
    await create_audit_log(
        db=db, request=request,
        action="CREATE_{MODULE_UPPER}",
        status="SUCCESS",
        details=body.dict(),
        current_user_id=current_user.username
    )
    return {"message": "创建成功", "id": new_item.id}
```

### Step 5: 注册路由

在 `main.py` 中添加：
```python
from modules.{module_name}.api import router as {module}_router
app.include_router({module}_router, prefix="/api/v1/{module_path}")
```

### Step 6: 注册权限节点

通过管理后台或 API 为目标角色添加新权限：
- `{module}:view` — 查看
- `{module}:manage` — 增删改
- `{module}:export` — 导出（如需要）

## 检查清单

完成后确认：
- [ ] 所有写入接口都挂了 `RequirePermission`
- [ ] 所有写入接口都调用了 `await create_audit_log(...)`
- [ ] 敏感字段使用了 `AESCipher` 加密存储
- [ ] 路由已在 `main.py` 中注册
- [ ] 权限节点已定义并分配给相应角色
