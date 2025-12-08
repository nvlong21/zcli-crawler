from fastapi import APIRouter, Depends, HTTPException, status, Body, Path, Query
from typing import List, Optional, Annotated, Any
from uuid import UUID
from datetime import datetime

# Schemas
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# Domain entity
from features.users.domain.entities.user import User as UserEntity

# Use Cases
from features.users.app.use_cases.create_user import CreateUserUseCase
from features.users.app.use_cases.get_user import GetUserUseCase
from features.users.app.use_cases.list_users import ListUsersUseCase
from features.users.app.use_cases.update_user import UpdateUserUseCase
from features.users.app.use_cases.delete_user import DeleteUserUseCase

# ---> SỬA: Import dependencies đúng
from app.dependencies import UoW, PasswordHasherDep, get_repo # Import get_repo
from app.exceptions import NotFoundError, ConflictError, UnprocessableEntityError, ForbiddenError, BadRequestError

# Auth & Permissions
from infrastructure.auth.jwt import get_token_payload, TokenPayload
from infrastructure.auth.permissions import require_permission

# ---> SỬA: Import repo đúng
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.repositories.base_repository import BaseRepositoryInterface
try: from infrastructure.utils.logging_config import logger
except ImportError: import logging; logger = logging.getLogger(__name__)


# --- API Schemas ---
class UserBaseSchema(BaseModel): # Response schema
    model_config = ConfigDict(from_attributes=True)
    id: UUID; username: str; email: EmailStr; is_active: bool; is_superuser: bool
    roles: List[str] = Field(default_factory=list); created_at: datetime; updated_at: datetime

class UserCreateRequestSchema(BaseModel): # Request for creating
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr; password: str = Field(..., min_length=8)
    is_active: Optional[bool] = None; is_superuser: Optional[bool] = None; roles: Optional[List[str]] = None

class UserUpdateRequestSchema(BaseModel): # Request for updating (PATCH)
    model_config = ConfigDict(extra='ignore')
    username: Optional[str] = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: Optional[EmailStr] = None; is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None; roles: Optional[List[str]] = None

# --- Repository Dependency ---
# ---> SỬA: Dùng get_repo để tạo dependency
UserRepo = Annotated[
    UserRepository, # Hint kiểu cụ thể nếu cần
    Depends(get_repo(UserEntity)) # Lấy provider từ get_repo
]

# --- Permission Helpers ---
AllowAnyAuthenticated = Depends(get_token_payload)
RequireAdmin = Depends(require_permission(required_roles=["admin"]))
RequireSuperuser = Depends(require_permission(required_roles=["superuser"]))

# --- API Router ---
router = APIRouter(prefix="/users", tags=["Users - CRUD"])

# --- Endpoints ---
# ---> SỬA: Đổi tên biến repo thành user_repo cho nhất quán
@router.post("/", response_model=UserBaseSchema, status_code=status.HTTP_201_CREATED, summary="Create User", dependencies=[RequireSuperuser])
async def create_user_endpoint(data: UserCreateRequestSchema, user_repo: UserRepo, uow: UoW, hasher: PasswordHasherDep):
    try: return await CreateUserUseCase(user_repo, uow, hasher).execute(data.model_dump()) # Pass user_repo
    except (ConflictError, UnprocessableEntityError, BadRequestError) as e: raise HTTPException(e.status_code, str(e.detail))
    except Exception as e: logger.exception("API Error create user"); raise HTTPException(500, "Failed create user")

@router.get("/", response_model=List[UserBaseSchema], summary="List Users", dependencies=[RequireAdmin])
async def list_users_endpoint(user_repo: UserRepo, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
    # ListUsersUseCase cần BaseRepo interface, UserRepository implement nó nên OK
    try: return await ListUsersUseCase(user_repo).execute(skip=skip, limit=limit) # Pass user_repo
    except Exception as e: logger.exception("API Error list users"); raise HTTPException(500, "Failed list users")

@router.get("/{user_id}", response_model=UserBaseSchema, summary="Get User by ID", dependencies=[AllowAnyAuthenticated])
async def get_user_endpoint(user_id: UUID, user_repo: UserRepo, current_user_payload: Annotated[TokenPayload, AllowAnyAuthenticated]): # Inject payload để check quyền
    # Example permission: Allow admin or self
    is_self = str(user_id) == current_user_payload.sub
    is_admin_or_super = "admin" in current_user_payload.roles or "superuser" in current_user_payload.roles
    if not is_self and not is_admin_or_super:
        raise ForbiddenError("You do not have permission to view this user.")
    try: return await GetUserUseCase(user_repo).execute(user_id) # Pass user_repo
    except NotFoundError as e: raise HTTPException(status.HTTP_404_NOT_FOUND, str(e.detail))
    except Exception as e: logger.exception("API Error get user"); raise HTTPException(500, "Failed get user")

@router.put("/{user_id}", response_model=UserBaseSchema, summary="Update User", dependencies=[AllowAnyAuthenticated])
async def update_user_endpoint(user_id: UUID, data: UserUpdateRequestSchema, user_repo: UserRepo, uow: UoW, current_user_payload: Annotated[TokenPayload, AllowAnyAuthenticated]):
    # Example permission: Allow admin/superuser or self
    is_self = str(user_id) == current_user_payload.sub
    is_admin_or_super = "admin" in current_user_payload.roles or "superuser" in current_user_payload.roles
    if not is_self and not is_admin_or_super:
        raise ForbiddenError("You do not have permission to update this user.")
    # Prevent non-admins from changing certain fields even if self
    update_payload = data.model_dump(exclude_unset=True)
    if not update_payload: raise HTTPException(status.HTTP_400_BAD_REQUEST, "No update data provided.")
    if not is_admin_or_super:
        update_payload.pop("is_superuser", None) # Only superuser can change superuser status
        update_payload.pop("roles", None) # Only admin/super can change roles (example policy)
        if not is_self: update_payload.pop("is_active", None) # Only admin or self can change active status?

    if not update_payload: raise HTTPException(status.HTTP_400_BAD_REQUEST, "No allowed update fields provided.")

    try: return await UpdateUserUseCase(user_repo, uow).execute(user_id, update_payload) # Pass user_repo
    except NotFoundError as e: raise HTTPException(status.HTTP_404_NOT_FOUND, str(e.detail))
    except (ConflictError, UnprocessableEntityError) as e: raise HTTPException(e.status_code, str(e.detail))
    except Exception as e: logger.exception("API Error update user"); raise HTTPException(500, "Failed update user")

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete User", dependencies=[RequireSuperuser])
async def delete_user_endpoint(user_id: UUID, user_repo: UserRepo, uow: UoW):
    try: await DeleteUserUseCase(user_repo, uow).execute(user_id) # Pass user_repo
    except NotFoundError as e: raise HTTPException(status.HTTP_404_NOT_FOUND, str(e.detail))
    except Exception as e: logger.exception("API Error delete user"); raise HTTPException(500, "Failed delete user")

