from typing import Dict, Any
from uuid import UUID
import logging

# --- Domain Layer Imports ---
from features.orders.domain.entities.orders import Uorders
# Optional: Import domain services if needed by the use case
# from features.orders.domain.services.orders_service import UordersDomainService

# --- Infrastructure Abstractions ---
# Use AbstractUnitOfWork and BaseRepositoryInterface for dependency inversion
from infrastructure.uow import AbstractUnitOfWork
from infrastructure.repositories.base_repository import BaseRepositoryInterface, PKType # Import PKType

# --- Application Specific Imports ---
from app.exceptions import ConflictError, UnprocessableEntityError # App-level exceptions
# Use configured logger if available
try: from infrastructure.utils.logging_config import logger
except ImportError: logger = logging.getLogger(__name__)


class CreateUordersUseCase:
    """
    Use Case for creating a new Uorders.
    Orchestrates domain logic and infrastructure interactions (repository, UoW).
    Receives input data (DTO), validates, interacts with domain, persists changes.
    """
    def __init__(
        self,
        # Type hint with the specific Domain Entity and its PK type (e.g., UUID)
        repository: BaseRepositoryInterface[Any, Uorders], # PKType removed from Base Interface ref
        uow: AbstractUnitOfWork,
        # Optional: Inject domain services if needed
        # domain_service: UordersDomainService,
    ):
        self._repository = repository
        self._uow = uow
        # self._domain_service = domain_service # Store injected service
        logger.debug(f"Initialized CreateUordersUseCase")

    async def execute(self, data: Dict[str, Any]) -> Uorders:
        """
        Executes the use case to create a orders.

        Args:
            data: Dictionary containing data for the new orders (e.g., from API schema).

        Returns:
            The created Uorders domain entity, potentially updated with DB defaults.

        Raises:
            UnprocessableEntityError: If input data fails domain validation.
            ConflictError: If a business rule conflict occurs (e.g., duplicate name).
            Exception: For unexpected errors during persistence or domain logic.
        """
        log_extra = {"feature": "orders", "data_keys": list(data.keys())}
        logger.info(f"Executing CreateUordersUseCase", extra=log_extra)

        # 1. Validate Input & Create Domain Entity
        try:
            # Pydantic model handles initial validation.
            # Ensure ID generation strategy aligns (client vs DB). default_factory implies client-side.
            new_entity = Uorders(**data)
            logger.debug(f"Domain entity for orders created: {new_entity.id}", extra=log_extra)
        except Exception as e: # Catch Pydantic ValidationError, etc.
            logger.warning(f"Invalid data for creating orders: {e}", extra=log_extra)
            raise UnprocessableEntityError(detail=f"Invalid data: {e}") from e

        # 2. Check Business Rule Conflicts (Example: Unique Name Check)
        # This usually requires a specific repository method.
        # If using only BaseRepositoryInterface, this check might need to be less specific
        # or the repository type hint in __init__ needs to be more concrete.
        # Example (assumes find_by_name exists or can be added to a specific interface):
        # try:
        #      existing = await self._repository.find_by_name(new_entity.name) # type: ignore
        #      if existing:
        #          msg = f"Uorders with name '{new_entity.name}' already exists."
        #          logger.warning(msg, extra=log_extra)
        #          raise ConflictError(msg)
        # except AttributeError:
        #      logger.debug("Skipping unique name check (find_by_name not available on repo interface).")
        # except Exception as e:
        #      logger.error(f"Error checking uniqueness for orders '{new_entity.name}': {e}", extra=log_extra)
        #      raise # Re-raise unexpected repo errors

        # 3. Persist using Unit of Work
        try:
            async with self._uow: # Handles transaction begin/commit/rollback
                created_entity = await self._repository.add(new_entity)
                # Optionally: Dispatch domain events gathered from the entity
                # events = created_entity.pull_domain_events()
                # await self._event_publisher.publish(events) # Requires event publisher dependency
                await self._uow.commit() # Commit changes

            logger.info(f"Uorders created successfully.", extra={**log_extra, "entity_id": str(created_entity.id)})
            return created_entity
        except Exception as e:
            logger.error(f"Persistence error creating orders: {e}", exc_info=True, extra=log_extra)
            # UoW context manager handles rollback on exception
            raise Exception("Could not save the orders due to a persistence error.") from e
