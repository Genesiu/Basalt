import pyotp

class TOTPManager:
    """
    两步验证（MFA/2FA）离线算法支持库
    管理员无须公网连通和短信服务即可用 Authenticator 等安全应用扫码绑定
    """
    
    @staticmethod
    def generate_secret() -> str:
        """为用户实体生成离线动态口令基础密钥基底"""
        return pyotp.random_base32()
        
    @staticmethod
    def get_provisioning_uri(secret_key: str, username: str, issuer_name: str = "Basalt-Framework") -> str:
        """生成供通用手机扫描绑定二维码的标准 URL"""
        totp = pyotp.TOTP(secret_key)
        return totp.provisioning_uri(name=username, issuer_name=issuer_name)
        
    @staticmethod
    def verify_totp(secret_key: str, token: str, valid_window: int = 1) -> bool:
        """
        验证前端所提报的动态 6 位一次性密码。
        valid_window=1 提供容错机制，默许终端时钟漂移前后的 30 秒容差。
        """
        if not secret_key or not token:
            return False
        totp = pyotp.TOTP(secret_key)
        return totp.verify(token, valid_window=valid_window)
