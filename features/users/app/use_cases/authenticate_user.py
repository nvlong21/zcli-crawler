from typing import Optional
from features.users.domain.entities.user import User as UserEntity
# ---> SỬA IMPORT REPO
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.utils.security import PasswordHasher
from app.exceptions import UnauthorizedError
try: from infrastructure.utils.logging_config import logger
except ImportError: import logging; logger = logging.getLogger(__name__)

class AuthenticateUserUseCase:
    def __init__(self, user_repository: UserRepository, password_hasher: PasswordHasher):
        self._user_repository = user_repository; self._password_hasher = password_hasher
    async def execute(self, *, identifier: str, password: str) -> UserEntity:
        log_extra = {"identifier": identifier}
        logger.info("Executing AuthenticateUserUseCase", extra=log_extra)
        # Use specific repo methods
        db_user = await self._user_repository.get_db_user_by_email(identifier) or await self._user_repository.get_db_user_by_username(identifier)
        if not db_user: logger.warning("Auth failed: User not found", extra=log_extra); raise UnauthorizedError("Incorrect username or password")
        if not self._password_hasher.verify_password(password, db_user.hashed_password): logger.warning("Auth failed: Invalid password", extra={"user_id": str(db_user.id)}); raise UnauthorizedError("Incorrect username or password")
        if not db_user.is_active: logger.warning("Auth failed: User inactive", extra={"user_id": str(db_user.id)}); raise UnauthorizedError("User account is inactive.")
        # Map to entity for return
        authenticated_entity = await self._user_repository._map_model_to_entity(db_user) # Should be self._user_repository
        if not authenticated_entity: logger.error("Failed map authenticated user", extra={"user_id": str(db_user.id)}); raise Exception("Internal auth error.")
        logger.info("User authenticated successfully", extra={"user_id": str(db_user.id)})
        return authenticated_entity
