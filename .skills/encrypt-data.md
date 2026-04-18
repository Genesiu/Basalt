---
trigger: encrypt_data
description: 在 Basalt 框架中正确处理敏感数据加密存储与脱敏展示
globs: ["modules/**/*.py"]
alwaysApply: false
---

# Skill: 敏感数据加密处理

当业务涉及 PII（个人身份信息）时，按本规范处理。

## 哪些数据必须加密

| 数据类型 | 必须加密 | 示例 |
|---------|---------|------|
| 手机号 | ✅ | 13800138000 |
| 身份证号 | ✅ | 110101199003071234 |
| 银行卡号 | ✅ | 6222021234567890 |
| 收货地址 | ✅ | 北京市朝阳区xxx |
| 姓名 | ⚠️ 按业务需求 | 张三 |
| 邮箱 | ⚠️ 按业务需求 | user@example.com |

## 加密存储

```python
from core.crypto import AESCipher

cipher = AESCipher()

# Model 层：存储密文
class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    encrypted_phone = Column(String(255))     # 密文字段
    encrypted_id_card = Column(String(255))   # 密文字段

# 写入时加密
new_customer = Customer(
    name="张三",
    encrypted_phone=cipher.encrypt("13800138000"),
    encrypted_id_card=cipher.encrypt("110101199003071234")
)

# 读取时解密（仅在需要明文时）
phone = cipher.decrypt(customer.encrypted_phone)
```

## 脱敏展示

API 返回时对敏感数据脱敏：

```python
def mask_phone(phone: str) -> str:
    """138****8000"""
    if len(phone) >= 7:
        return phone[:3] + "****" + phone[-4:]
    return "****"

def mask_id_card(id_card: str) -> str:
    """1101**********1234"""
    if len(id_card) >= 8:
        return id_card[:4] + "*" * (len(id_card) - 8) + id_card[-4:]
    return "****"

# API 返回脱敏数据
def _customer_to_dict(c):
    return {
        "id": c.id,
        "name": c.name,
        "phone_masked": mask_phone(cipher.decrypt(c.encrypted_phone)),
    }
```

## AES-256-GCM 特性

- 加密算法：AES-256-GCM（认证加密）
- 每次加密都生成随机 nonce，同一明文加密后密文不同
- 内置 Auth Tag，任何 1-bit 篡改都会抛出 `InvalidTag` 异常
- 密钥从 `.env` 文件中的 `AES_ENCRYPTION_KEY_B64` 加载
