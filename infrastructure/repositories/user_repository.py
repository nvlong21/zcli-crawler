from typing import Optional, Type, Sequence, Any
from uuid import UUID

# Correct import path for domain entity
from features.users.domain.entities.user import User as UserEntity
from infrastructure.database.models.user_model import User as UserModel
from infrastructure.repositories.base_repository import BaseRepository # Correct import path
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
try: from infrastructure.utils.logging_config import logger
except ImportError: import logging; logger = logging.getLogger(__name__)

class UserRepository(BaseRepository[UserModel, UserEntity]): # Removed PKType
    @property
    def model_class(self) -> Type[UserModel]: return UserModel

    @property
    def entity_class(self) -> Type[UserEntity]:
        return UserEntity

    async def get_by_email(self, email: str) -> Optional[UserEntity]:
        logger.debug(f"Getting user by email: {email}")
        stmt = select(self.model_class).where(self.model_class.email.ilike(email))
        model = await self._execute_and_get_first(stmt)
        return await self._map_model_to_entity(model)

    async def get_by_username(self, username: str) -> Optional[UserEntity]:
        logger.debug(f"Getting user by username: {username}")
        stmt = select(self.model_class).where(self.model_class.username == username)
        model = await self._execute_and_get_first(stmt)
        return await self._map_model_to_entity(model)

    async def get_db_user_by_email(self, email: str) -> Optional[UserModel]:
        logger.debug(f"Getting DB user model by email: {email}")
        stmt = select(self.model_class).where(self.model_class.email.ilike(email))
        return await self._execute_and_get_first(stmt)

    async def get_db_user_by_username(self, username: str) -> Optional[UserModel]:
         logger.debug(f"Getting DB user model by username: {username}")
         stmt = select(self.model_class).where(self.model_class.username == username)
         return await self._execute_and_get_first(stmt)

    async def _execute_and_get_first(self, stmt) -> Optional[UserModel]:
         # Helper method assumed from previous context
         model = None
         if self._is_async:
             result = await self._db.execute(stmt) # type: ignore
             model = result.scalars().first()
         else:
             model = self._db.scalars(stmt).first() # type: ignore
         return model
