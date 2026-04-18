from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.database import get_db
from models.system import IPWhitelist
import ipaddress

def get_real_ip(request: Request) -> str:
    """对抗代理流量欺骗穿透：抓取真实源 IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # 当使用正向/反向代理链时，第一个 IP 通常为发起端真实 IP
        return forwarded.split(",")[0].strip()
    return request.client.host

async def ip_whitelist_checker(request: Request, db: AsyncSession = Depends(get_db)):
    """
    IP 白名单网关卡口 (利用 Depends 进行路由层拦截)
    使用说明：在特定后端高权限 API路由处增加 Dependencies
    """
    real_ip = get_real_ip(request)
    
    result = await db.execute(select(IPWhitelist))
    whitelists = result.scalars().all()
    
    # 评测基线原则: 如果白名单未定义，则只容许 localhost 执行调试通信
    if not whitelists:
        if real_ip not in ["127.0.0.1", "::1"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="系统处于冷启动基线阻断状态，必须由本地配置至少一条白名单规则。"
            )
        return real_ip
        
    client_ip_obj = ipaddress.ip_address(real_ip)
    
    for wl in whitelists:
        network = ipaddress.ip_network(wl.ip_network, strict=False)
        if client_ip_obj in network:
            return real_ip
            
    # 无匹配即为被阻断
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"安全源阻断：当前发启端接入网络地址 {real_ip} 被访问控制防火墙拦截。"
    )
