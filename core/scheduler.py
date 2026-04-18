"""
内置定时任务调度器（替代系统 crontab）

使用 APScheduler 在进程内运行，不依赖操作系统 cron 服务。
支持通过 API 动态控制开启/关闭、调整时间和路径。
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

# 备份配置（可通过 .env 覆盖，也可通过 API 动态修改）
BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups"))
BACKUP_KEEP_DAYS = int(os.environ.get("BACKUP_KEEP_DAYS", "30"))
BACKUP_CRON_HOUR = int(os.environ.get("BACKUP_CRON_HOUR", "2"))
BACKUP_CRON_MINUTE = int(os.environ.get("BACKUP_CRON_MINUTE", "0"))
BACKUP_ENABLED = os.environ.get("BACKUP_ENABLED", "true").lower() == "true"

_scheduler: BackgroundScheduler = None
_config = {}


def _run_backup() -> dict:
    """执行数据库备份（支持 SQLite / PostgreSQL / MySQL）"""
    backup_dir = _config.get("backup_dir", BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        if is_sqlite():
            db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
            if db_path.startswith("./"):
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", db_path[2:])

            if not os.path.exists(db_path):
                logger.warning(f"[备份] 数据库文件不存在: {db_path}")
                return {"status": "failed", "error": f"数据库文件不存在: {db_path}"}

            dump_file = os.path.join(backup_dir, f"basalt_backup_{ts}.sql")
            gz_file = dump_file + ".gz"

            try:
                result = subprocess.run(
                    ["sqlite3", db_path, ".dump"],
                    capture_output=True, text=True, timeout=60
                )
                with open(dump_file, "w") as f:
                    f.write(result.stdout)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                shutil.copy2(db_path, dump_file.replace(".sql", ".db"))
                dump_file = dump_file.replace(".sql", ".db")
                gz_file = dump_file + ".gz"

        elif "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
            dump_file = os.path.join(backup_dir, f"basalt_backup_{ts}.sql")
            gz_file = dump_file + ".gz"
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
                return {"status": "failed", "error": str(e)}

        elif "mysql" in DATABASE_URL:
            dump_file = os.path.join(backup_dir, f"basalt_backup_{ts}.sql")
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
                return {"status": "failed", "error": str(e)}
        else:
            return {"status": "skipped", "error": "不支持的数据库类型"}

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
        logger.info(f"[备份完成] {gz_file} ({file_size:.1f} KB)")

        # 清理过期备份
        _cleanup_old_backups()

        return {
            "status": "success",
            "file": os.path.basename(gz_file),
            "size_kb": round(file_size, 1),
            "sha256": sha256.hexdigest()
        }

    except Exception as e:
        logger.error(f"[备份失败] {e}")
        return {"status": "failed", "error": str(e)}


def _cleanup_old_backups():
    """清理超过保留天数的旧备份"""
    import time
    backup_dir = _config.get("backup_dir", BACKUP_DIR)
    keep_days = _config.get("keep_days", BACKUP_KEEP_DAYS)
    cutoff = time.time() - (keep_days * 86400)
    if not os.path.exists(backup_dir):
        return
    for fname in os.listdir(backup_dir):
        fpath = os.path.join(backup_dir, fname)
        if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
            os.remove(fpath)
            logger.info(f"[备份清理] 已删除: {fname}")


def start_scheduler():
    """启动内置调度器"""
    global _scheduler, _config
    if _scheduler is not None:
        return

    _config = {
        "enabled": BACKUP_ENABLED,
        "cron_hour": BACKUP_CRON_HOUR,
        "cron_minute": BACKUP_CRON_MINUTE,
        "backup_dir": BACKUP_DIR,
        "keep_days": BACKUP_KEEP_DAYS,
    }

    _scheduler = BackgroundScheduler()

    if _config["enabled"]:
        _scheduler.add_job(
            _run_backup,
            trigger="cron",
            hour=_config["cron_hour"],
            minute=_config["cron_minute"],
            id="basalt_auto_backup",
            name="Basalt 自动数据库备份",
            misfire_grace_time=3600
        )
    
    _scheduler.start()
    status = "已启用" if _config["enabled"] else "已关闭"
    logger.info(
        f"[调度器] 备份调度{status} — "
        f"每日 {_config['cron_hour']:02d}:{_config['cron_minute']:02d}，"
        f"保留 {_config['keep_days']} 天，路径 {_config['backup_dir']}"
    )


def get_scheduler_status() -> dict:
    """获取调度器当前状态（供 API 调用）"""
    backup_dir = _config.get("backup_dir", BACKUP_DIR)
    
    # 统计已有备份
    backup_files = []
    if os.path.exists(backup_dir):
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith(".gz"):
                fpath = os.path.join(backup_dir, f)
                backup_files.append({
                    "filename": f,
                    "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                    "time": datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S")
                })
    
    return {
        "enabled": _config.get("enabled", BACKUP_ENABLED),
        "cron_hour": _config.get("cron_hour", BACKUP_CRON_HOUR),
        "cron_minute": _config.get("cron_minute", BACKUP_CRON_MINUTE),
        "backup_dir": backup_dir,
        "keep_days": _config.get("keep_days", BACKUP_KEEP_DAYS),
        "recent_backups": backup_files[:10],  # 最近 10 个
        "total_backups": len(backup_files)
    }


def update_scheduler_config(
    enabled: bool = None,
    cron_hour: int = None,
    cron_minute: int = None,
    backup_dir: str = None,
    keep_days: int = None
) -> dict:
    """动态更新调度配置（供 API 调用）"""
    global _config

    if enabled is not None:
        _config["enabled"] = enabled
    if cron_hour is not None:
        _config["cron_hour"] = cron_hour
    if cron_minute is not None:
        _config["cron_minute"] = cron_minute
    if backup_dir is not None:
        _config["backup_dir"] = backup_dir
    if keep_days is not None:
        _config["keep_days"] = keep_days

    # 重新调度
    if _scheduler:
        try:
            _scheduler.remove_job("basalt_auto_backup")
        except Exception:
            pass
        
        if _config["enabled"]:
            _scheduler.add_job(
                _run_backup,
                trigger="cron",
                hour=_config["cron_hour"],
                minute=_config["cron_minute"],
                id="basalt_auto_backup",
                name="Basalt 自动数据库备份",
                misfire_grace_time=3600
            )

    status = "已启用" if _config["enabled"] else "已关闭"
    logger.info(f"[调度器] 配置已更新：{status}，{_config['cron_hour']:02d}:{_config['cron_minute']:02d}")
    
    return {
        "message": f"备份调度{status}",
        "config": {
            "enabled": _config["enabled"],
            "cron_hour": _config["cron_hour"],
            "cron_minute": _config["cron_minute"],
            "backup_dir": _config["backup_dir"],
            "keep_days": _config["keep_days"],
        }
    }


def trigger_backup_now() -> dict:
    """手动触发一次备份（供 API 调用）"""
    return _run_backup()
