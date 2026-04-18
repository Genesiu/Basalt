"""
等保三级安全标记机制（8.1.4.2g/h）

提供强制访问控制（MAC）骨架，与 RBAC 并行运行。
命名采用企业数据分类术语，严格避免使用国家秘密等级用语（秘密/机密/绝密），
以免在审计和合规场景中与《保守国家秘密法》产生冲突。

框架职责：提供枚举、Mixin、装饰器
业务职责：给数据打标、给角色分配许可等级
"""

import enum
from sqlalchemy import Column, Integer
from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.auth import get_current_user
from core.database import get_db


class SecurityLevel(int, enum.Enum):
    """
    企业数据分类分级标记（非国家秘密等级）
    
    注意：本枚举仅为企业内部数据管理使用，
    与《中华人民共和国保守国家秘密法》所定义的国家秘密等级无关。
    """
    PUBLIC = 0       # 公开：可对外披露的信息
    INTERNAL = 1     # 内部：仅限企业内部人员访问
    SENSITIVE = 2    # 敏感：限特定岗位或业务角色访问
    CORE = 3         # 核心：仅最高权限管理者可触及

    @classmethod
    def label(cls, level: int) -> str:
        """人类可读标签"""
        _labels = {0: "公开", 1: "内部", 2: "敏感", 3: "核心"}
        return _labels.get(level, "未知")
    
    @classmethod
    def all_choices(cls) -> list:
        """供前端渲染的选项列表"""
        return [
            {"value": e.value, "label": cls.label(e.value), "code": e.name}
            for e in cls
        ]


class SecurityLabelMixin:
    """
    Model Mixin：任何业务数据表继承此 Mixin 即自动获得 security_level 字段。
    
    使用方式：
        class Contract(Base, SecurityLabelMixin):
            __tablename__ = "contracts"
            title = Column(String)
            ...
    
    创建记录时：
        new_contract = Contract(title="xxx", security_level=SecurityLevel.SENSITIVE)
    """
    security_level = Column(
        Integer, 
        default=SecurityLevel.INTERNAL.value,
        nullable=False,
        comment="数据安全标记等级：0=公开 1=内部 2=敏感 3=核心"
    )


def RequireSecurityClearance(min_level: SecurityLevel):
    """
    MAC 强制访问控制装饰器。
    
    与 RequirePermission 并行使用，实现双重访问控制：
      - RequirePermission：检查用户「能做什么」（RBAC）
      - RequireSecurityClearance：检查用户「能看什么密级」（MAC）
    
    使用方式：
        @router.get("/contracts", dependencies=[
            RequirePermission("contract:view"),
            RequireSecurityClearance(SecurityLevel.SENSITIVE)
        ])
        async def list_contracts(): ...
    
    前提：角色表（Role）需包含 max_clearance 字段。
    """
    async def _clearance_checker(
        current_user = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        from models.system import Role
        result = await db.execute(select(Role).where(Role.code == current_user.role_code))
        role = result.scalars().first()
        
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="角色不存在，无法进行安全等级校验。"
            )
        
        # max_clearance 默认为 0（仅公开），未配置时从严
        user_clearance = getattr(role, 'max_clearance', 0) or 0
        
        if user_clearance < min_level.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"安全等级不足：您的许可等级为「{SecurityLevel.label(user_clearance)}」，"
                       f"该资源要求「{SecurityLevel.label(min_level.value)}」及以上。"
            )
        return current_user
    
    return Depends(_clearance_checker)
