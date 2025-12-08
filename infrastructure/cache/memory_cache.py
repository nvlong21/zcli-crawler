from typing import Any, Optional, Dict, Tuple
import time
import asyncio

from .base_cache import BaseCache
from infrastructure.utils.logging_config import logger

# Simple thread-safe dictionary-based in-memory cache with TTL support
_cache_store: Dict[str, Tuple[Any, Optional[float]]] = {}
_cache_lock = asyncio.Lock() # Lock for async safety

class MemoryCache(BaseCache):
    """A simple in-memory cache implementation with TTL."""

    async def get(self, key: str) -> Optional[Any]:
        async with _cache_lock:
            item = _cache_store.get(key)
            if item:
                value, expiry = item
                # Use time.monotonic() for TTL checks as it's not affected by system clock changes
                if expiry is None or time.monotonic() < expiry:
                    logger.debug(f"Memory Cache HIT for key: {key}")
                    return value
                else:
                    # Expired item, remove it lazily
                    logger.debug(f"Memory Cache EXPIRED for key: {key}")
                    # Ensure key still exists before deleting (might have been re-set)
                    if key in _cache_store and _cache_store[key] == item:
                         del _cache_store[key]
            logger.debug(f"Memory Cache MISS for key: {key}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Sets value with TTL in seconds."""
        expiry_time = (time.monotonic() + ttl) if ttl is not None and ttl > 0 else None
        if ttl == 0: # Cache indefinitely
             expiry_time = None
        elif ttl is not None and ttl < 0: # Treat negative TTL as immediate expiration (delete)
             logger.debug(f"Memory Cache DELETE (via negative TTL) for key: {key}")
             await self.delete(key) # Use delete method to ensure lock safety
             return

        async with _cache_lock:
            logger.debug(f"Memory Cache SET for key: {key}, TTL: {ttl}s, Expiry Ts (monotonic): {expiry_time}")
            _cache_store[key] = (value, expiry_time)

    async def delete(self, key: str) -> bool:
        async with _cache_lock:
            if key in _cache_store:
                logger.debug(f"Memory Cache DELETE for key: {key}")
                del _cache_store[key]
                return True
            logger.debug(f"Memory Cache DELETE failed: key '{key}' not found.")
            return False

    async def exists(self, key: str) -> bool:
        # Check existence without altering cache state, considering TTL
        async with _cache_lock:
            item = _cache_store.get(key)
            if item:
                _, expiry = item
                if expiry is None or time.monotonic() < expiry:
                    return True
            return False

    async def clear(self) -> bool:
        async with _cache_lock:
            count = len(_cache_store)
            logger.warning(f"Clearing in-memory cache! ({count} items)")
            _cache_store.clear()
        return True

    # Note: This implementation performs lazy expiration (on access).
    # For high-volume caches or strict memory limits, a background pruning task might be needed.
