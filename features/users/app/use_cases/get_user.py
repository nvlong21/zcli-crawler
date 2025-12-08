from typing import Any, Optional
from uuid import UUID
from features.users.domain.entities.user import User as UserEntity
from infrastructure.repositories.base_repository import BaseRepositoryInterface # Use interface
from app.exceptions import NotFoundError
try: from infrastructure.utils.logging_config import logger
except ImportError: import logging; logger = logging.getLogger(__name__)

class GetUserUseCase:
    # ---> SỬA: Dùng interface cho repo type hint
    def __init__(self, repository: BaseRepositoryInterface[Any, UserEntity]):
        self._repository = repository
    async def execute(self, user_id: UUID) -> UserEntity:
        logger.info(f"Executing GetUserUseCase for user_id: {user_id}")
        user = await self._repository.get_by_id(user_id)
        if not user: logger.warning(f"User not found", extra={"user_id": str(user_id)}); raise NotFoundError(f"User {user_id} not found.")
        logger.info(f"User found successfully", extra={"user_id": str(user_id)})
        return user
