# Basalt Framework — 等保三级测评指引

> **标准**：GB/T 22239-2019《信息安全技术 网络安全等级保护基本要求》第三级  
> **系统**：Basalt Framework v2.1.0 | by Genesiu  
> **说明**：本文档供等保测评师现场核查使用，每项条款均标注了可直接访问的验证路径。

---

## 一、身份鉴别（8.1.4.1）

### a) 用户标识唯一性
- **验证路径**：`GET /api/v1/users/` → 查看用户列表，`username` 字段均为唯一值
- **代码位置**：`models/system.py` → `User.username` 有 `unique=True` 约束

### b) 鉴别信息复杂度
- **验证路径**：`GET /api/v1/config/` → 查看 `PWD_COMPLEXITY_ENFORCE` 配置为 `true`
- **现场演示**：尝试创建弱密码用户 → 系统拒绝并返回复杂度要求
- **代码位置**：`core/policy.py` → `PasswordPolicyEngine.validate_complexity()`

### c) 鉴别信息定期更换
- **验证路径**：`GET /api/v1/config/` → 查看 `PWD_MAX_AGE_DAYS` 配置（默认 90 天）
- **代码位置**：`core/auth_router.py` → 登录时检查 `password_updated_at` 是否超期

### d) 登录失败限制
- **验证路径**：`GET /api/v1/config/` → 查看 `LOGIN_MAX_FAILURES`（默认 5 次）和 `LOGIN_LOCKOUT_MINUTES`（默认 30 分钟）
- **现场演示**：连续输错密码 → 账号被锁定
- **代码位置**：`core/auth_router.py` → `handle_login()` 中的失败计数逻辑

### e) 默认账户口令修改
- **验证路径**：使用默认密码登录 → 返回 403 + `X-Password-Expired: true`，强制改密
- **现场演示**：新建用户 → 首次登录必须修改密码
- **代码位置**：`main.py` → 种子用户 `password_updated_at=None`

### f) 会话超时
- **验证路径**：`GET /api/v1/config/` → 查看 `SESSION_TIMEOUT_MINS`（默认 15 分钟）
- **前端验证**：登录后静置 15 分钟 → 自动跳转登录页
- **代码位置**：前端 `AdminDashboard.vue` → 60 秒心跳轮询

### h) 多因素认证（MFA）
- **验证路径**：管理员登录后 → 前端显示 TOTP 强制绑定告警横幅
- **现场演示**：`POST /api/v1/auth/totp/setup` → 返回 QR 码 URI
- **代码位置**：`core/mfa_totp.py` + `core/auth_router.py`

### i) 密码不含用户名
- **现场演示**：创建用户 `testuser`，设置密码 `Testuser@123` → 系统拒绝
- **代码位置**：`core/policy.py` → `validate_complexity(password, username=username)`

### j) 密码历史不重复
- **验证路径**：修改密码后尝试改回旧密码 → 系统拒绝
- **代码位置**：`core/policy.py` → `_check_password_reuse()`，检查近 5 次历史

---

## 二、访问控制（8.1.4.2）

### a) 最小权限
- **验证路径**：`GET /api/v1/roles/` → 查看每个角色的权限节点列表
- **现场演示**：普通用户访问 `/api/v1/users/` → 返回 403
- **代码位置**：`core/auth.py` → `RequirePermission` 装饰器

### b) 三员分立
- **验证路径**：`GET /api/v1/roles/` → 确认存在 sysadmin / auditadmin / ordinary 三个角色
- **权限矩阵**：
  - sysadmin：`policy:manage`, `user:manage`, `role:manage`
  - auditadmin：`audit:view`, `audit:export`
  - ordinary：无预置权限

### g/h) 安全标记 + 基于标记的访问控制
- **验证路径**：`GET /api/v1/roles/security-levels` → 查看安全等级定义（公开/内部/敏感/核心）
- **验证路径**：`GET /api/v1/roles/` → 每个角色包含 `max_clearance` 和 `max_clearance_label` 字段
- **代码位置**：`core/security_label.py` → `RequireSecurityClearance` 装饰器

---

## 三、安全审计（8.1.4.3）

