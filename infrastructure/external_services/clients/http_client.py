import httpx
from typing import Any, Dict, Optional, Union
from contextlib import asynccontextmanager
import json
import logging

from .base_client import BaseClient, ExternalServiceError
# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for http_client.py.")

from app.config import settings # For potential global timeout settings

# --- Shared HTTPX Client (Recommended for Production) ---
_shared_http_client: Optional[httpx.AsyncClient] = None

async def get_shared_http_client() -> httpx.AsyncClient:
    """Gets or initializes a shared httpx.AsyncClient instance."""
    global _shared_http_client
    if _shared_http_client is None:
         # Configure the shared client (timeouts, limits, etc.)
         timeout = httpx.Timeout(getattr(settings, "HTTP_CLIENT_TIMEOUT", 10.0), connect=5.0)
         limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
         try:
             _shared_http_client = httpx.AsyncClient(timeout=timeout, limits=limits, http2=True, follow_redirects=True)
             logger.info("Initialized shared httpx.AsyncClient.")
             # Optional: Start background task to check health/metrics?
         except Exception as e:
              logger.exception("Failed to initialize shared httpx.AsyncClient.")
              raise RuntimeError("Could not create shared HTTP client") from e
    return _shared_http_client

async def close_shared_http_client():
    """Closes the shared httpx.AsyncClient."""
    global _shared_http_client
    if _shared_http_client:
         logger.info("Closing shared httpx.AsyncClient...")
         try:
             await _shared_http_client.aclose()
             _shared_http_client = None
             logger.info("Shared httpx.AsyncClient closed.")
         except Exception as e:
              logger.exception("Error closing shared httpx.AsyncClient.")

# --- HTTPClient Implementation using Shared Client ---
class HTTPClient(BaseClient):
    """Generic HTTP client implementation using a shared httpx.AsyncClient."""

    def __init__(
        self,
        base_url: str,
        service_name: str = "HTTP Service",
        default_headers: Optional[Dict[str, str]] = None,
        default_timeout: Optional[float] = None # Timeout override for this specific service
    ):
        if not base_url:
            raise ValueError("Base URL must be provided for HTTPClient")
        self.base_url = base_url.rstrip('/')
        self.service_name = service_name
        self.default_headers = default_headers or {}
        self.default_timeout = default_timeout

        logger.debug(f"Initialized HTTPClient wrapper for {self.service_name} at {self.base_url}")

    async def call(
        self,
        method: str,
        endpoint: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None # Per-call timeout override
    ) -> Any:
        """Makes an HTTP call using the shared client."""
        request_url = f"{self.base_url}{endpoint}" # Construct full URL
        final_headers = self.default_headers.copy()
        if headers: final_headers.update(headers)

        payload_kwarg = {}
        if isinstance(data, dict):
            payload_kwarg['json'] = data
            if 'content-type' not in (h.lower() for h in final_headers):
                 final_headers.setdefault('Content-Type', 'application/json')
        elif data is not None:
            payload_kwarg['content'] = data

        # Determine effective timeout: per-call > service default > global default
        call_timeout = timeout if timeout is not None else self.default_timeout
        # If still None, httpx client's default will be used

        log_extra = {
            "service": self.service_name,
            "method": method.upper(),
            "url": request_url,
            "params": params or {},
            "headers": list(final_headers.keys()),
            "timeout": call_timeout if call_timeout is not None else "ClientDefault",
        }
        logger.debug(f"Making HTTP request", extra=log_extra)

        try:
            shared_client = await get_shared_http_client()
            response = await shared_client.request(
                method=method.upper(),
                url=request_url,
                params=params,
                headers=final_headers,
                timeout=call_timeout, # Pass specific timeout if provided
                **payload_kwarg
            )

            logger.debug(f"HTTP response received", extra={**log_extra, "status_code": response.status_code})
            response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx

            if response.status_code == 204: return None
            try:
                return response.json()
            except json.JSONDecodeError:
                logger.warning(f"Non-JSON response from {self.service_name}: {response.status_code}", extra=log_extra)
                return response.text

        except httpx.HTTPStatusError as e:
            error_detail = f"HTTP Error: {e.response.status_code}."
            try: response_text = e.response.text[:500]; error_detail += f" Response: '{response_text}'"
            except Exception: pass
            logger.warning(f"HTTP error calling {self.service_name}: {e.response.status_code}", extra=log_extra)
            raise ExternalServiceError(
                message=error_detail, service_name=self.service_name,
                status_code=e.response.status_code, original_exception=e
            ) from e
        except httpx.RequestError as e: # Covers timeouts, connection errors etc.
            error_message = f"Request Error: {type(e).__name__} calling {e.request.url}"
            logger.error(error_message, extra=log_extra)
            raise ExternalServiceError(
                message=f"Request Error: {type(e).__name__}", service_name=self.service_name,
                original_exception=e
            ) from e
        except Exception as e:
             logger.exception(f"Unexpected error calling {self.service_name} at {request_url}", extra=log_extra)
             raise ExternalServiceError(
                 message="Unexpected communication error", service_name=self.service_name,
                 original_exception=e
             ) from e

    # --- Convenience Methods ---
    async def get(self, endpoint: str, params: Optional[Dict] = None, headers: Optional[Dict] = None, timeout: Optional[float] = None) -> Any:
        return await self.call("GET", endpoint, params=params, headers=headers, timeout=timeout)
    # ... POST, PUT, DELETE methods remain the same ...
    async def post(self, endpoint: str, data: Any, headers: Optional[Dict] = None, timeout: Optional[float] = None) -> Any:
        return await self.call("POST", endpoint, data=data, headers=headers, timeout=timeout)

    async def put(self, endpoint: str, data: Any, headers: Optional[Dict] = None, timeout: Optional[float] = None) -> Any:
        return await self.call("PUT", endpoint, data=data, headers=headers, timeout=timeout)

    async def delete(self, endpoint: str, headers: Optional[Dict] = None, timeout: Optional[float] = None) -> Any:
        return await self.call("DELETE", endpoint, headers=headers, timeout=timeout)

    # Override close method - we don't close the shared client here
    async def close(self):
        logger.debug(f"Close called on HTTPClient wrapper for {self.service_name}, but shared client is managed globally.")
        pass # Do not close the shared client instance here
