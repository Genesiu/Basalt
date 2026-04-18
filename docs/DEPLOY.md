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

**生产环境**须额外配置 CORS：
```bash
# 编辑 .env，添加：
CORS_ORIGINS=https://app.example.com,https://admin.example.com
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

### 2.5 定时备份

```bash
# 添加 crontab
crontab -e

# 每天 2:00 执行备份
0 2 * * * /opt/basalt/backup.sh >> /var/log/basalt-backup.log 2>&1
```

## 三、安全加固清单

部署后逐项确认：

- [ ] `.env` 文件权限为 `600`
- [ ] `CORS_ORIGINS` 已配置为受信域名
- [ ] Nginx TLS 已启用
- [ ] IP 白名单已添加管理网段
- [ ] 默认管理员密码已在首次登录时修改
- [ ] crontab 备份已配置
- [ ] 防火墙仅开放 80/443 端口

## 四、前端部署

```bash
cd /opt/basalt-frontend
npm install
npm run build
# 产物在 dist/ 目录，由 Nginx 托管
```