### a-b) 审计记录覆盖与完整性
- **验证路径**：`GET /api/v1/audit/` → 查看审计日志列表
- **字段验证**：每条记录包含 timestamp / user_id / action / status / ip_address / details

### c) 审计日志防删改
- **验证方式**：直接在数据库中尝试 `DELETE FROM audit_logs` → 触发器拦截并报错
- **代码位置**：`main.py` → `audit_logs_no_update` / `audit_logs_no_delete` SQLite 触发器

### d) 审计进程保护
- **验证方式**：查看代码中 `create_audit_log()` 为同步 `await` 调用，非 `BackgroundTasks`
- **代码位置**：`core/audit.py` → 使用独立 `AsyncSession` 同步 commit

### e) 审计查询
- **验证路径**：以 auditadmin 身份登录 → `GET /api/v1/audit/` 可查询
- **验证路径**：以 sysadmin 身份登录 → `GET /api/v1/audit/` 返回 403（无 `audit:view` 权限）

### f) 审计导出
- **验证路径**：`GET /api/v1/audit/export/csv` → 下载 CSV 文件（需 `audit:export` 权限）

---

## 四、入侵防范（8.1.4.4）

### c) 管理终端限制
- **验证路径**：`GET /api/v1/config/whitelist` → 查看 IP 白名单
- **现场演示**：从非白名单 IP 访问管理接口 → 返回 403
- **代码位置**：`core/ip_filter.py` → `ip_whitelist_checker`

---

## 五、数据安全（8.1.4.7-10）

### 存储保密性
- **验证方式**：查看数据库中 `encrypted_phone` 等字段为密文存储
- **代码位置**：`core/crypto.py` → `AESCipher`（AES-256-GCM 认证加密）

### 密钥管理
- **验证方式**：查看 `.env` 文件权限为 `600`（`ls -la .env`）
- **验证方式**：`.env` 在 `.gitignore` 中，不会提交到代码仓库

### 数据备份
- **验证路径**：管理后台「系统配置」→ 备份管理面板
- **验证方式**：`ls -la backups/` → 查看备份文件 + `.sha256` 校验码文件
- **代码位置**：`core/scheduler.py` → APScheduler 定时备份

### 敏感数据释放
- **现场演示**：停用用户 → 查看数据库中 `totp_secret` 和 `encrypted_phone` 已被清空
- **代码位置**：`core/user_router.py` → 停用时 `totp_secret=None, encrypted_phone=None`

---

## 六、安全管理中心（8.1.5）

### 三员职能
- **系统管理员**：用户管理 + 策略配置 + 备份 → `GET /api/v1/users/` + `GET /api/v1/config/`
- **审计管理员**：审计查询 + 导出 → `GET /api/v1/audit/` + `GET /api/v1/audit/export/csv`
- **安全管理员**：安全标记 + 策略 → `GET /api/v1/roles/security-levels`

---

## 快速验证清单（测评师用）

| # | 验证项 | 操作 | 预期结果 |
|---|--------|------|---------|
| 1 | 弱密码拦截 | 创建用户密码 `123456` | 返回"密码复杂度不足" |
| 2 | 首登改密 | 默认密码登录 | 返回 403 + 强制改密 |
| 3 | 密码历史 | 改密用旧密码 | 返回"与近5次相同" |
| 4 | 账号锁定 | 连错 5 次密码 | 账号锁定 30 分钟 |
| 5 | 权限隔离 | 普通用户访管理接口 | 返回 403 |
| 6 | 审计防删 | `DELETE FROM audit_logs` | 触发器拦截报错 |
| 7 | IP白名单 | 非白名单 IP 访管理接口 | 返回 403 |
| 8 | TOTP | 管理员登录看告警 | TOTP 绑定提醒 |
| 9 | 数据加密 | 查看 DB 中 phone 字段 | 密文存储 |
| 10 | 数据擦除 | 停用用户后查 DB | totp_secret=NULL |

---

> **合规声明**：本框架内置的安全标记等级（公开/内部/敏感/核心）为企业数据分类术语，  
> 与《中华人民共和国保守国家秘密法》所定义的国家秘密等级无关。
