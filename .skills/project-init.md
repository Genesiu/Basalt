---
trigger: project_init
description: Basalt 项目初始化与环境搭建指引
globs: ["main.py", "requirements.txt", ".env"]
alwaysApply: false
---

# Skill: Basalt 项目初始化

当用户首次克隆项目或遇到启动问题时，按以下指引操作。

## 零配置启动流程

Basalt 采用「克隆即用」设计。以下两个文件 **不存在于 Git 仓库中**，但会在首次启动时 **自动生成**：

| 文件 | 作用 | 生成时机 | 生成逻辑 |
|------|------|---------|---------|
| `.env` | AES 加密密钥 + JWT 签名密钥 | `main.py` 中的 `_load_or_create_env()` | 如果文件不存在，用 `os.urandom(32)` 生成 256-bit 随机密钥，Base64 编码后写入文件，权限设为 600 |
| `basalt.db` | SQLite 数据库 | `main.py` 中的 `@app.on_event("startup")` | SQLAlchemy `create_all()` 自动建表 + 播种角色/用户/配置 |

**无需手动创建这两个文件。**

## 标准初始化步骤

```bash
# 1. 克隆
git clone https://github.com/Genesiu/Basalt.git && cd Basalt

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动（首次会自动生成 .env + basalt.db）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 首次启动后的自动初始化内容

### .env 文件（自动生成）
```
# Basalt 自动生成的密钥文件，请勿删除或手动修改（除非你知道后果）
# 生产环境建议使用 KMS 或 Vault 管理密钥
AES_ENCRYPTION_KEY_B64=<随机生成的 Base64 密钥>
JWT_SECRET_KEY=<随机生成的 Base64 密钥>
# 可选配置：
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/basalt
# CORS_ORIGINS=https://your-domain.com
# BACKUP_ENABLED=true
# BACKUP_CRON_HOUR=2
# BACKUP_KEEP_DAYS=30
```

### 数据库（自动生成）
自动创建的表：
- `roles` — 角色表（预置 sysadmin/auditadmin/ordinary）
- `users` — 用户表（预置两个管理员）
- `audit_logs` — 审计日志（附带 UPDATE/DELETE 触发器保护）
- `login_attempts` — 登录尝试记录
- `system_configs` — 等保基线配置
- `ip_whitelist` — IP 白名单
- `password_history` — 密码历史记录

### 默认账号
| 用户名 | 密码 | 首次登录行为 |
|--------|------|------------|
| sysadmin | Admin!@#123 | 返回 403 + "首次登录需改密" |
| auditadmin | Admin!@#123 | 同上 |

## 常见问题排查

### Q: 启动报 "No module named 'xxx'"
```bash
pip install -r requirements.txt  # 确认安装了所有依赖
```

### Q: 登录返回 "首次登录或密码已被重置"
这是**正常的等保合规行为**。调用改密接口：
```bash
curl -X POST http://localhost:8000/api/v1/auth/reset-expired-password \
  -H "Content-Type: application/json" \
  -d '{"username":"sysadmin","old_password":"Admin!@#123","new_password":"你的新密码"}'
```
新密码要求：≥8位，含大小写+数字+特殊字符（支持 `!@#$%^&*()_+-=~.,?`），不得包含用户名。

### Q: 想重置整个环境
```bash
rm -f basalt.db .env    # 删除数据库和密钥
uvicorn main:app ...     # 重新启动，自动重建
```

### Q: 生产环境需要额外配置什么
编辑 `.env` 文件（首次启动后自动生成），添加：
```
CORS_ORIGINS=https://your-domain.com
```

### Q: 如何管理备份？
- **WebUI**：登录后台 → 菜单「备份管理」→ 开关/时间/路径/保留天数
- **API**：`GET /api/v1/compliance/backup/status`
- 内置 APScheduler 调度器，无需配置系统 crontab
