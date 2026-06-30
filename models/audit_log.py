from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text
from core.database import Base

class AuditLog(Base):
    """
    等保三级审计流水表
    强制安全规则：此表在应用层只接受 APPEND 操作
    Modified: 增加 prev_hash 字段，形成链式完整性校验（防篡改）
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    user_id = Column(String(50), nullable=False, index=True)      # 操作人 UID
    ip_address = Column(String(45), nullable=False)               # 发起点真实IP
    action = Column(String(100), nullable=False)                  # 动作: 例如 USER_LOGIN, 修改配置
    resource = Column(String(255), nullable=False)                # 目标对象 URI 或表
    status = Column(String(20), nullable=False)                   # 操作结果: SUCCESS / FAILED
    details = Column(Text, nullable=True)                         # 上下文或脱敏负载JSON
    # Added: 链式哈希 — 存储前一条日志的 SHA-256 摘要，形成防篡改证据链
    prev_hash = Column(String(64), nullable=True, default="GENESIS")
