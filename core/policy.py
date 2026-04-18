import re
from datetime import datetime
from fastapi import HTTPException, status

class PasswordPolicyEngine:
    """等保三级高约束要求：账号生命周期与密码安全基线策略"""
    
    # 强制正则要求：至少 8 字符组合，至少 1 大写字母，1 小写字母，1数字，1特殊符号
    COMPLEXITY_REGEX = re.compile(
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=~.,?])[A-Za-z\d!@#$%^&*()_+\-=~.,?]{8,}$"
    )
    
    PASSWORD_MAX_AGE_DAYS = 90
    MAX_LOGIN_FAILURES = 5
    LOCKOUT_DURATION_MINUTES = 30
    PASSWORD_HISTORY_COUNT = 5  # Added: 禁止重复使用近 N 次密码

    @classmethod
    def validate_complexity(cls, password: str, username: str = None):
        """
        强制复杂度预检切面
        Added: 等保 8.1.4.1i — 密码不得与用户名相同
        """
        if not cls.COMPLEXITY_REGEX.match(password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码过于脆弱：必须至少包含8位，且混合大写字母、小写字母、数字组合以及特殊字符。"
            )
        
        # Added: 密码不得与用户名相同（不区分大小写）
        if username and password.lower() == username.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码不得与用户名相同。"
            )
        
        # Added: 密码不得包含用户名（不区分大小写，3字符以上用户名才检测）
        if username and len(username) >= 3 and username.lower() in password.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码不得包含用户名。"
            )
            
    @classmethod
    def is_password_expired(cls, password_updated_at: datetime) -> bool:
        """验证口令是否越界死亡循环 (90 Days)"""
        if not password_updated_at:
            return True
        delta = datetime.utcnow() - password_updated_at
        return delta.days >= cls.PASSWORD_MAX_AGE_DAYS

    @classmethod
    def check_lockout_status(cls, is_locked: bool, lock_expires_at: datetime) -> bool:
        """评估账号封禁状态是否依然生效"""
        if not is_locked:
            return False
            
        if lock_expires_at and lock_expires_at > datetime.utcnow():
            return True  # 在小黑屋时期
            
        return False  # 已过封禁衰减期

    @classmethod
    def check_password_history(cls, plain_password: str, history_hashes: list[str]) -> bool:
        """
        Added: 等保 8.1.4.1j — 检查新密码是否与近 N 次历史密码重复
        返回 True 表示密码重复（不合规），False 表示可用
        """
        from core.crypto import Hasher
        for old_hash in history_hashes:
            if Hasher.verify_password(plain_password, old_hash):
                return True  # 发现重复
        return False
