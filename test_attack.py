"""
Basalt 等保防线自动预演：暴力破解攻击模拟

Modified: [QUAL-02] 适配 RSA 加密 JSON 登录接口
使用方式: python test_attack.py
"""
import requests
import json
import time
import sys

API_BASE = "http://127.0.0.1:8000/api/v1/auth"


def get_public_key():
    """获取 RSA 公钥"""
    try:
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_OAEP
        from Crypto.Hash import SHA256
    except ImportError:
        print("❌ 需要安装 pycryptodome: pip install pycryptodome")
        sys.exit(1)

    res = requests.get(f"{API_BASE}/public-key", timeout=5)
    res.raise_for_status()
    pem = res.json()["public_key"]
    return RSA.import_key(pem)


def rsa_encrypt(public_key, payload: dict) -> str:
    """RSA-OAEP 加密 JSON 载荷"""
    from Crypto.Cipher import PKCS1_OAEP
    from Crypto.Hash import SHA256
    import base64

    cipher = PKCS1_OAEP.new(public_key, hashAlgo=SHA256)
    encrypted = cipher.encrypt(json.dumps(payload).encode())
    return base64.b64encode(encrypted).decode()


def test_brute_force():
    print("\n--- 🚨 等保防线自动预演：暴力破解攻击模拟 ---\n")

    try:
        pubkey = get_public_key()
        print("✅ 已获取 RSA 公钥\n")
    except Exception as e:
        print(f"❌ 无法连接后端: {e}")
        return

    for i in range(1, 8):
        creds = {"username": "sysadmin", "password": f"wrongpassword_{i}"}
        encrypted = rsa_encrypt(pubkey, creds)

        body = {"encrypted_payload": encrypted, "captcha_id": "", "captcha_code": ""}
        print(f"[攻击流 #{i}] 尝试凭证: {creds['username']} / {creds['password']}")

        res = requests.post(f"{API_BASE}/login", json=body, timeout=10)
        status = res.status_code
        detail = res.json().get("detail", "")

        if status == 400:
            print(f"  ⚡ 验证码防线触发 (400): {detail}")
        elif status == 401:
            print(f"  ✔️ 被系统优雅拦截 (401): {detail}")
        elif status == 403:
            print(f"  🛑 等保红线触发 (403 Forbidden): {detail}")
        elif status == 429:
            print(f"  🚫 速率限制触发 (429 Too Many Requests): {detail}")
        else:
            print(f"  ❓ 未知状态: {status} - {res.text}")

        time.sleep(0.3)

    print("\n--- ✅ 预演结束 ---")


if __name__ == "__main__":
    test_brute_force()
