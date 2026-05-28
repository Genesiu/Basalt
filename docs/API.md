# Basalt API 接口文档

> **基础地址**：`http://localhost:8000/api/v1`  
> **认证方式**：Bearer Token（JWT）  
> **内容类型**：`application/json`（除登录接口外）

---

## 一、身份鉴别 (`/auth`)

### POST `/auth/login`

登录获取 JWT Token。

**Content-Type**: `application/x-www-form-urlencoded`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | ✅ | 用户名 |
| password | string | ✅ | 密码 |
| scope | string | ❌ | TOTP 验证码（已绑定时必填） |

**响应示例**：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "totp_required_warning": "您的管理员角色要求绑定双因子认证..."  // 仅管理员未绑定时返回
}
```

**错误码**：
| 状态码 | 场景 | Headers |
|--------|------|---------|
| 401 | 密码错误 / TOTP 错误 | `X-TOTP-Required: true`（需 TOTP 时） |
| 403 | 首次登录需改密 / 密码过期 | `X-Password-Expired: true` |
| 403 | IP 或账号锁定 | — |

---

### POST `/auth/reset-expired-password`

首次登录或密码过期时的改密接口（无需 Token）。

```json
{
  "username": "sysadmin",
  "old_password": "<启动日志中打印的随机初始密码>",
  "new_password": "NewSecure@2026"
}
```

**密码策略**：
- 至少 8 位，含大小写字母 + 数字 + 特殊字符（支持 `!@#$%^&*()_+-=~.,?`）
- 不得与用户名相同或包含用户名
- 不得与近 5 次使用过的密码相同

---

### PUT `/auth/change-password` 🔒

已登录用户修改密码。

```json
{
  "old_password": "当前密码",
  "new_password": "新密码"
}
```

---

### POST `/auth/totp/setup` 🔒

第一步：为当前用户生成 TOTP 密钥和 QR 码。**此时不写入数据库**。

**响应**：
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "provisioning_uri": "otpauth://totp/Basalt-Framework:sysadmin?secret=...",
  "message": "请使用 Authenticator 应用扫描二维码，然后输入 6 位验证码完成绑定。"
}
```

### POST `/auth/totp/verify` 🔒

第二步：验证用户输入的 6 位 TOTP 码。服务端从内存缓存取出 setup 阶段生成的 secret 进行验证，通过后写入数据库完成绑定。

```json
{
  "code": "123456"
}
```

> ⚠️ **安全变更**：`secret` 字段已移除，不再由客户端传入。服务端在 `/totp/setup` 时临时缓存 secret（5 分钟有效），verify 时自动关联。

**响应**：
```json
{
  "message": "双因子认证绑定成功！下次登录将需要输入动态验证码。"
}
```

### DELETE `/auth/totp/cancel` 🔒

取消已绑定的 TOTP（清除数据库中的 secret）。

> ⚠️ **权限限制**：管理员角色（`sysadmin`、`auditadmin`）不可自行取消 TOTP 绑定，需由安全管理员重置。

---

## 二、用户管理 (`/users`)

### GET `/users/me` 🔒

获取当前用户资料 + 权限树。

```json
{
  "id": 1,
  "username": "sysadmin",
  "role_code": "sysadmin",
  "role_name": "系统管理员",
  "permissions": ["policy:manage", "user:manage", "role:manage", "audit:view", "audit:export"],
  "totp_force_required": true,
  "last_login_at": "2026-04-18 10:00:00"
}
```

### PUT `/users/me` 🔒

修改个人密码（需原密码 + 新密码，前端已增加二次确认）。

### GET `/users/` 🔒🛡️

列出所有用户。需要 `user:manage` 权限 + IP 白名单。

### POST `/users/` 🔒🛡️

创建新用户（首次登录需改密）。

```json
{
  "username": "newuser",
  "password": "Initial@Pass123",
  "role_code": "ordinary"
}
```

### PUT `/users/{user_id}` 🔒🛡️

修改用户角色或状态。

### DELETE `/users/{user_id}` 🔒🛡️

停用用户（自动擦除 TOTP 密钥和加密数据）。

---

## 三、角色与权限 (`/roles`)

### GET `/roles/` 🔒🛡️

获取所有角色（含安全等级）。

### GET `/roles/security-levels` 🔒🛡️

获取安全等级选项（公开/内部/敏感/核心）。

### POST `/roles/` 🔒🛡️

创建新角色。

### PUT `/roles/{role_id}` 🔒🛡️

修改角色权限和安全等级。

---

## 四、安全审计 (`/audit`)

### GET `/audit/` 🔒🛡️

查询审计日志（需 `audit:view` 权限）。

### GET `/audit/{log_id}` 🔒🛡️

查看单条审计详情。

### GET `/audit/export/csv` 🔒🛡️

导出审计日志为 CSV 文件（需 `audit:export` 权限）。

---

## 五、安全策略 (`/config`)

### GET `/config/` 🔒🛡️

获取等保基线配置。

### PUT `/config/` 🔒🛡️

修改等保基线配置。

```json
{
  "LOGIN_MAX_FAILURES": "5",
  "LOGIN_LOCKOUT_MINUTES": "30",
  "PWD_MAX_AGE_DAYS": "90",
  "SESSION_TIMEOUT_MINS": "15"
}
```

### GET `/config/whitelist` 🔒🛡️

获取 IP 白名单列表。

### POST `/config/whitelist` 🔒🛡️

添加 IP 白名单规则。

### DELETE `/config/whitelist/{item_id}` 🔒🛡️

删除 IP 白名单规则。

---

## 六、备份管理 (`/compliance`)

### GET `/compliance/backup/status` 🔒🛡️

获取备份调度状态及最近备份列表。

```json
{
  "enabled": true,
  "cron_hour": 2,
  "cron_minute": 0,
  "backup_dir": "/opt/basalt/backups",
  "keep_days": 30,
  "recent_backups": [
    {"filename": "basalt_20260418_020000.db.gz", "size_kb": 128, "time": "2026-04-18 02:00:00"}
  ],
  "total_backups": 15
}
```

### PUT `/compliance/backup/config` 🔒🛡️

动态修改备份策略（开关、时间、路径、保留天数）。

```json
{
  "enabled": true,
  "cron_hour": 3,
  "cron_minute": 0,
  "backup_dir": "/opt/basalt/backups",
  "keep_days": 15
}
```

### POST `/compliance/backup/trigger` 🔒🛡️

手动触发一次即时备份。返回备份文件信息和 SHA-256 校验码。

---

## 图标说明

| 图标 | 含义 |
|------|------|
| 🔒 | 需要 Bearer Token |
| 🛡️ | 需要特定权限 + IP 白名单 |
