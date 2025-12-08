from typing import Any, Sequence
from uuid import UUID
from features.users.domain.entities.user import User as UserEntity
from infrastructure.repositories.base_repository import BaseRepositoryInterface # Use interface
try: from infrastructure.utils.logging_config import logger
except ImportError: import logging; logger = logging.getLogger(__name__)

class ListUsersUseCase:
     # ---> SỬA: Dùng interface cho repo type hint
    def __init__(self, repository: BaseRepositoryInterface[Any, UserEntity]):
        self._repository = repository
    async def execute(self, skip: int = 0, limit: int = 100) -> Sequence[UserEntity]:
        logger.info(f"Executing ListUsersUseCase", extra={"skip": skip, "limit": limit})
        try:
            users = await self._repository.get_all(skip=skip, limit=limit)
            logger.info(f"Found {len(users)} users.", extra={"skip": skip, "limit": limit})
            return users
        except Exception as e: logger.exception("Error retrieving users list."); raise Exception("Could not retrieve users.") from e
