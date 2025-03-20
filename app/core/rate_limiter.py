from fastapi import Request, HTTPException, status
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis
from ..core.config import settings
import ipaddress

# Rate limiting for login attempts (5 per minute)
login_rate_limiter = RateLimiter(times=5, seconds=60)

# Rate limiting for registration (3 per hour)
registration_rate_limiter = RateLimiter(times=3, seconds=3600)

# Rate limiting for password reset (3 per hour)
password_reset_rate_limiter = RateLimiter(times=3, seconds=3600)

# General API rate limiter (100 requests per minute)
general_rate_limiter = RateLimiter(times=100, seconds=60)


async def setup_rate_limiter():
    """
    Initialize the rate limiter with Redis
    """
    redis_instance = redis.Redis(
        host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True
    )
    await FastAPILimiter.init(redis_instance)


def get_client_ip(request: Request) -> str:
    """
    Get the client IP address from the request
    """
    # Check for X-Forwarded-For header (for proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Get the first IP in the list
        ip = forwarded_for.split(",")[0].strip()
        try:
            # Validate IP address
            ipaddress.ip_address(ip)
            return ip
        except ValueError:
            pass

    # Fallback to client.host
    return request.client.host
