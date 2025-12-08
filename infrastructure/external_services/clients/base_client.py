from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, List, Tuple

# --- Custom Exception for External Services ---
class ExternalServiceError(Exception):
    """Custom exception for errors during external service communication."""
    def __init__(
        self,
        message: str,
        service_name: str,
        status_code: Optional[Union[int, str]] = None, # Can be HTTP status or gRPC code name
        original_exception: Optional[Exception] = None
    ):
        self.service_name = service_name
        self.status_code = status_code
        self.original_exception = original_exception
        # Construct a detailed error message
        full_message = f"[{service_name}] {message}"
        if status_code:
            full_message += f" (Status: {status_code})"
        if original_exception:
            full_message += f" | Original Error: {type(original_exception).__name__}"
        super().__init__(full_message)

# --- Base Client Abstract Class ---
class BaseClient(ABC):
    """Abstract Base Class for external service clients."""

    @abstractmethod
    async def call(
        self,
        method: str, # e.g., HTTP verb ('GET', 'POST') or RPC method name ('SendEmail')
        endpoint: str, # URL path for HTTP, often empty or informational for RPC
        data: Optional[Any] = None, # Request payload (dict for JSON, bytes, gRPC message obj)
        params: Optional[Dict[str, Any]] = None, # URL query parameters (HTTP)
        headers: Optional[Dict[str, str]] = None, # Request headers (HTTP) or metadata (gRPC)
        timeout: Optional[float] = None # Request timeout in seconds
    ) -> Any: # Return type depends on the service (dict, object, status bool, etc.)
        """
        Abstract method to make a call to the external service.
        Subclasses must implement the specific protocol logic (HTTP, gRPC, etc.).
        """
        raise NotImplementedError("Subclasses must implement the 'call' method.")

    async def __aenter__(self):
        # Optional: Perform setup when entering context
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Perform cleanup (e.g., close connections)
        await self.close()

    async def close(self):
        """Optional method to close connections or clean up resources."""
        pass # Default implementation does nothing
