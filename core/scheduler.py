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
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from core.database import is_sqlite, DATABASE_URL, AsyncSessionLocal

logger = logging.getLogger("basalt.scheduler")

# Modified: [L-02] 使用绝对路径查找外部工具
_SQLITE3_PATH = shutil.which("sqlite3") or "sqlite3"
_PGDUMP_PATH = shutil.which("pg_dump") or "pg_dump"
_MYSQLDUMP_PATH = shutil.which("mysqldump") or "mysqldump"

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
                # Modified: [L-02] 使用绝对路径
                result = subprocess.run(
                    [_SQLITE3_PATH, db_path, ".dump"],
                    capture_output=True, text=True, timeout=60
                )
                with open(dump_file, "w") as f:
                    f.write(result.stdout)
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.warning(f"[备份] sqlite3 工具不可用，回退到文件拷贝: {e}")
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
                # Modified: [L-02] 使用绝对路径
                subprocess.run([
                    _PGDUMP_PATH,
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
                # Modified: [L-02] 使用绝对路径 + [L-03] with 管理文件句柄
                with open(dump_file, "w") as dump_fh:
                    subprocess.run([
                        _MYSQLDUMP_PATH,
                        "-h", parsed.hostname or "localhost",
                        "-P", str(parsed.port or 3306),
                        "-u", parsed.username or "root",
                        f"-p{parsed.password or ''}",
                        "--single-transaction",  # Added: MySQL InnoDB 一致性快照
                        parsed.path.lstrip("/")
                    ], stdout=dump_fh, timeout=300, check=True)
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


# Modified: [M-06] LoginAttempt 定时清理（兼容 SQLite/MySQL/PostgreSQL）
def _cleanup_login_attempts():
    """清理 N 天前的登录尝试记录，防止表无限膨胀"""
    import asyncio
    from sqlalchemy import text as sa_text
    
    async def _do_cleanup():
        keep_days = int(os.environ.get("LOGIN_ATTEMPT_KEEP_DAYS", "30"))
        try:
            async with AsyncSessionLocal() as session:
                if is_sqlite():
                    await session.execute(sa_text(
                        f"DELETE FROM login_attempts WHERE attempt_time < datetime('now', '-{keep_days} days')"
                    ))
                elif "mysql" in DATABASE_URL:
                    await session.execute(sa_text(
                        f"DELETE FROM login_attempts WHERE attempt_time < NOW() - INTERVAL {keep_days} DAY"
                    ))
                else:
                    await session.execute(sa_text(
                        f"DELETE FROM login_attempts WHERE attempt_time < NOW() - INTERVAL '{keep_days} days'"
                    ))
                await session.commit()
            logger.info(f"[清理] 已清理 {keep_days} 天前的登录尝试记录")
        except Exception as e:
            logger.error(f"[清理] LoginAttempt 清理失败: {e}")

    # 在新事件循环中运行异步任务
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_do_cleanup())
        else:
            loop.run_until_complete(_do_cleanup())
    except RuntimeError:
        asyncio.run(_do_cleanup())


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

    # Added: [M-06] 每 6 小时清理过期的 LoginAttempt 记录
    _scheduler.add_job(
        _cleanup_login_attempts,
        trigger="interval",
        hours=6,
        id="basalt_login_cleanup",
        name="LoginAttempt 过期记录清理",
        misfire_grace_time=3600
    )
    
    _scheduler.start()
    status = "已启用" if _config["enabled"] else "已关闭"
    logger.info(
        f"[调度器] 备份调度{status} — "
        f"每日 {_config['cron_hour']:02d}:{_config['cron_minute']:02d}，"
        f"保留 {_config['keep_days']} 天，路径 {_config['backup_dir']}"
    )
    logger.info("[调度器] LoginAttempt 清理任务已启用（每 6 小时）")


def stop_scheduler():
    """Added: 优雅停止调度器（供 lifespan shutdown 调用）"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("[调度器] 已停止。")
        _scheduler = None


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
        # Modified: [M-05 安全修复] 备份路径穿越防护
        _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        abs_backup = os.path.abspath(backup_dir)
        if not abs_backup.startswith(_project_root):
            logger.warning(f"[安全] 备份路径越界被拦截: {backup_dir} → {abs_backup}")
            return {"message": "错误：备份路径不能超出项目根目录", "error": True}
        _config["backup_dir"] = abs_backup
    if keep_days is not None:
        _config["keep_days"] = keep_days

    # 重新调度
    if _scheduler:
        try:
            _scheduler.remove_job("basalt_auto_backup")
        except Exception as e:
            logger.debug(f"移除旧备份任务时异常（可忽略）: {e}")  # Modified: [L-03] 不再静默吞异常
        
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
