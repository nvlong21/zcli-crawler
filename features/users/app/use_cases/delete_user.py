from typing import Any
from uuid import UUID
from infrastructure.repositories.base_repository import BaseRepositoryInterface # Use interface
from infrastructure.uow import AbstractUnitOfWork
from app.exceptions import NotFoundError
try: from infrastructure.utils.logging_config import logger
except ImportError: import logging; logger = logging.getLogger(__name__)

class DeleteUserUseCase:
     # ---> SỬA: Dùng interface cho repo type hint
    def __init__(self, repository: BaseRepositoryInterface[Any, Any], uow: AbstractUnitOfWork):
        self._repository = repository; self._uow = uow
    async def execute(self, user_id: UUID) -> bool:
        log_extra = {"user_id": str(user_id)}
        logger.info(f"Executing DeleteUserUseCase", extra=log_extra)
        try:
             async with self._uow:
                 deleted = await self._repository.delete(user_id)
                 if not deleted: logger.warning(f"User not found for deletion", extra=log_extra); raise NotFoundError("User not found")
                 await self._uow.commit()
             logger.info(f"User deleted successfully", extra=log_extra)
             return True
        except NotFoundError: raise
        except Exception as e: logger.error(f"Error deleting user {user_id}: {e}", exc_info=True); raise Exception("Could not delete user.") from e
