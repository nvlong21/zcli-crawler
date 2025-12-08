from abc import ABC, abstractmethod
from typing import Any, Optional
from infrastructure.utils.logging_config import logger

class BaseCache(ABC):
    """Abstract Base Class for cache implementations."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieves an item from the cache."""
        logger.debug(f"Cache GET request for key: {key}")
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Stores an item in the cache."""
        logger.debug(f"Cache SET request for key: {key} (TTL: {ttl})")
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Removes an item from the cache."""
        logger.debug(f"Cache DELETE request for key: {key}")
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Checks if a key exists in the cache."""
        logger.debug(f"Cache EXISTS check for key: {key}")
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Clears the entire cache (use with caution!)."""
        logger.warning("Cache CLEAR request received.")
        pass

    async def ping(self) -> bool:
        """Optional: Checks if the cache backend is reachable."""
        logger.debug(f"Cache PING request for backend: {type(self).__name__}")
        # Default implementation assumes reachable if instance exists
        return True
