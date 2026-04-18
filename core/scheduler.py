"""
内置定时任务调度器（替代系统 crontab）

使用 APScheduler 在进程内运行，不依赖操作系统 cron 服务。
默认调度：
  - 数据库备份：每天凌晨 2:00
"""

import os
import gzip
import hashlib
import shutil
import logging
import subprocess
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from core.database import is_sqlite, DATABASE_URL

logger = logging.getLogger("basalt.scheduler")

# 备份配置（可通过 .env 覆盖）
BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups"))
BACKUP_KEEP_DAYS = int(os.environ.get("BACKUP_KEEP_DAYS", "30"))
BACKUP_CRON_HOUR = int(os.environ.get("BACKUP_CRON_HOUR", "2"))
BACKUP_CRON_MINUTE = int(os.environ.get("BACKUP_CRON_MINUTE", "0"))

_scheduler = None


def _run_backup():
    """执行数据库备份（支持 SQLite / PostgreSQL / MySQL）"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        if is_sqlite():
            # SQLite: 直接复制 db 文件
            db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
            if db_path.startswith("./"):
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", db_path[2:])

            if not os.path.exists(db_path):
                logger.warning(f"[备份] 数据库文件不存在: {db_path}")
                return

            dump_file = os.path.join(BACKUP_DIR, f"basalt_backup_{ts}.sql")
            gz_file = dump_file + ".gz"

            # 使用 sqlite3 CLI dump（如可用），否则直接复制
            try:
                result = subprocess.run(
                    ["sqlite3", db_path, ".dump"],
                    capture_output=True, text=True, timeout=60
                )
                with open(dump_file, "w") as f:
                    f.write(result.stdout)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                # sqlite3 CLI 不可用时，直接复制数据库文件
                shutil.copy2(db_path, dump_file.replace(".sql", ".db"))
                dump_file = dump_file.replace(".sql", ".db")
                gz_file = dump_file + ".gz"

        elif "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
            # PostgreSQL: pg_dump
            dump_file = os.path.join(BACKUP_DIR, f"basalt_backup_{ts}.sql")
            gz_file = dump_file + ".gz"
            # 从 URL 解析连接参数
            # postgresql+asyncpg://user:pass@host:5432/dbname
            try:
                from urllib.parse import urlparse
                parsed = urlparse(DATABASE_URL.replace("+asyncpg", ""))
                env = os.environ.copy()
                env["PGPASSWORD"] = parsed.password or ""
                subprocess.run([
                    "pg_dump",
                    "-h", parsed.hostname or "localhost",
                    "-p", str(parsed.port or 5432),
                    "-U", parsed.username or "postgres",
                    "-f", dump_file,
                    parsed.path.lstrip("/")
                ], env=env, timeout=300, check=True)
            except Exception as e:
                logger.error(f"[备份] PostgreSQL dump 失败: {e}")
                return

        elif "mysql" in DATABASE_URL:
            # MySQL: mysqldump
            dump_file = os.path.join(BACKUP_DIR, f"basalt_backup_{ts}.sql")
            gz_file = dump_file + ".gz"
            try:
                from urllib.parse import urlparse
                parsed = urlparse(DATABASE_URL.replace("+aiomysql", ""))
                subprocess.run([
                    "mysqldump",
                    "-h", parsed.hostname or "localhost",
                    "-P", str(parsed.port or 3306),
                    "-u", parsed.username or "root",
                    f"-p{parsed.password or ''}",
                    parsed.path.lstrip("/")
                ], stdout=open(dump_file, "w"), timeout=300, check=True)
            except Exception as e:
                logger.error(f"[备份] MySQL dump 失败: {e}")
                return
        else:
            logger.warning(f"[备份] 不支持的数据库类型，跳过备份")
            return

        # 压缩
        with open(dump_file, "rb") as f_in:
            with gzip.open(gz_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(dump_file)

        # SHA-256 校验码
        sha256 = hashlib.sha256()
        with open(gz_file, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        checksum_file = gz_file + ".sha256"
        with open(checksum_file, "w") as f:
            f.write(f"{sha256.hexdigest()}  {os.path.basename(gz_file)}\n")

        file_size = os.path.getsize(gz_file) / 1024
        logger.info(f"[备份完成] {gz_file} ({file_size:.1f} KB) SHA256: {sha256.hexdigest()[:16]}...")

        # 清理过期备份
        _cleanup_old_backups()

    except Exception as e:
        logger.error(f"[备份失败] {e}")


def _cleanup_old_backups():
    """清理超过保留天数的旧备份"""
    import time
    cutoff = time.time() - (BACKUP_KEEP_DAYS * 86400)
    for fname in os.listdir(BACKUP_DIR):
        fpath = os.path.join(BACKUP_DIR, fname)
        if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
            os.remove(fpath)
            logger.info(f"[备份清理] 已删除过期备份: {fname}")


def start_scheduler():
    """启动内置调度器"""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_backup,
        trigger="cron",
        hour=BACKUP_CRON_HOUR,
        minute=BACKUP_CRON_MINUTE,
        id="basalt_auto_backup",
        name="Basalt 自动数据库备份",
        misfire_grace_time=3600
    )
    _scheduler.start()
    logger.info(
        f"[调度器] 内置备份调度已启动 — 每日 {BACKUP_CRON_HOUR:02d}:{BACKUP_CRON_MINUTE:02d} 执行，"
        f"保留 {BACKUP_KEEP_DAYS} 天"
    )


def trigger_backup_now():
    """手动触发一次备份（供 API 调用）"""
    _run_backup()
