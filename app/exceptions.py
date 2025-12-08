from fastapi import HTTPException, status
from typing import Any, Optional, Dict # Added Optional, Dict

# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for exceptions.py.")


# Define custom application exceptions inheriting from FastAPI's HTTPException.
# This allows them to be caught by standard FastAPI error handling or specific handlers.

class BaseAppException(HTTPException):
    """Base class for custom application exceptions for consistent logging."""
    def __init__(self, status_code: int, detail: Any = None, headers: Optional[Dict[str, str]] = None):
        super().__init__(status_code=status_code, detail=detail or "Application error", headers=headers)
        # Log the creation of the exception - adjust level as needed
        # logger.debug(f"Raised {self.__class__.__name__}: Status={status_code}, Detail='{detail}'")

class NotFoundError(BaseAppException):
    """Resource not found (HTTP 404)."""
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class BadRequestError(BaseAppException):
    """Client provided invalid data or made a bad request (HTTP 400)."""
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

class UnauthorizedError(BaseAppException):
    """Authentication required or failed (HTTP 401)."""
    def __init__(self, detail: str = "Not authorized", headers: Optional[Dict[str, str]] = None):
        # Ensure WWW-Authenticate header for 401 unless overridden
        auth_header = {"WWW-Authenticate": "Bearer"}
        if headers:
            auth_header.update(headers)
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=auth_header,
        )

class ForbiddenError(BaseAppException):
    """Authenticated user lacks permission for the action (HTTP 403)."""
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

class ConflictError(BaseAppException):
    """Resource conflict, e.g., duplicate item already exists (HTTP 409)."""
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)

class UnprocessableEntityError(BaseAppException):
    """Input data has correct format but fails business validation rules (HTTP 422)."""
    def __init__(self, detail: Any = "Unprocessable entity"):
        # Can accept detailed error structures (e.g., list of dicts from Pydantic)
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

class ExternalServiceError(BaseAppException):
    """Error communicating with an external service dependency (HTTP 503)."""
    def __init__(self, service_name: str = "External service", detail: Optional[str] = None):
        msg = detail or f"{service_name} unavailable or encountered an error."
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=msg)

class InternalServerError(BaseAppException):
    """Generic unexpected server error (HTTP 500)."""
    def __init__(self, detail: str = "Internal server error"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)

# You can define more specific exceptions inheriting from these as needed.
# Example: class UserNotFoundError(NotFoundError): ...
