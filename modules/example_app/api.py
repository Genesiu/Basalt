from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from core.auth import RequirePermission, get_current_user
from core.ip_filter import ip_whitelist_checker
from core.audit import create_audit_log
from core.crypto import AESCipher
from core.database import get_db
from modules.example_app.schemas import EmployeeCreateSchema
from models.system import User

router = APIRouter(prefix="/employees", tags=["Business Example Demo"])

cipher = AESCipher()

@router.post("/", dependencies=[RequirePermission("user:manage"), Depends(ip_whitelist_checker)])
async def create_employee(
    request: Request,
    employee_in: EmployeeCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Modified: [QUAL-01] 注入真实用户
):
    """
    【AI Vibecoding 示范】
    安全隔离已被强卡口依赖 dependencies 锁死。
    """
    encrypted_phone = cipher.encrypt(employee_in.phone)
    
    # Modified: [QUAL-01] 使用真实操作人，不再硬编码 demo-admin
    await create_audit_log(
        db=db, request=request,
        action="CREATE_EMPLOYEE",
        details={"name": employee_in.name, "dept": employee_in.department},
        current_user_id=current_user.username
    )
    
    return {"message": "新建员工密文信息操作成功完毕"}

@router.get("/admin-only-data", dependencies=[RequirePermission("audit:view")])
async def get_admin_data():
    """只有审计管理员角色才能通过的安全路由"""
    return {"message": "读取等保流水库..."}
