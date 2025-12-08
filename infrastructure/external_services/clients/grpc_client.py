import grpc
import grpc.aio # Import the asyncIO API explicitly
from typing import Any, Dict, Optional, Tuple, List, Type
from abc import abstractmethod
import asyncio
import logging

from .base_client import BaseClient, ExternalServiceError
# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for grpc_client.py.")

from app.config import settings # For potential global timeout settings

class BaseGrpcClient(BaseClient):
    """
    Abstract Base Class for gRPC clients using grpc.aio.
    Manages channel and stub creation lazily. Handles channel closure.
    """

    def __init__(
        self,
        service_url: str,
        service_name: str = "gRPC Service",
        default_timeout: Optional[float] = None # Default timeout for calls
        # TODO: Add args for credentials, interceptors, channel options
    ):
        if not service_url:
            raise ValueError("Service URL must be provided for BaseGrpcClient")
        # Remove grpc:// prefix if present, target address for channel
        self.target_address = service_url.replace("grpc://", "")
        self.service_name = service_name
        self.default_timeout = default_timeout

        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[Any] = None # The generated stub instance
        self._channel_lock = asyncio.Lock() # Lock for lazy channel/stub initialization
        self._closed = False # Flag to prevent use after close

        logger.debug(f"Initialized BaseGrpcClient wrapper for {self.service_name} targeting {self.target_address}")

    @abstractmethod
    def _get_stub_class(self) -> Type:
        """Subclasses MUST implement this to return the generated Stub class."""
        raise NotImplementedError

    async def _get_channel(self) -> grpc.aio.Channel:
        """Lazily creates and returns the gRPC channel."""
        if self._closed:
            raise RuntimeError(f"gRPC client for {self.service_name} has been closed.")
        if self._channel is None:
            async with self._channel_lock:
                # Double-check after acquiring lock
                if self._channel is None:
                    logger.info(f"Creating gRPC channel to {self.target_address} for {self.service_name}...")
                    # --- Credentials Logic ---
                    # TODO: Implement secure channel creation based on settings
                    use_tls = getattr(settings, "GRPC_USE_TLS", False) # Example setting
                    if use_tls:
                        logger.warning(f"Secure gRPC channel creation logic not fully implemented for {self.service_name}. Using insecure.")
                        # credentials = grpc.ssl_channel_credentials(...)
                        # self._channel = grpc.aio.secure_channel(self.target_address, credentials, ...)
                        self._channel = grpc.aio.insecure_channel(self.target_address) # Fallback
                    else:
                        logger.warning(f"Creating INSECURE gRPC channel to {self.target_address} for {self.service_name}.")
                        self._channel = grpc.aio.insecure_channel(self.target_address)

                    # TODO: Add interceptors if provided during init
                    # self._channel = grpc.aio.intercept_channel(self._channel, *self.interceptors)
                    logger.info(f"gRPC channel created for {self.service_name}")
        return self._channel

    async def _get_stub(self) -> Any:
        """Lazily creates and returns the gRPC stub instance."""
        if self._stub is None:
             channel = await self._get_channel() # Ensures channel exists
             async with self._channel_lock: # Protect stub creation as well
                 if self._stub is None:
                     stub_class = self._get_stub_class()
                     self._stub = stub_class(channel)
                     logger.debug(f"gRPC stub ({stub_class.__name__}) created for {self.service_name}")
        return self._stub

    def _prepare_metadata(self, headers: Optional[Dict[str, str]] = None) -> Optional[List[Tuple[str, str]]]:
        """Prepares gRPC metadata (list of tuples) from a headers dictionary."""
        if not headers: return None
        return [(k.lower(), str(v)) for k, v in headers.items()]

    async def call(
        self,
        method: str, # Name of the RPC method on the stub
        endpoint: str = "", # Informational, not typically used to route gRPC calls
        data: Optional[Any] = None, # The gRPC request message object
        params: Optional[Dict[str, Any]] = None, # Not used for gRPC
        headers: Optional[Dict[str, str]] = None, # For gRPC metadata
        timeout: Optional[float] = None # Optional request timeout override
    ) -> Any:
        """Makes a gRPC call using the configured stub."""
        if self._closed:
            raise RuntimeError(f"gRPC client for {self.service_name} has been closed.")

        call_timeout = timeout if timeout is not None else self.default_timeout
        log_extra = { "service": self.service_name, "rpc_method": method, "target": self.target_address }

        try:
            stub = await self._get_stub()
            rpc_method_callable = getattr(stub, method, None)

            if not rpc_method_callable or not callable(rpc_method_callable):
                raise AttributeError(f"RPC method '{method}' not found or not callable on {type(stub).__name__}")

            metadata = self._prepare_metadata(headers)
            log_extra["metadata_keys"] = list(headers.keys()) if headers else []
            log_extra["timeout"] = call_timeout if call_timeout is not None else "ClientDefault"
            logger.debug(f"Making gRPC call", extra=log_extra)

            # Make the actual RPC call
            response = await rpc_method_callable(request=data, metadata=metadata, timeout=call_timeout)

            logger.debug(f"gRPC call successful", extra=log_extra)
            return response

        except grpc.aio.AioRpcError as e:
            status_code: grpc.StatusCode = e.code()
            details = e.details() or "No details"
            log_level = logging.WARNING if status_code in (grpc.StatusCode.NOT_FOUND, grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED, grpc.StatusCode.INVALID_ARGUMENT) else logging.ERROR
            log_level(f"gRPC error calling '{method}' on {self.service_name}: Code={status_code.name}, Details='{details}'", extra=log_extra)
            raise ExternalServiceError(
                message=f"gRPC Error: {status_code.name} - {details}", service_name=self.service_name,
                status_code=status_code.name, original_exception=e
            ) from e
        except AttributeError as e:
            logger.error(f"Attribute error preparing gRPC call '{method}': {e}", exc_info=True, extra=log_extra)
            raise ExternalServiceError(
                message=f"Invalid RPC method setup: {e}", service_name=self.service_name,
                original_exception=e
            ) from e
        except Exception as e:
            logger.exception(f"Unexpected error during gRPC call '{method}' to {self.service_name}", extra=log_extra)
            raise ExternalServiceError(
                message="Unexpected communication error", service_name=self.service_name,
                original_exception=e
            ) from e

    async def close(self):
        """Closes the underlying gRPC channel gracefully."""
        if self._closed: return # Already closed
        self._closed = True # Mark as closed immediately

        channel_to_close = None
        async with self._channel_lock: # Ensure no new channel is created while closing
             if self._channel:
                 channel_to_close = self._channel
                 self._channel = None # Clear reference
                 self._stub = None # Clear stub reference

        if channel_to_close:
            logger.info(f"Closing gRPC channel to {self.target_address} for {self.service_name}...")
            try:
                await channel_to_close.close(grace=1.0) # Allow 1 sec for graceful shutdown
                logger.info(f"gRPC channel closed for {self.service_name}.")
            except Exception as e:
                 logger.error(f"Error closing gRPC channel for {self.service_name}: {e}", exc_info=True)
        else:
             logger.debug(f"No active gRPC channel to close for {self.service_name}.")
