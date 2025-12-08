from functools import lru_cache
from typing import Literal, Optional

from .base_cache import BaseCache
from .memory_cache import MemoryCache
from .redis_cache import RedisCache
from app.config import settings
from infrastructure.utils.logging_config import logger

CacheType = Literal["memory", "redis"]

# Use a simple variable to hold the singleton instance
_cache_instance: Optional[BaseCache] = None

def get_cache() -> BaseCache:
    """
    Factory function to create and return a cache instance based on settings.
    Ensures only one instance is created per application lifecycle (singleton).
    """
    global _cache_instance
    if _cache_instance is None:
        # Ensure cache_type comparison is case-insensitive
        cache_type_setting = settings.CACHE_TYPE.lower()
        if cache_type_setting not in CacheType.__args__: # Validate against Literal options
             logger.error(f"Invalid CACHE_TYPE configured: '{settings.CACHE_TYPE}'. Falling back to memory cache.")
             cache_type: CacheType = "memory" # type: ignore # Fallback type
        else:
             cache_type: CacheType = cache_type_setting # type: ignore # Assign validated type

        logger.info(f"Initializing cache instance with type: {cache_type}")

        if cache_type == "redis":
            _cache_instance = RedisCache()
        elif cache_type == "memory":
            _cache_instance = MemoryCache()
        else: # Fallback (shouldn't be reached with validation)
            _cache_instance = MemoryCache()

    return _cache_instance

# Function to explicitly close connections (e.g., during app shutdown)
async def close_cache_connections():
    """Closes connections for cache types that require it (like Redis pool)."""
    global _cache_instance
    if _cache_instance and isinstance(_cache_instance, RedisCache):
        logger.info("Closing Redis cache connection pool...")
        try:
            await RedisCache.close_redis_pool() # Use class method to close pool
            logger.info("Redis cache connection pool closed.")
        except Exception as e:
             logger.exception(f"Error closing Redis cache pool: {e}")
    elif _cache_instance:
         logger.debug(f"Cache type {_cache_instance.__class__.__name__} does not require explicit closing.")
    _cache_instance = None # Clear instance on shutdown
