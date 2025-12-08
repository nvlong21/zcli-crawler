from fastapi import APIRouter, Depends, HTTPException, status, Body, Path, Query
from typing import List, Optional, Annotated, Any
from uuid import UUID
from datetime import datetime # For response model timestamps

# --- API Schemas ---
from pydantic import BaseModel, Field, ConfigDict

# --- Domain Entity ---
# Used for type hinting the final response after mapping from use case result
from features.orders.domain.entities.orders import Uorders as UordersEntity

# --- Use Cases ---
# Import the specific use cases this API endpoint will orchestrate
from features.orders.app.use_cases.create_orders import CreateUordersUseCase
# Example placeholders for other use cases:
# from features.orders.app.use_cases.get_orders import GetUordersUseCase
# from features.orders.app.use_cases.list_orderss import ListUorderssUseCase
# from features.orders.app.use_cases.update_orders import UpdateUordersUseCase
# from features.orders.app.use_cases.delete_orders import DeleteUordersUseCase

# --- Common Dependencies & Exceptions ---
# Import UoW, Session provider (DBSession), Repo factory (get_repo)
from app.dependencies import UoW, DBSession, get_repo
# Import custom application exceptions to map use case errors to HTTP responses
from app.exceptions import NotFoundError, ConflictError, UnprocessableEntityError, ForbiddenError, BadRequestError
# Import configured logger
try: from infrastructure.utils.logging_config import logger
except ImportError: import logging; logger = logging.getLogger(__name__)

# --- Auth Dependencies (Optional) ---
# Import necessary auth dependencies (e.g., get token payload, permission checks)
# from app.dependencies import Authenticated # Example: Gets TokenPayload
# from infrastructure.auth.permissions import is_admin # Example predefined permission check

# --- Infrastructure Interfaces (for type hinting) ---
# Use the base interface for the repository dependency
from infrastructure.repositories.base_repository import BaseRepositoryInterface
# Import DB Model only if needed for explicit type hinting of the repo interface
# from infrastructure.database.models.orders_model import Uorders as UordersModel


# --- API Schemas specific to this Feature ---

class UordersBaseSchema(BaseModel):
    """Base schema for orders data."""
    model_config = ConfigDict(extra='forbid') # Prevent unexpected fields

    name: str = Field(..., min_length=1, max_length=100, examples=["Example Uorders"])
    description: Optional[str] = Field(None, examples=["An optional description."])

class UordersCreateSchema(UordersBaseSchema):
    """Schema for data needed to create a new orders."""
    pass # Inherits fields from base

class UordersUpdateSchema(BaseModel):
     """Schema for data allowed when updating a orders (PATCH style)."""
     model_config = ConfigDict(extra='forbid')
     name: Optional[str] = Field(None, min_length=1, max_length=100, examples=["Updated Name"])
     description: Optional[str] = Field(None, examples=["Updated description"])
     # Add other updatable fields here

class UordersResponseSchema(UordersBaseSchema):
    """Schema for the orders data returned by the API."""
    model_config = ConfigDict(from_attributes=True) # Enable ORM mode

    id: UUID
    created_at: datetime
    updated_at: datetime
    # Add other fields from UordersEntity as needed


# --- Repository Dependency Provider ---
# Defines how to inject the repository for this feature using the common factory
# Type hint uses the Base Interface and the specific Domain Entity
# PK type is assumed to be UUID here, adjust if different
UordersRepo = Annotated[
    BaseRepositoryInterface[Any, UordersEntity], # Use Any for ModelType if not explicitly needed
    Depends(get_repo(UordersEntity))
]

# --- API Router ---
router = APIRouter(
    prefix="/orders", # Base path for all routes in this file
    tags=["Uorders"] # Grouping tag in OpenAPI docs
    # dependencies=[Depends(global_dependency)] # Add router-level dependencies if needed
)


# --- API Endpoints ---

@router.post(
    "/",
    response_model=UordersResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create Uorders",
    description="Create a new orders resource.",
    # --- Security ---
    # dependencies=[Depends(is_admin)], # Example: Require admin role
)
async def create_orders_endpoint(
    # --- Inject Dependencies needed by the Use Case ---
    repo: UordersRepo, # Inject the repository using Annotated type
    uow: UoW, # Inject the Unit of Work
    # token_payload: Authenticated, # Example: Inject authenticated user payload if needed
     # Request body parsed into the CreateSchema
    data: UordersCreateSchema = Body(...),
):
    """API endpoint to handle the creation of a orders."""
    try:
        # Instantiate the use case, injecting its dependencies
        use_case = CreateUordersUseCase(repository=repo, uow=uow)
        # Execute the use case with validated data from the request body
        created_entity = await use_case.execute(data.model_dump())
        # FastAPI automatically converts the returned entity to the response_model schema
        return created_entity
    except (ConflictError, UnprocessableEntityError, BadRequestError) as e:
        # Map known application errors to HTTP exceptions
        raise HTTPException(status_code=e.status_code, detail=str(e.detail))
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e.detail))
    except Exception as e:
        # Catch unexpected errors from the use case or persistence layer
        logger.exception(f"API Error: Failed to create orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the orders."
        )

# --- Placeholder Endpoints for other CRUD operations ---

# GET /orders/{ordersid}
# @router.get("/{ordersid}", response_model=UordersResponseSchema, ...)

# GET /orders/
# @router.get("/", response_model=List[UordersResponseSchema], ...)

# PUT or PATCH /orders/{ordersid}
# @router.patch("/{ordersid}", response_model=UordersResponseSchema, ...)

# DELETE /orders/{ordersid}
# @router.delete("/{ordersid}", status_code=status.HTTP_204_NO_CONTENT, ...)

