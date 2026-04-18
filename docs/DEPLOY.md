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
ExecStart=/opt/basalt/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
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

### 2.5 备份管理

Basalt 内置 APScheduler 调度器，**无需配置系统 crontab**。

- **WebUI 控制**：登录管理后台 → 菜单「备份管理」→ 开关/时间/路径/保留天数
- **API 控制**：`PUT /api/v1/compliance/backup/config`
- **手动触发**：`POST /api/v1/compliance/backup/trigger`
- **默认参数**：每天 2:00 自动备份，保留 30 天
- **备份内容**：Gzip 压缩 + SHA-256 完整性校验码

> ⚠️ PostgreSQL/MySQL 环境下，备份使用 `pg_dump` / `mysqldump`，请确保相应工具已安装。

## 三、安全加固清单

部署后逐项确认：

- [ ] `.env` 文件权限为 `600`
- [ ] `CORS_ORIGINS` 已配置为受信域名
- [ ] Nginx TLS 已启用
- [ ] IP 白名单已添加管理网段
- [ ] 默认管理员密码已在首次登录时修改
- [ ] 管理员已绑定 TOTP 双因子认证
- [ ] 备份已在「备份管理」面板中确认开启
- [ ] 防火墙仅开放 80/443 端口
- [ ] PostgreSQL/MySQL 环境下已手动部署审计防删改触发器

## 四、前端部署

```bash
cd /opt/basalt-frontend
npm install
npm run build
# 产物在 dist/ 目录，由 Nginx 托管
```
