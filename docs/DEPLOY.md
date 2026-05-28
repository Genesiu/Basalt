# Basalt 生产环境部署指南

## 一、系统要求

| 组件 | 最低版本 |
|------|---------|
| Python | 3.10+ |
| Nginx | 1.24+ |
| OS | Ubuntu 22.04 / CentOS 8+ |

## 二、快速部署

### 2.1 代码部署

```bash
# 1. 克隆代码
git clone https://github.com/genesiu/basalt.git /opt/basalt
cd /opt/basalt

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 首次启动（自动生成 .env 和数据库）
uvicorn main:app --host 127.0.0.1 --port 8000
# ⚠️ 首次启动时，初始管理员密码会随机生成并打印在启动日志中：
#    [SECURITY NOTICE] 初始管理员密码: xxxxxxxx — 请立即登录修改！
# 请务必记录该密码，登录后系统会强制要求修改。
# 启动后按 Ctrl+C 停止
```

### 2.2 密钥管理

首次启动自动生成 `.env` 文件：
```
AES_ENCRYPTION_KEY_B64=xxxxx
JWT_SECRET_KEY=xxxxx
```

**生产环境**须额外配置：
```bash
# 编辑 .env，添加：
CORS_ORIGINS=https://app.example.com,https://admin.example.com

# 反向代理信任配置（使用 Nginx 时必须配置，否则 IP 白名单和防爆破以代理 IP 计算）
# 填写 Nginx 所在服务器的 IP 网段，多个用逗号分隔
TRUSTED_PROXY_CIDRS=127.0.0.1/32

# 如需切换数据库（默认 SQLite）：
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/basalt
# DATABASE_URL=mysql+aiomysql://user:pass@localhost:3306/basalt

# 备份配置（可选，也可在 WebUI「备份管理」中动态修改）：
BACKUP_ENABLED=true
BACKUP_CRON_HOUR=2
BACKUP_KEEP_DAYS=30
```

### 2.3 Systemd 服务

```ini
# /etc/systemd/system/basalt.service
[Unit]
Description=Basalt Security Framework
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/basalt
ExecStart=/opt/basalt/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1 --loop uvloop
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now basalt
```

### 2.4 Nginx 反向代理（含 TLS）

```nginx
server {
    listen 443 ssl http2;
    server_name basalt.example.com;

    ssl_certificate     /etc/ssl/certs/basalt.pem;
    ssl_certificate_key /etc/ssl/private/basalt.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # 安全头
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header Strict-Transport-Security "max-age=31536000" always;

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 前端静态文件
    location / {
        root /opt/basalt-frontend/dist;
        try_files $uri $uri/ /index.html;
    }
}

server {
    listen 80;
    server_name basalt.example.com;
    return 301 https://$server_name$request_uri;
}
```

### 2.5 备份与自动清理

Basalt 内置 APScheduler 调度器，**无需配置系统 crontab**。

- **备份**：每天 2:00 自动 Gzip 压缩 + SHA-256 校验
- **LoginAttempt 清理**：每 6 小时自动清理过期记录（默认 30 天，`LOGIN_ATTEMPT_KEEP_DAYS` 可调）
- **MySQL 备份**：使用 `mysqldump --single-transaction` 保证 InnoDB 一致性

### 2.6 MySQL 部署

```bash
# 1. 创建数据库
mysql -u root -p -e "
CREATE DATABASE basalt CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'basalt'@'%' IDENTIFIED BY '强密码';
GRANT ALL PRIVILEGES ON basalt.* TO 'basalt'@'%';
FLUSH PRIVILEGES;"

# 2. 修改 .env
# DATABASE_URL=mysql+aiomysql://basalt:强密码@localhost:3306/basalt

# 3. 启动 — 以下全部自动完成：
#    ✅ 建表（ORM 自动迁移）
#    ✅ 审计防删改触发器（SIGNAL SQLSTATE '45000'）
#    ✅ 定时备份 + LoginAttempt 清理
```

## 三、安全加固清单

- [ ] `.env` 权限 `600`，`PRODUCTION=true`
- [ ] `CORS_ORIGINS` 为受信域名（生产模式下 `*` 会阻止启动）
- [ ] `TRUSTED_PROXY_CIDRS` 配置为 Nginx 网段
- [ ] 从启动日志获取随机初始密码并修改
- [ ] 管理员已绑定 TOTP（不可自行取消）
- [ ] IP 白名单收紧（默认 `0.0.0.0/0`）
- [ ] 防火墙仅开放 80/443

## 四、前端部署

```bash
cd /opt/basalt-frontend && npm install && npm run build
# dist/ 目录由 Nginx 托管
```

## 五、环境变量参考

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接串 | `sqlite+aiosqlite:///./basalt.db` |
| `CORS_ORIGINS` | CORS 域名白名单 | `*`（生产禁止） |
| `TRUSTED_PROXY_CIDRS` | 可信代理网段 | 空 |
| `PRODUCTION` | 生产模式 | `false` |
| `LOGIN_ATTEMPT_KEEP_DAYS` | 登录记录保留天数 | `30` |
| `BACKUP_CRON_HOUR` | 备份执行小时 | `2` |
| `BACKUP_KEEP_DAYS` | 备份保留天数 | `30` |
