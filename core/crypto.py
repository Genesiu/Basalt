import base64
import os
import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class Hasher:
    """密码单向不可逆哈希工具类"""
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        # Bcrypt 机制先天自带随机加盐策略
        pwd_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(pwd_bytes, salt)
        return hashed_password.decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        pwd_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)


class AESCipher:
    """
    业务数据保密性与完整性联合防御 (AES-256-GCM)
    等保合规要求：底层数据库的脏数据篡改不仅要加密，还要被应用拦截
    """
    def __init__(self, key_base64: str = None):
        # 密钥要求: 必须是 32 位随机字节的 Base64 字符串
        if not key_base64:
            key_base64 = os.environ.get("AES_ENCRYPTION_KEY_B64")
        if not key_base64:
            raise ValueError("系统加密依赖 AES_ENCRYPTION_KEY_B64 未从环境变量挂载")
        
        self.key = base64.b64decode(key_base64)
        if len(self.key) != 32:
            raise ValueError("AES key必须精准为32字节 (256-bit) 以满足合规引擎")
        
        self.aesgcm = AESGCM(self.key)

    def encrypt(self, plain_text: str) -> str:
        if plain_text is None:
            return None
        # 初始化唯一随机向量 Nonce
        nonce = os.urandom(12)
        # Auth Tag被自动附加于密文尾端
        cipher_text_with_tag = self.aesgcm.encrypt(nonce, plain_text.encode('utf-8'), None)
        combined = nonce + cipher_text_with_tag
        return base64.b64encode(combined).decode('utf-8')

    def decrypt(self, encrypted_b64: str) -> str:
        if encrypted_b64 is None:
            return None
            
        combined = base64.b64decode(encrypted_b64)
        if len(combined) < 12:
            raise ValueError("无法解密，载荷结构不完整")
            
        nonce = combined[:12]
        cipher_text_with_tag = combined[12:]
        # 万一数据库后台记录被直接触碰修改哪怕1 bit，解密立刻雪崩并抛出 InvalidTag 异常！
        plain_bytes = self.aesgcm.decrypt(nonce, cipher_text_with_tag, None)
        return plain_bytes.decode('utf-8')
