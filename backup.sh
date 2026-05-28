#!/bin/bash
# ============================================================
# ⚠️ DEPRECATED — 此脚本已被内置 APScheduler 调度器取代
# 新备份系统支持 SQLite/MySQL/PostgreSQL，通过 WebUI 或 API 管理。
# 仅在无法启动 Python 后端时作为应急手段使用。
# ============================================================
# Basalt Framework 等保三级数据备份脚本（8.1.4.9a）
# 建议通过 crontab 定时执行：
#   0 2 * * * /path/to/safem/backup.sh >> /var/log/basalt_backup.log 2>&1
# ============================================================

set -euo pipefail

# 配置区
DB_FILE="${SAFEM_DB_PATH:-./basalt.db}"
BACKUP_DIR="${SAFEM_BACKUP_DIR:-./backups}"
KEEP_DAYS="${SAFEM_BACKUP_KEEP_DAYS:-30}"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/basalt_backup_${TIMESTAMP}.sql"
BACKUP_FILE_GZ="${BACKUP_FILE}.gz"

echo "[$(date)] 开始备份 Basalt 数据库..."

# 检查数据库文件存在
if [ ! -f "$DB_FILE" ]; then
    echo "[ERROR] 数据库文件不存在: $DB_FILE"
    exit 1
fi

# 使用 sqlite3 .dump 导出完整 SQL（包含结构+数据）
sqlite3 "$DB_FILE" ".dump" > "$BACKUP_FILE"

# 压缩备份
gzip "$BACKUP_FILE"

# 计算校验和（完整性验证）
CHECKSUM=$(shasum -a 256 "$BACKUP_FILE_GZ" | awk '{print $1}')
echo "$CHECKSUM  $BACKUP_FILE_GZ" > "${BACKUP_FILE_GZ}.sha256"

echo "[$(date)] 备份完成: $BACKUP_FILE_GZ"
echo "[$(date)] SHA-256: $CHECKSUM"

# 清理过期备份
DELETED_COUNT=$(find "$BACKUP_DIR" -name "basalt_backup_*.sql.gz" -mtime +"$KEEP_DAYS" -delete -print | wc -l)
find "$BACKUP_DIR" -name "basalt_backup_*.sql.gz.sha256" -mtime +"$KEEP_DAYS" -delete 2>/dev/null || true

echo "[$(date)] 已清理 ${DELETED_COUNT} 个超过 ${KEEP_DAYS} 天的过期备份。"
echo "[$(date)] 当前备份目录文件数: $(ls -1 "$BACKUP_DIR"/basalt_backup_*.sql.gz 2>/dev/null | wc -l)"
echo "---"
