"""
内存级速率限制器

在数据库查询前提供第一道防线，基于滑动窗口算法。
针对登录接口 (/api/v1/auth/login) 做 IP 维度限速。
"""

import time
import threading
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from core.ip_filter import get_real_ip


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    滑动窗口速率限制中间件
    
    - 仅对指定路径生效（默认只限制登录接口）
    - 基于真实 IP 计数
    - 超限返回 429 Too Many Requests
    """

    def __init__(self, app, rate_limit: int = 20, window_seconds: int = 60,
                 protected_paths: list = None):
        super().__init__(app)
        self.rate_limit = rate_limit          # 窗口内最大请求数
        self.window_seconds = window_seconds  # 滑动窗口大小（秒）
        self.protected_paths = protected_paths or ["/api/v1/auth/login", "/api/v1/auth/captcha"]
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def _cleanup(self):
        """定期清理过期条目（防止内存膨胀）"""
        now = time.time()
        if now - self._last_cleanup < 300:  # 每 5 分钟清理一次
            return
        with self._lock:
            cutoff = now - self.window_seconds * 2
            expired_keys = [k for k, v in self._requests.items()
                           if not v or v[-1] < cutoff]
            for k in expired_keys:
                del self._requests[k]
            self._last_cleanup = now

    async def dispatch(self, request: Request, call_next):
        # 仅对受保护路径生效
        if request.url.path not in self.protected_paths:
            return await call_next(request)

        client_ip = get_real_ip(request)
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # 清理该 IP 的过期记录
            timestamps = self._requests[client_ip]
            self._requests[client_ip] = [t for t in timestamps if t > window_start]

            if len(self._requests[client_ip]) >= self.rate_limit:
                retry_after = int(self.window_seconds - (now - self._requests[client_ip][0]))
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"请求过于频繁，请 {max(retry_after, 1)} 秒后重试。"},
                    headers={"Retry-After": str(max(retry_after, 1))}
                )

            self._requests[client_ip].append(now)

        self._cleanup()
        return await call_next(request)
