---
trigger: security_review
description: 对 Basalt 框架中的业务代码进行等保合规性审查
globs: ["modules/**/*.py", "**/*_router.py"]
alwaysApply: false
---

# Skill: 安全合规性审查

当用户要求审查代码安全性或准备等保测评时，按以下清单逐项检查。

## 审查维度

### 1. 接口安全

对每个路由文件，检查：

```
□ 所有 POST/PUT/DELETE 接口是否挂载了 RequirePermission
□ 管理接口是否同时挂载了 Depends(ip_whitelist_checker)
□ 是否存在未鉴权的裸接口（只有 GET /health 允许裸露）
```

### 2. 审计完整性

```
□ 所有写操作是否调用了 await create_audit_log(...)
□ create_audit_log 是否传入了 db 参数（不是 background_tasks）
□ action 名称是否清晰可追溯（大写+下划线命名）
□ details 是否包含了足够的上下文（谁做了什么）
```

### 3. 数据安全

```
□ 手机号、身份证号、银行卡号等 PII 是否使用 AESCipher 加密后存储
□ 密码是否使用 Hasher.get_password_hash 哈希存储
□ 查询结果中的敏感字段是否做了脱敏处理
□ 日志中是否避免了打印明文密码或 Token
```

### 4. 安全标记

```
□ 业务 Model 是否按需继承了 SecurityLabelMixin
□ 包含敏感数据的路由是否挂载了 RequireSecurityClearance
□ 安全等级命名是否使用企业术语（公开/内部/敏感/核心），而非国家保密术语
```

### 5. 输入校验

```
□ 所有用户输入是否通过 Pydantic BaseModel 校验
□ 文件上传（如有）是否限制了类型和大小
□ SQL 操作是否全部通过 ORM（禁止拼接 raw SQL）
```

### 6. 密码策略

```
□ 新建用户时 password_updated_at 是否设为 None（强制首登改密）
□ 修改密码时是否校验了 validate_complexity(password, username=username)
□ 修改密码时是否检查了密码历史 _check_password_reuse
□ 修改密码后是否更新了 password_updated_at
```

## 输出格式

审查结果以表格形式输出：

```markdown
| 文件 | 问题 | 严重度 | 建议 |
|------|------|--------|------|
| modules/xxx/api.py | POST `/items` 未挂 RequirePermission | 🔴 严重 | 添加 dependencies=[RequirePermission("item:manage")] |
```
