from typing import Dict, Any
from uuid import UUID

from features.users.domain.entities.user import User as UserEntity
# ---> SỬA IMPORT REPO
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.database.models.user_model import User as UserModel
from infrastructure.uow import AbstractUnitOfWork
from app.exceptions import ConflictError, UnprocessableEntityError, BadRequestError
from infrastructure.utils.security import PasswordHasher
try: from infrastructure.utils.logging_config import logger
except ImportError: import logging; logger = logging.getLogger(__name__)

class CreateUserUseCase:
    def __init__(self, user_repository: UserRepository, uow: AbstractUnitOfWork, password_hasher: PasswordHasher):
        self._repository = user_repository; self._uow = uow; self._password_hasher = password_hasher
    async def execute(self, user_data: Dict[str, Any]) -> UserEntity:
        log_extra = {"username": user_data.get("username"), "email": user_data.get("email")}
        logger.info("Executing CreateUserUseCase", extra=log_extra)
        plain_password = user_data.get('password')
        if not plain_password: raise BadRequestError(detail="Password is required.")
        try:
            entity_for_validation = UserEntity(username=user_data["username"], email=user_data["email"], **{k: v for k, v in user_data.items() if k not in ['username', 'email', 'password', 'id']})
        except Exception as e: raise UnprocessableEntityError(detail=f"Invalid user data: {e}") from e
        if await self._repository.get_by_username(entity_for_validation.username): raise ConflictError(f"Username '{entity_for_validation.username}' is taken.")
        if await self._repository.get_by_email(entity_for_validation.email): raise ConflictError(f"Email '{entity_for_validation.email}' is registered.")
        hashed_password = self._password_hasher.get_password_hash(plain_password)
        db_model_data = entity_for_validation.model_dump(exclude={'id', 'created_at', 'updated_at'})
        db_model_data["hashed_password"] = hashed_password
        try:
            async with self._uow:
                new_db_user = UserModel(**db_model_data)
                self._repository._db.add(new_db_user) # Access session directly (or refine repo.add)
                await self._uow.commit()
                await self._repository._db.refresh(new_db_user)
            created_entity = await self._repository._map_model_to_entity(new_db_user)
            if not created_entity: raise Exception("Internal error mapping created user.")
            logger.info("User created successfully", extra={"user_id": str(created_entity.id)})
            return created_entity
        except Exception as e: logger.error(f"Error during user persistence: {e}", exc_info=True); raise Exception("Could not save user.") from e
