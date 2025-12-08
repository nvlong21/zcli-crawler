import redis.asyncio as redis
import pickle # Use standard library pickle
from typing import Any, Optional
import logging

from .base_cache import BaseCache
from app.config import settings
from infrastructure.utils.logging_config import logger

class RedisCache(BaseCache):
    """Redis cache implementation using redis-py's async client."""

    _redis_client: Optional[redis.Redis] = None
    _redis_pool: Optional[redis.ConnectionPool] = None

    @classmethod
    async def _get_redis_client(cls) -> redis.Redis:
        """Gets or initializes the Redis client using a connection pool."""
        if cls._redis_client is None:
            if cls._redis_pool is None:
                logger.info("Initializing Redis connection pool...")
                try:
                    redis_url = settings.REDIS_URL # Prefer URL format
                    if not redis_url:
                        password_part = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
                        # Ensure host and port are strings for URL construction
                        redis_url = f"redis://{password_part}{str(settings.REDIS_HOST)}:{str(settings.REDIS_PORT)}/{str(settings.REDIS_DB)}"

                    # Create pool - decode_responses=False to handle bytes (for pickle)
                    cls._redis_pool = redis.ConnectionPool.from_url(
                        str(redis_url), # Ensure URL is a string
                        decode_responses=False,
                        socket_timeout=5,
                        socket_connect_timeout=5,
                        health_check_interval=30, # Check connection periodically
                        max_connections=getattr(settings, "REDIS_MAX_CONNECTIONS", 10) # Use setting or default
                    )
                    # Mask password in log
                    log_url = str(redis_url)
                    if settings.REDIS_PASSWORD: log_url = log_url.replace(settings.REDIS_PASSWORD, '*****')
                    logger.info(f"Redis connection pool created for URL: {log_url}")

                except Exception as e:
                    logger.exception(f"FATAL: Failed to create Redis connection pool: {e}")
                    raise ConnectionError(f"Failed to initialize Redis pool: {e}") from e

            # Create client instance from the pool
            cls._redis_client = redis.Redis(connection_pool=cls._redis_pool)
            logger.info("Redis client instance created from pool.")

            # Perform initial PING check
            try:
                 await cls.ping() # Use the class's ping method
            except ConnectionError: # Ping raises ConnectionError on failure
                 # Allow initialization but log error, subsequent calls will likely fail until Redis is up
                 logger.error("Initial PING to Redis failed. Check Redis server and connection settings.")
                 # Don't raise here, allow lazy connection attempts

        return cls._redis_client

    @classmethod
    async def close_redis_pool(cls):
        """Closes the Redis client connection pool if it exists."""
        client = cls._redis_client
        pool = cls._redis_pool
        cls._redis_client = None # Prevent reuse during closing
        cls._redis_pool = None

        # Client closing behavior in redis-py with pools might just return conn to pool.
        # Closing the pool is the important part.
        # if client: ...

        if pool:
            logger.info("Disconnecting Redis connection pool.")
            try:
                 await pool.disconnect(inuse_connections=True) # Force close active connections
                 logger.info("Redis connection pool disconnected.")
            except Exception as e:
                 logger.error(f"Error disconnecting Redis connection pool: {e}", exc_info=True)

    async def get(self, key: str) -> Optional[Any]:
        """Retrieves and unpickles an item from Redis."""
        try:
            client = await self._get_redis_client()
            cached_bytes = await client.get(key)
            if cached_bytes:
                logger.debug(f"Redis Cache HIT for key: {key}")
                try:
                    # Deserialize using standard pickle
                    return pickle.loads(cached_bytes)
                except (pickle.UnpicklingError, EOFError, TypeError, ValueError) as e:
                     logger.error(f"Failed to unpickle Redis value for key '{key}'. Corrupted data? Error: {e}", exc_info=True)
                     # Optionally delete the corrupted key
                     # await self.delete(key)
                     return None
            else:
                logger.debug(f"Redis Cache MISS for key: {key}")
                return None
        except redis.RedisError as e:
             # Log Redis-specific errors less verbosely in production
             log_level = logging.DEBUG if isinstance(e, redis.ConnectionError) else logging.ERROR
             logger.log(log_level, f"Redis error getting key '{key}': {e.__class__.__name__} - {e}", exc_info=False)
             return None # Fail safe: treat Redis errors as cache miss
        except Exception as e:
             logger.exception(f"Unexpected error getting key '{key}' from Redis: {e}")
             return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Pickles and stores an item in Redis with optional TTL."""
        try:
            client = await self._get_redis_client()
            # Serialize using standard pickle (use HIGHEST_PROTOCOL for efficiency)
            serialized_value = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)

            logger.debug(f"Redis Cache SET for key: {key}, TTL: {ttl}s")
            # Use 'ex' for TTL in seconds.
            if ttl is not None and ttl > 0:
                 await client.set(key, serialized_value, ex=ttl)
            elif ttl == 0 or ttl is None: # Treat 0 and None as indefinite TTL for simplicity
                 await client.set(key, serialized_value)
                 logger.debug(f"Set key '{key}' with indefinite TTL.")
            elif ttl < 0: # Treat negative TTL as delete
                 await self.delete(key)

        except redis.RedisError as e:
             logger.error(f"Redis error setting key '{key}': {e.__class__.__name__} - {e}", exc_info=False)
        except (pickle.PicklingError, TypeError, ValueError) as e:
             logger.error(f"Failed to pickle value for Redis key '{key}': {e}", exc_info=True)
        except Exception as e:
             logger.exception(f"Unexpected error setting key '{key}' in Redis: {e}")

    async def delete(self, key: str) -> bool:
        """Deletes an item from Redis."""
        try:
            client = await self._get_redis_client()
            result = await client.delete(key)
            deleted = result > 0
            logger.debug(f"Redis Cache DELETE for key: {key} {'succeeded' if deleted else 'failed (not found)'}")
            return deleted
        except redis.RedisError as e:
             logger.error(f"Redis error deleting key '{key}': {e.__class__.__name__} - {e}", exc_info=False)
             return False
        except Exception as e:
             logger.exception(f"Unexpected error deleting key '{key}' from Redis: {e}")
             return False

    async def exists(self, key: str) -> bool:
        """Checks if a key exists in Redis."""
        try:
            client = await self._get_redis_client()
            result = await client.exists(key)
            return result > 0
        except redis.RedisError as e:
             logger.error(f"Redis error checking existence of key '{key}': {e.__class__.__name__} - {e}", exc_info=False)
             return False
        except Exception as e:
             logger.exception(f"Unexpected error checking existence of key '{key}' in Redis: {e}")
             return False

    async def clear(self) -> bool:
        """Clears the current Redis database (FLUSHDB). Use with extreme caution!"""
        if settings.ENVIRONMENT not in ["testing", "development"]:
             logger.error("Cache clearing (FLUSHDB) is disabled outside of testing/development environments for safety.")
             return False
        try:
            client = await self._get_redis_client()
            logger.warning(f"Clearing Redis cache (FLUSHDB) for DB: {settings.REDIS_DB} in environment: {settings.ENVIRONMENT}!")
            # flushdb is synchronous in redis-py v4+, but await for async client pattern
            await client.flushdb() # Returns bool confirmation
            logger.info(f"Redis DB {settings.REDIS_DB} cleared.")
            return True
        except redis.RedisError as e:
             logger.error(f"Redis error clearing cache (FLUSHDB): {e.__class__.__name__} - {e}", exc_info=False)
             return False
        except Exception as e:
             logger.exception(f"Unexpected error clearing Redis cache: {e}")
             return False

    @classmethod
    async def ping(cls) -> bool:
        """Checks the connection to the Redis server."""
        try:
            # Get client instance (this might initialize pool/client if not done yet)
            client = await cls._get_redis_client()
            await client.ping()
            logger.debug("Redis PING successful.")
            return True
        except (redis.RedisError, ConnectionError, TimeoutError) as e:
             logger.error(f"Redis PING failed: {e.__class__.__name__} - {e}", exc_info=False)
             # Re-raise as a standard ConnectionError for consistent handling upstream
             raise ConnectionError("Failed to connect to Redis") from e
        except Exception as e:
             logger.exception(f"Unexpected error during Redis PING: {e}")
             raise ConnectionError("Unexpected error connecting to Redis") from e
