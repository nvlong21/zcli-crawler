from typing import Dict, Any, Optional
from uuid import UUID
from features.users.domain.entities.user import User as UserEntity
# ---> SỬA IMPORT REPO
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.uow import AbstractUnitOfWork
from app.exceptions import NotFoundError, ConflictError, UnprocessableEntityError
try: from infrastructure.utils.logging_config import logger
except ImportError: import logging; logger = logging.getLogger(__name__)

class UpdateUserUseCase:
    # ---> SỬA: Dùng repo cụ thể nếu cần check uniqueness
    def __init__(self, user_repository: UserRepository, uow: AbstractUnitOfWork):
        self._repository = user_repository; self._uow = uow
    async def execute(self, user_id: UUID, update_data: Dict[str, Any]) -> UserEntity:
        log_extra = {"user_id": str(user_id), "update_keys": list(update_data.keys())}
        logger.info(f"Executing UpdateUserUseCase", extra=log_extra)
        update_data.pop('id', None); update_data.pop('hashed_password', None); update_data.pop('created_at', None)
        existing_entity = await self._repository.get_by_id(user_id)
        if not existing_entity: raise NotFoundError("User not found")
        # Check conflicts
        new_username = update_data.get("username"); new_email = update_data.get("email")
        if new_username and new_username != existing_entity.username:
            # Check using specific repo method
            conflicting_user_by_name = await self._repository.get_by_username(new_username)
            if conflicting_user_by_name and conflicting_user_by_name.id != user_id: raise ConflictError(f"Username '{new_username}' is taken.")
        if new_email and new_email != existing_entity.email:
            # Check using specific repo method
            conflicting_user_by_email = await self._repository.get_by_email(new_email)
            if conflicting_user_by_email and conflicting_user_by_email.id != user_id: raise ConflictError(f"Email '{new_email}' is registered.")
        # Apply updates & Validate
        updated_entity_data = existing_entity.model_dump(); updated_entity_data.update(update_data)
        try: updated_entity = UserEntity(**updated_entity_data)
        except Exception as e: raise UnprocessableEntityError(f"Invalid update data: {e}") from e
        # Persist
        try:
            async with self._uow:
                result_entity = await self._repository.update(updated_entity)
                if result_entity is None: raise NotFoundError("User not found during update.")
                await self._uow.commit()
            logger.info(f"User updated successfully", extra=log_extra)
            return result_entity
        except Exception as e: logger.error(f"Error updating user {user_id}: {e}", exc_info=True); raise Exception("Could not update user.") from e
