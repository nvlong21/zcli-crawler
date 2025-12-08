import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from typing import Optional, Callable, Set, Dict # Thêm Set, Dict
import logging
import contextvars # For managing request context across async tasks

# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for middleware.")

# --- Context Variable for Request ID ---
request_id_contextvar = contextvars.ContextVar[Optional[str]]("request_id", default=None)

def get_request_id() -> Optional[str]:
    """Helper function to retrieve the current request ID from context."""
    return request_id_contextvar.get()

# --- Logging Middleware ---
class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log incoming requests, outgoing responses, and processing time.
    Injects a unique request ID into logs and request state.
    """
    def __init__(
        self,
        app: ASGIApp,
        exclude_headers: Optional[Set[str]] = None # Use set for faster lookup
    ):
        super().__init__(app)
        # Default sensitive headers to exclude (lowercase)
        default_exclude = {'authorization', 'cookie', 'x-api-key', 'secret', 'proxy-authorization'}
        self.exclude_headers = default_exclude.union(
            {h.lower() for h in exclude_headers} if exclude_headers else set()
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Generate Request ID and Set Context
        request_id = str(uuid.uuid4())
        request_id_token = request_id_contextvar.set(request_id)
        request.state.request_id = request_id # Make accessible in endpoint via request.state

        # 2. Log Request Start
        start_time = time.monotonic()
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else "unknown"

        headers_to_log: Dict[str, str] = {
            k: "[REDACTED]" if k.lower() in self.exclude_headers else v
            for k, v in request.headers.items()
        }

        log_extra_request = {
            "request_id": request_id, # Added for direct access if filter not used
            "http.request.id": request_id,
            "http.request.method": request.method,
            "http.request.url": str(request.url),
            "http.request.headers": headers_to_log,
            "network.client.ip": client_host,
            "network.client.port": client_port,
        }
        logger.info(f"--> {request.method} {request.url.path}", extra=log_extra_request)

        # 3. Process Request
        response = None
        status_code = 500 # Default status code for unexpected errors
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
             # Log unhandled exceptions here, before they potentially get caught by FastAPI handlers
             # This ensures exceptions during middleware processing itself are logged
             log_extra_exception = {**log_extra_request, "exception_type": type(e).__name__}
             logger.exception("Unhandled exception during middleware/endpoint processing",
                              exc_info=e, extra=log_extra_exception)
             # Re-raise so FastAPI's exception handling takes over to return proper response
             raise e
        finally:
            # 4. Log Response End
            process_time = (time.monotonic() - start_time) * 1000 # Milliseconds

            log_extra_response = {
                "request_id": request_id,
                "http.request.id": request_id,
                "http.response.status_code": status_code,
                "duration_ms": round(process_time, 2),
            }
            if response:
                 resp_headers_to_log: Dict[str, str] = {
                     k: "[REDACTED]" if k.lower() in self.exclude_headers else v
                     for k, v in response.headers.items()
                 }
                 log_extra_response["http.response.headers"] = resp_headers_to_log

            log_level = logging.WARNING if 400 <= status_code < 500 else logging.ERROR if status_code >= 500 else logging.INFO
            logger.log(log_level, f"<-- {status_code} ({request.method} {request.url.path}) [{process_time:.2f}ms]", extra=log_extra_response)

            # 5. Reset ContextVar
            request_id_contextvar.reset(request_id_token)

        return response

# --- Add Request ID to Log Records (Optional - via Filter) ---
class RequestIdLogFilter(logging.Filter):
    """Logging filter to inject the request ID from contextvar into log records."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_contextvar.get(None) # type: ignore
        return True

# Apply Filter (in logging_config.py):
# logger_instance = logging.getLogger(...)
# logger_instance.addFilter(RequestIdLogFilter())
# Ensure '%(request_id)s' is in your log formatter string.
