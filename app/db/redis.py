import redis.asyncio as redis
from ..core.config import settings

# Create Redis connection
redis_client = redis.Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True
)


async def get_redis():
    """
    Dependency to get Redis connection
    """
    try:
        yield redis_client
    finally:
        await redis_client.aclose()


async def init_redis_pool():
    """
    Initialize Redis connection pool
    """
    return redis_client
