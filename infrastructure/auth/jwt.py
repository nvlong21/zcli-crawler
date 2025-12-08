from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError, Field
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated, List, Union, Any, Dict # Thêm Dict
from uuid import UUID
import logging
import sqlalchemy as sa

from app.config import settings
# Use configured logger if available, otherwise basic logger
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for jwt.py.")

# OAuth2 scheme definition
# tokenUrl should point to the API endpoint that issues the token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token") # Use API_V1_STR

# --- Constants ---
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
# Make token expiry configurable via settings, with a default
ACCESS_TOKEN_EXPIRE_MINUTES = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30)

# --- Token Schemas ---
class TokenPayload(BaseModel):
    """Schema for data encoded within the JWT."""
    # 'sub' (subject) typically holds the user identifier (UUID, int ID, username)
    sub: str # Subject MUST be present (as per JWT standard)
    exp: Optional[int] = None # Expiration time (Unix timestamp), automatically verified by jwt.decode
    iat: Optional[int] = None # Issued at timestamp (Unix timestamp)
    # Custom claims (add application-specific data here)
    roles: List[str] = Field(default_factory=list) # Example: User roles
    # Example: user_type: Optional[str] = None
    # Example: is_superuser: Optional[bool] = False # Thêm claim này nếu cần check superuser từ token

class TokenResponse(BaseModel):
    """Schema for the token response sent back to the client."""
    access_token: str
    token_type: str = "bearer"


# --- Token Creation ---
def create_access_token(
    subject: Union[str, UUID, int], # User identifier
    expires_delta: Optional[timedelta] = None,
    custom_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Creates a JWT access token.

    Args:
        subject: The unique identifier of the user (e.g., user ID as string/UUID/int).
        expires_delta: Optional timedelta object for custom expiration. Uses default if None.
        custom_claims: Optional dictionary containing custom data to include in the payload (e.g., roles).

    Returns:
        The encoded JWT access token string.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    issued_at = datetime.now(timezone.utc)

    # Base payload with standard claims
    to_encode: Dict[str, Any] = {
        "sub": str(subject), # Ensure subject is stringified for JWT standard
        "exp": expire,
        "iat": issued_at,
    }

    # Add custom claims if provided
    if custom_claims:
        # Ensure custom claims don't overwrite standard ones unintentionally
        standard_claims = {"sub", "exp", "iat", "jti", "nbf", "aud", "iss"}
        safe_custom_claims = {k: v for k, v in custom_claims.items() if k not in standard_claims}
        to_encode.update(safe_custom_claims)
        # Warn if standard claims were attempted to be overwritten
        overwritten = set(custom_claims.keys()) & standard_claims
        if overwritten:
             logger.warning(f"Attempted to overwrite standard JWT claims via custom_claims: {overwritten}. These were ignored.")


    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.debug(f"Created access token for subject: {subject}") # Avoid logging expiry/claims unless debugging heavily
        return encoded_jwt
    except Exception as e:
         logger.exception(f"Error encoding JWT: {e}")
         # Raise an internal server error or specific encoding error
         raise RuntimeError("Could not create access token due to encoding error.") from e


# --- Token Decoding and Validation ---
def decode_access_token(token: str) -> TokenPayload: # Return TokenPayload directly, raise exception on failure
    """
    Decodes a JWT access token, validates its signature, expiration, and payload structure.

    Args:
        token: The encoded JWT string.

    Returns:
        TokenPayload instance if the token is valid and conforms to the schema.

    Raises:
        HTTPException(401): If token is invalid, malformed, expired, or payload validation fails.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # jwt.decode handles signature verification and expiration check (exp claim)
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_aud": False} # Set to True if using audience (aud) claim
        )
        # Validate the decoded payload against the TokenPayload schema
        # This ensures required fields like 'sub' are present and types are correct.
        token_data = TokenPayload.model_validate(payload) # Pydantic v2 validation

        logger.debug(f"Token decoded successfully for subject: {token_data.sub}")
        return token_data

    except jwt.ExpiredSignatureError:
        logger.warning("Token validation failed: Expired signature")
        raise credentials_exception # Re-raise as 401
    except jwt.JWTClaimsError as e:
         logger.warning(f"Token validation failed: Invalid claims - {e}")
         raise credentials_exception
    except jwt.JWTError as e: # Catches other JWT errors like invalid signature, malformed token
        logger.warning(f"Token validation failed: JWTError - {e}")
        raise credentials_exception
    except ValidationError as e:
        # Payload structure is invalid according to TokenPayload schema
        logger.error(f"Token payload validation failed: {e.errors()}")
        raise credentials_exception
    except Exception as e: # Catch unexpected errors during decoding/validation
        logger.exception(f"Unexpected error decoding or validating token: {e}")
        raise credentials_exception


# --- FastAPI Dependencies ---

async def get_token_payload(
    token: Annotated[str, Depends(oauth2_scheme)]
) -> TokenPayload:
    """
    FastAPI dependency to get the validated token payload from the Authorization header.
    Handles token decoding and raises HTTPException(401) if invalid or expired.
    """
    # decode_access_token now raises HTTPException on failure
    payload = decode_access_token(token)
    return payload

# --- Dependency to get the full User object (Example Placeholder) ---
# Move this to features/users/dependencies.py or keep here if tightly coupled.

# from features.users.domain.entities.user import User as UserEntity
# from app.dependencies import DBSession, get_repository # Needs get_repo from app/dependencies
# from features.users.infrastructure.repositories.user_repository import UserRepository # Specific repo often needed
# from uuid import UUID
# from typing import Callable # Add Callable

# def get_user_repo_for_auth(session: DBSession) -> UserRepository:
#      repo_interface = get_repository(UserEntity, session)
#      if not isinstance(repo_interface, UserRepository):
#           raise TypeError(f"Auth requires UserRepository, got {type(repo_interface).__name__}")
#      return repo_interface

# UserRepoForAuth = Annotated[UserRepository, Depends(get_user_repo_for_auth)]

# async def get_current_user(
#     payload: Annotated[TokenPayload, Depends(get_token_payload)],
#     user_repo: UserRepoForAuth,
# ) -> UserEntity:
#     user_identifier = payload.sub
#     logger.debug(f"Attempting to fetch current user for sub: {user_identifier}")
#     try:
#         user_id = UUID(user_identifier)
#         user = await user_repo.get_by_id(user_id) # Use specific repo method if needed
#     except (ValueError, TypeError):
#          logger.error(f"Token subject '{user_identifier}' is not a valid UUID.")
#          raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user identifier in token.")
#     except Exception as e:
#          logger.exception(f"Error fetching user {user_identifier} from repository: {e}")
#          raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving user information.")
#
#     if user is None:
#         logger.warning(f"User not found for token subject: {user_identifier}")
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User associated with token not found.")
#
#     logger.debug(f"Current user resolved: {user.username} (ID: {user.id})")
#     return user

