import requests
import time

API_URL = "http://127.0.0.1:8000/api/v1/auth/login"

def test_brute_force():
    payload = {
        "grant_type": "password",
        "username": "sysadmin",
        "password": "wrongpassword"
    }

    print("\n--- 🚨 等保防线自动预演：极速黑客字典爆破攻击 ---")
    for i in range(1, 8):
        print(f"\n[攻击流 #{i}] 尝试侵入凭证: {payload['username']} / {payload['password']}")
        res = requests.post(API_URL, data=payload)
        
        status = res.status_code
        detail = res.json().get("detail", "")
        
        if status == 401:
            print(f"✔️ 被系统优雅拦截 (401). {detail}")
        elif status == 403:
            print(f"🛑 等保红线触发断路保护 (HTTP 403 Forbidden)! ")
            print(f"   返回体信息: << {detail} >>")
        else:
            print(f"未知状态: {status} - {res.text}")
            
        time.sleep(0.5)

if __name__ == "__main__":
    test_brute_force()
