from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated, Any
from uuid import UUID

# Use Cases & Dependencies
from features.users.app.use_cases.authenticate_user import AuthenticateUserUseCase
from features.users.app.use_cases.get_user import GetUserUseCase
# ---> SỬA: Import get_repo từ app.dependencies
from app.dependencies import PasswordHasherDep, get_repo, DBSession # Import DBSession nếu cần type hint bên trong provider
from app.exceptions import UnauthorizedError, NotFoundError

# Auth JWT functions & schemas
from infrastructure.auth.jwt import create_access_token, TokenResponse, TokenPayload, get_token_payload
# ---> SỬA: Import UserRepository từ đúng đường dẫn
from infrastructure.repositories.user_repository import UserRepository
from .users_api import UserBaseSchema # Reuse response schema
from features.users.domain.entities.user import User as UserEntity # Import UserEntity
# Import logger
try: from infrastructure.utils.logging_config import logger
except ImportError: import logging; logger = logging.getLogger(__name__)

# --- Repository Dependency ---
# ---> SỬA: Định nghĩa AuthUserRepo dùng get_repo
AuthUserRepo = Annotated[
    UserRepository,
    Depends(get_repo(UserEntity)) # Dùng get_repo từ app.dependencies
]

# --- API Router ---
router = APIRouter(prefix="/auth", tags=["Authentication"])

# --- Endpoints ---
@router.post("/token", response_model=TokenResponse, summary="Login for Access Token")
# ---> SỬA: Inject repo dùng AuthUserRepo
async def login_for_access_token_endpoint(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], repo: AuthUserRepo, hasher: PasswordHasherDep):
    logger.info("Token requested", extra={"username": form_data.username})
    auth_use_case = AuthenticateUserUseCase(user_repository=repo, password_hasher=hasher)
    try:
        user = await auth_use_case.execute(identifier=form_data.username, password=form_data.password)
    except UnauthorizedError as e: raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e.detail), headers={"WWW-Authenticate": "Bearer"})
    except Exception as e: logger.exception("Error during authentication"); raise HTTPException(500, "Authentication error")

    claims = {"roles": user.roles, "is_superuser": user.is_superuser}
    access_token = create_access_token(subject=str(user.id), custom_claims=claims)
    logger.info("Access token generated", extra={"user_id": str(user.id)})
    return TokenResponse(access_token=access_token, token_type="bearer")

@router.get("/me", response_model=UserBaseSchema, summary="Get Current User")
# ---> SỬA: Inject repo dùng AuthUserRepo (có thể dùng chung với UserRepo)
async def read_users_me_endpoint(payload: Annotated[TokenPayload, Depends(get_token_payload)], repo: AuthUserRepo):
    user_id_str = payload.sub
    logger.info("Fetching current user (/me)", extra={"user_id": user_id_str})
    # GetUserUseCase cần BaseRepositoryInterface, repo (UserRepository) là implementation nên OK
    get_use_case = GetUserUseCase(repository=repo)
    try: user_id = UUID(user_id_str); return await get_use_case.execute(user_id)
    except (ValueError, TypeError): logger.warning(f"Invalid UUID format in token sub: {user_id_str}"); raise HTTPException(status.HTTP_404_NOT_FOUND, "Current user not found.")
    except NotFoundError: logger.warning(f"User from token not found: {user_id_str}"); raise HTTPException(status.HTTP_404_NOT_FOUND, "Current user not found.")
    except Exception as e: logger.exception("Error fetching current user"); raise HTTPException(500, "Error retrieving user info.")

