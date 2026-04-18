from pydantic import BaseModel, ConfigDict
from typing import Optional

class EmployeeCreateSchema(BaseModel):
    name: str
    phone: str
    department: str

class EmployeeResponseSchema(BaseModel):
    id: int
    name: str
    department: str
    # 强制在视图层屏蔽原始明文暴露
    phone_masked: str
    
    model_config = ConfigDict(from_attributes=True)
