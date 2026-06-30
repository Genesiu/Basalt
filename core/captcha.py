"""
图形验证码生成与校验模块

使用纯 Python 生成 Base64 编码的 PNG 验证码图片，
无需外部服务依赖（如 reCAPTCHA）。

验证码存储在内存中（进程级缓存），5分钟自动过期。

⚠️ [S-03 部署约束] 本模块使用进程内存缓存，仅支持单 Worker 部署。
多 Worker 模式下（uvicorn --workers N > 1），验证码生成和校验可能路由到不同 Worker，
导致校验永远失败。生产环境如需多 Worker，请替换为 Redis 等共享存储。
"""

import os
import io
import time
import base64
import random   # 仅用于验证码视觉渲染干扰元素（非密码学场景）
import secrets  # Modified: [L-01] 验证码字符选取使用密码学安全随机
import hashlib
from typing import Optional, Tuple

# 验证码缓存: { captcha_id: (answer, expire_timestamp) }
_captcha_store: dict[str, Tuple[str, float]] = {}
CAPTCHA_EXPIRE_SECONDS = 300  # 5 分钟过期
CAPTCHA_LENGTH = 4
MAX_CAPTCHA_POOL = 10000  # Added: [M-02 安全修复] 防止内存无限膨胀


def _cleanup_expired():
    """清理过期验证码（惰性清理）"""
    now = time.time()
    expired_keys = [k for k, (_, exp) in _captcha_store.items() if now > exp]
    for k in expired_keys:
        del _captcha_store[k]


def generate_captcha() -> dict:
    """
    生成验证码，返回 { captcha_id, image_base64 }
    使用 SVG 格式渲染（无需 Pillow 依赖）
    """
    _cleanup_expired()
    
    # Modified: [M-02 安全修复] 池容量超限时强制淘汰最旧的一半
    if len(_captcha_store) > MAX_CAPTCHA_POOL:
        sorted_keys = sorted(_captcha_store, key=lambda k: _captcha_store[k][1])
        for k in sorted_keys[:len(sorted_keys) // 2]:
            del _captcha_store[k]
    
    # 生成随机字符（排除易混淆字符 0OIl1）
    # Modified: [L-01] 使用 secrets.choice 替代 random.choices
    _charset = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    chars = ''.join(secrets.choice(_charset) for _ in range(CAPTCHA_LENGTH))
    
    # 生成唯一 ID
    captcha_id = hashlib.sha256(os.urandom(32)).hexdigest()[:24]
    
    # 存储答案（不区分大小写）
    _captcha_store[captcha_id] = (chars.upper(), time.time() + CAPTCHA_EXPIRE_SECONDS)
    
    # 生成 SVG 图片
    svg = _render_svg_captcha(chars)
    image_b64 = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    
    return {
        "captcha_id": captcha_id,
        "image_base64": f"data:image/svg+xml;base64,{image_b64}"
    }


def verify_captcha(captcha_id: str, user_input: str) -> bool:
    """
    校验验证码（一次性消费，验证后立即删除）
    返回 True 表示验证通过

    ⚠️ [S-03 部署约束] 本模块使用进程内存缓存，仅支持单 Worker 部署。
    多 Worker 模式下，若请求路由至不同 Worker，验证码校验将始终返回失败。
    """
    if not captcha_id or not user_input:
        return False
    
    entry = _captcha_store.pop(captcha_id, None)
    if entry is None:
        return False
    
    answer, expire_at = entry
    if time.time() > expire_at:
        return False
    
    return user_input.upper() == answer


def _render_svg_captcha(text: str) -> str:
    """
    用 SVG 渲染带干扰线和噪点的验证码图片
    无需 Pillow / PIL，纯字符串拼接
    """
    width, height = 160, 60
    
    # 随机背景色（深色系）
    bg_r, bg_g, bg_b = random.randint(20, 40), random.randint(20, 40), random.randint(30, 50)
    
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        f'<rect width="{width}" height="{height}" fill="rgb({bg_r},{bg_g},{bg_b})"/>',
    ]
    
    # 干扰线 (6-8 条)
    for _ in range(random.randint(6, 8)):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        r, g, b = random.randint(60, 120), random.randint(60, 120), random.randint(60, 120)
        svg_parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="rgb({r},{g},{b})" stroke-width="{random.uniform(0.5, 1.5):.1f}"/>'
        )
    
    # 干扰圆点 (15-25 个)
    for _ in range(random.randint(15, 25)):
        cx, cy = random.randint(0, width), random.randint(0, height)
        radius = random.uniform(1, 3)
        r, g, b = random.randint(80, 160), random.randint(80, 160), random.randint(80, 160)
        svg_parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{radius:.1f}" fill="rgb({r},{g},{b})" opacity="0.5"/>'
        )
    
    # 渲染文字（每个字符独立定位 + 随机旋转）
    char_width = width / (len(text) + 1)
    for i, ch in enumerate(text):
        x = int(char_width * (i + 0.5)) + random.randint(-5, 5)
        y = height // 2 + random.randint(-8, 8)
        rotation = random.randint(-25, 25)
        font_size = random.randint(24, 32)
        r, g, b = random.randint(180, 255), random.randint(180, 255), random.randint(180, 255)
        svg_parts.append(
            f'<text x="{x}" y="{y}" font-size="{font_size}" font-family="monospace" '
            f'font-weight="bold" fill="rgb({r},{g},{b})" '
            f'transform="rotate({rotation},{x},{y})" '
            f'text-anchor="middle" dominant-baseline="central">{ch}</text>'
        )
    
    # 再加一层干扰弧线
    for _ in range(2):
        cx, cy = random.randint(20, width - 20), random.randint(10, height - 10)
        rx, ry = random.randint(30, 80), random.randint(10, 30)
        r, g, b = random.randint(100, 180), random.randint(100, 180), random.randint(100, 180)
        svg_parts.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
            f'fill="none" stroke="rgb({r},{g},{b})" stroke-width="0.8" opacity="0.6"/>'
        )
    
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)
