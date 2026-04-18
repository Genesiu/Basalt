"""
等保三级测评材料一键导出（GB/T 22239-2019）

生成 ZIP 材料包，包含：
- 用户权限矩阵
- 角色清单与安全等级
- 审计日志全量 CSV
- 安全策略配置
- IP 白名单
- 密码策略摘要
"""

import io
import csv
import json
import zipfile
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_db
from core.auth import RequirePermission
from core.ip_filter import ip_whitelist_checker
from models.system import User, Role, SystemConfig, IPWhitelist
from models.audit_log import AuditLog
from core.security_label import SecurityLevel

router = APIRouter(
    tags=["等保合规"],
    dependencies=[RequirePermission("audit:export"), Depends(ip_whitelist_checker)]
)


def _csv_to_bytes(headers: list, rows: list) -> bytes:
    """将数据生成 CSV 字节流"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")  # BOM 兼容 Excel


@router.get("/export/package")
async def export_compliance_package(db: AsyncSession = Depends(get_db)):
    """
    一键生成等保三级测评材料 ZIP 包

    包含：
    1. 用户权限矩阵.csv
    2. 角色与安全等级.csv
    3. 安全策略配置.csv
    4. IP 白名单.csv
    5. 审计日志全量.csv
    6. 合规声明.txt
    """
    zip_buffer = io.BytesIO()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:

        # ── 1. 用户权限矩阵 ──
        users_result = await db.execute(select(User).order_by(User.id))
        roles_result = await db.execute(select(Role).order_by(Role.id))
        roles_map = {r.code: r for r in roles_result.scalars().all()}

        user_rows = []
        for u in users_result.scalars().all():
            role = roles_map.get(u.role_code)
            user_rows.append([
                u.id, u.username, u.role_code,
                role.name if role else "未知",
                ", ".join(role.permissions) if role else "",
                SecurityLevel.label(role.max_clearance) if role else "未知",
                "启用" if u.is_active else "停用",
                str(u.last_login_at or "从未登录"),
                str(u.password_updated_at or "未设置")
            ])
        zf.writestr(
            f"01_用户权限矩阵.csv",
            _csv_to_bytes(
                ["ID", "用户名", "角色代码", "角色名称", "权限节点", "安全等级", "状态", "最后登录", "创建时间"],
                user_rows
            )
        )

        # ── 2. 角色与安全等级 ──
        roles_result2 = await db.execute(select(Role).order_by(Role.id))
        role_rows = []
        for r in roles_result2.scalars().all():
            role_rows.append([
                r.id, r.code, r.name,
                ", ".join(r.permissions) if r.permissions else "无",
                r.max_clearance, SecurityLevel.label(r.max_clearance)
            ])
        zf.writestr(
            f"02_角色与安全等级.csv",
            _csv_to_bytes(
                ["ID", "角色代码", "角色名称", "权限节点", "安全等级值", "安全等级标签"],
                role_rows
            )
        )

        # ── 3. 安全策略配置 ──
        configs_result = await db.execute(select(SystemConfig).order_by(SystemConfig.key))
        config_rows = []
        policy_desc = {
            "LOGIN_MAX_FAILURES": "登录失败锁定阈值（次）",
            "LOGIN_LOCKOUT_MINUTES": "账号锁定时长（分钟）",
            "PWD_MAX_AGE_DAYS": "密码最大有效期（天）",
            "SESSION_TIMEOUT_MINS": "会话超时时间（分钟）",
            "PWD_MIN_LENGTH": "密码最小长度",
            "INACTIVE_DAYS_LIMIT": "不活跃账号停用天数",
        }
        for c in configs_result.scalars().all():
            config_rows.append([
                c.key, c.value,
                policy_desc.get(c.key, ""),
                "8.1.4.1" if "PWD" in c.key else "8.1.4.1d" if "LOGIN" in c.key else "8.1.4.1f"
            ])
        zf.writestr(
            f"03_安全策略配置.csv",
            _csv_to_bytes(["配置项", "当前值", "说明", "对应等保条款"], config_rows)
        )

        # ── 4. IP 白名单 ──
        whitelist_result = await db.execute(select(IPWhitelist).order_by(IPWhitelist.id))
        wl_rows = []
        for w in whitelist_result.scalars().all():
            wl_rows.append([w.id, w.ip_network, w.description or "", str(w.created_at)])
        zf.writestr(
            f"04_IP白名单.csv",
            _csv_to_bytes(["ID", "IP/CIDR", "描述", "创建时间"], wl_rows)
        )

        # ── 5. 审计日志全量 ──
        audit_result = await db.execute(select(AuditLog).order_by(AuditLog.id))
        audit_rows = []
        for a in audit_result.scalars().all():
            audit_rows.append([
                a.id, str(a.timestamp), a.user_id or "",
                a.action, a.status, a.ip_address or "",
                json.dumps(a.details, ensure_ascii=False) if a.details else ""
            ])
        zf.writestr(
            f"05_审计日志全量.csv",
            _csv_to_bytes(["ID", "时间", "操作人", "动作", "状态", "IP地址", "详情"], audit_rows)
        )

        # ── 6. 合规声明 ──
        compliance_text = f"""Basalt Framework 等保三级合规材料包
生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
框架版本：v2.0.0
合规标准：GB/T 22239-2019《信息安全技术 网络安全等级保护基本要求》第三级

本材料包由系统自动生成，包含以下内容：
1. 用户权限矩阵 — 对应条款 8.1.4.2（访问控制）
2. 角色与安全等级 — 对应条款 8.1.4.2g/h（安全标记）+ 8.1.5（安全管理中心）
3. 安全策略配置 — 对应条款 8.1.4.1（身份鉴别）
4. IP 白名单 — 对应条款 8.1.4.4c（入侵防范）
5. 审计日志全量 — 对应条款 8.1.4.3（安全审计）

声明：
本框架内置的安全标记等级（公开/内部/敏感/核心）为企业数据分类术语，
与《中华人民共和国保守国家秘密法》所定义的国家秘密等级无关。

Build on Basalt. Secure by default. | by Genesiu
"""
        zf.writestr("00_合规声明.txt", compliance_text.encode("utf-8"))

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="basalt_compliance_{ts}.zip"'}
    )


@router.post("/backup/trigger")
async def trigger_manual_backup():
    """手动触发一次数据库备份"""
    from core.scheduler import trigger_backup_now
    trigger_backup_now()
    return {"message": "备份任务已执行，请在 backups/ 目录查看结果"}

