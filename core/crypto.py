import base64
import os
import threading
import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes


class RSACipher:
    """
    RSA-2048 非对称加密 — 用于前端凭据传输加密
    
    安全设计要点:
    - 公钥暴露在前端 JS 中是安全的（只能加密，不能解密）
    - 私钥仅存在于服务端内存（每次启动重新生成，或从环境变量加载）
    - 使用 OAEP + SHA-256 填充，抗选择密文攻击
    """
    _instance = None
    _lock = threading.Lock()  # Added: [M-03 安全修复] 线程安全锁
    
    def __init__(self):
        # 尝试从环境变量加载持久化私钥，否则生成临时密钥对
        pem_b64 = os.environ.get("RSA_PRIVATE_KEY_B64")
        if pem_b64:
            pem_bytes = base64.b64decode(pem_b64)
            self._private_key = serialization.load_pem_private_key(pem_bytes, password=None)
        else:
            self._private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
        self._public_key = self._private_key.public_key()
    
    @classmethod
    def get_instance(cls):
        """单例模式（双重检查锁定），确保整个应用生命周期使用同一密钥对"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def get_public_key_pem(self) -> str:
        """导出 PEM 格式公钥（供前端 jsencrypt 使用）"""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    
    def decrypt(self, encrypted_b64: str) -> str:
        """用私钥解密前端 RSA 加密的 Base64 密文"""
        encrypted_bytes = base64.b64decode(encrypted_b64)
        # Modified: JSEncrypt 前端库使用 PKCS1v1.5 padding，必须匹配
        plain_bytes = self._private_key.decrypt(
            encrypted_bytes,
            padding.PKCS1v15()
        )
        return plain_bytes.decode('utf-8')

class Hasher:
    """
    密码纵深防御哈希工具类
    流程: plaintext → bcrypt hash → AES-256-GCM encrypt → 存储
    验证: 存储值 → AES decrypt → bcrypt verify
    
    安全设计要点:
    - bcrypt 提供单向不可逆哈希 + 自适应慢哈希抗暴力破解
    - AES-256-GCM 提供加密 + 完整性校验（防数据库被拖后仍需密钥才能离线攻击）
    - 向后兼容：旧的纯 bcrypt 格式（$2b$ 开头）仍可验证，首次登录改密后自动升级
    """
    
    # 缓存 AESCipher 实例（延迟初始化）
    _cipher = None
    _cipher_lock = threading.Lock()  # Added: [QUAL-04] 线程安全锁
    
    @classmethod
    def _get_cipher(cls):
        """延迟初始化 AES 加密器，避免模块加载阶段 .env 尚未就绪"""
        if cls._cipher is None:
            with cls._cipher_lock:
                if cls._cipher is None:
                    cls._cipher = AESCipher()
        return cls._cipher
    
    @staticmethod
    def _bcrypt_hash(password: str) -> str:
        """纯 bcrypt 哈希（内部使用）"""
        pwd_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(pwd_bytes, salt)
        return hashed_password.decode('utf-8')
    
    @staticmethod
    def _bcrypt_verify(plain_password: str, bcrypt_hash: str) -> bool:
        """纯 bcrypt 验证（内部使用）"""
        pwd_bytes = plain_password.encode('utf-8')
        hashed_bytes = bcrypt_hash.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    
    @staticmethod
    def _is_plain_bcrypt(stored: str) -> bool:
        """检测是否为旧格式的纯 bcrypt 哈希（$2b$/$2a$ 开头）"""
        return stored.startswith('$2b$') or stored.startswith('$2a$')

    @classmethod
    def get_password_hash(cls, password: str) -> str:
        """
        生成双层防护密码哈希：bcrypt → AES-256-GCM 加密
        存储格式: Base64(nonce + AES-GCM(bcrypt_hash))
        """
        bcrypt_hash = cls._bcrypt_hash(password)
        cipher = cls._get_cipher()
        return cipher.encrypt(bcrypt_hash)

    @classmethod
    def verify_password(cls, plain_password: str, stored_password: str) -> bool:
        """
        验证密码（自动兼容新旧格式）
        - 新格式: AES decrypt → bcrypt verify
        - 旧格式: 直接 bcrypt verify（$2b$ 开头）
        """
        # 向后兼容：旧的纯 bcrypt 格式
        if cls._is_plain_bcrypt(stored_password):
            return cls._bcrypt_verify(plain_password, stored_password)
        
        # 新格式：先 AES 解密，再 bcrypt 验证
        try:
            cipher = cls._get_cipher()
            bcrypt_hash = cipher.decrypt(stored_password)
            return cls._bcrypt_verify(plain_password, bcrypt_hash)
        except Exception:
            # 解密失败（密钥不匹配或数据被篡改）
            return False


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
