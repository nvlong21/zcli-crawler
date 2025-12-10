from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Type, Optional, List, Any, Sequence, Union
from pydantic import BaseModel, ValidationError
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func # SQLAlchemy 2.0 style imports
from uuid import UUID
from pydantic import BaseModel # For domain entity type hint
import logging

# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for base_repository.py.")


# Type variable for the SQLAlchemy model (subclass of Base)
ModelType = TypeVar('ModelType')
# Type variable for the Pydantic domain entity (subclass of BaseModel)
EntityType = TypeVar('EntityType', bound=BaseModel)
# Type for primary key (can be int, UUID, str) - Use Union for broader compatibility
PKType = Union[int, UUID, str]


# --- Base Repository Interface (Defines the contract) ---
class BaseRepositoryInterface(ABC, Generic[ModelType, EntityType]): # Removed PKType from generic def here
    """Defines the common interface for all repositories."""

    @property
    @abstractmethod
    def model_class(self) -> Type[ModelType]:
        """The SQLAlchemy model class associated with the repository."""
        raise NotImplementedError

    @property 
    @abstractmethod
    def entity_class(self) -> Type[EntityType]: pass

    @abstractmethod
    async def _map_model_to_entity(self, model: Optional[ModelType]) -> Optional[EntityType]:
        """Maps a single SQLAlchemy model instance to a domain entity."""
        raise NotImplementedError

    @abstractmethod
    async def _map_models_to_entities(self, models: Sequence[ModelType]) -> Sequence[EntityType]:
        """Maps a sequence of SQLAlchemy models to a sequence of domain entities."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, entity_id: PKType) -> Optional[EntityType]: # Use PKType here
        """Finds an entity by its primary key."""
        raise NotImplementedError

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[EntityType]:
        """Retrieves a sequence of entities with pagination."""
        raise NotImplementedError

    @abstractmethod
    async def add(self, entity: EntityType) -> EntityType:
        """Adds a new domain entity. Returns the entity (possibly updated)."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, entity: EntityType) -> Optional[EntityType]:
         """Updates an existing entity. Returns updated entity or None."""
         raise NotImplementedError

    @abstractmethod
    async def delete(self, entity_id: PKType) -> bool: # Use PKType here
        """Deletes an entity by its primary key. Returns True if deleted."""
        raise NotImplementedError

    @abstractmethod
    async def count(self) -> int:
        """Counts the total number of entities."""
        raise NotImplementedError


# --- Concrete SQLAlchemy Base Repository Implementation ---
class BaseRepository(BaseRepositoryInterface[ModelType, EntityType]): # Removed PKType here
    """Abstract Base Class providing core SQLAlchemy implementation."""

    def __init__(self, db_session: Union[Session, AsyncSession]):
        self._is_async = isinstance(db_session, AsyncSession)
        self._db: Union[Session, AsyncSession] = db_session

    @property
    @abstractmethod
    def model_class(self) -> Type[ModelType]:
        raise NotImplementedError("Subclasses must define model_class property")

    @property 
    @abstractmethod
    def entity_class(self) -> Type[EntityType]: raise NotImplementedError("Subclass must implement entity_class property")
    
    async def _map_model_to_entity(self, model: Optional[ModelType]) -> Optional[EntityType]:
        """Default mapping using Pydantic's model_validate."""
        if model is None: return None
        try:
            # Assumes EntityType is Pydantic v2 with model_config(from_attributes=True)
            entity = self.entity_class.model_validate(model)
            logger.debug(f"Validation successful for {type(model).__name__}")
            return entity
        except Exception as e:
            logger.error(f"Mapping error: {type(model).__name__} -> {EntityType.__name__}: {e}", exc_info=True)
            if isinstance(e, ValidationError):
                 logger.error(f"Pydantic Errors: {e.errors()}")
            return None

    async def _map_models_to_entities(self, models: Sequence[ModelType]) -> Sequence[EntityType]:
        """Maps a sequence of models to entities."""
        entities = [await self._map_model_to_entity(model) for model in models]
        return [entity for entity in entities if entity is not None]

    async def get_by_id(self, entity_id: PKType) -> Optional[EntityType]: # Use PKType here
        logger.debug(f"Getting {self.model_class.__name__} by ID: {entity_id}")
        if self._is_async:
            model = await self._db.get(self.model_class, entity_id) # type: ignore
        else:
            model = self._db.get(self.model_class, entity_id) # type: ignore
        return await self._map_model_to_entity(model)

    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[EntityType]:
        logger.debug(f"Getting all {self.model_class.__name__} (skip={skip}, limit={limit})")
        stmt = select(self.model_class).offset(skip).limit(limit)
        order_by_attr = getattr(self.model_class, 'id', getattr(self.model_class, 'created_at', None))
        if order_by_attr is not None:
            stmt = stmt.order_by(order_by_attr)

        if self._is_async:
            result = await self._db.execute(stmt) # type: ignore
            models = result.scalars().all()
        else:
             models = self._db.scalars(stmt).all() # type: ignore
        return await self._map_models_to_entities(models)

    async def add(self, entity: EntityType) -> EntityType:
        logger.debug(f"Adding new {type(entity).__name__} entity.")
        try:
            # Convert Pydantic entity to dict, potentially excluding unset defaults
            model_data = entity.model_dump(exclude_unset=False) # Adjust exclude_unset based on needs

            pk_name = 'id' # Assume PK name is 'id'
            db_generates_pk = False
            pk_column_info = None
            # Lấy thông tin cột từ __table__ của model nếu có
            if hasattr(self.model_class, '__table__') and pk_name in self.model_class.__table__.c:
                 pk_column_info = self.model_class.__table__.c[pk_name]

            if pk_column_info is not None:
                 # Kiểm tra xem cột có phải là integer và có auto increment không (phổ biến cho DB gen ID)
                 if isinstance(pk_column_info.type, sa.Integer) and pk_column_info.autoincrement is True:
                     db_generates_pk = True
                 # Kiểm tra xem có server_default hoặc default không (trừ trường hợp default là Python UUID factory)
                 elif pk_column_info.server_default is not None:
                     db_generates_pk = True
                 elif pk_column_info.default is not None and not callable(pk_column_info.default.arg):
                     # Chỉ coi là DB gen nếu default không phải là hàm gọi được (như uuid.uuid4)
                     db_generates_pk = True
                 # Thêm các kiểm tra khác nếu cần cho kiểu DB cụ thể (ví dụ: SERIAL cho Postgres)

            if db_generates_pk and pk_name in model_data and model_data[pk_name] is not None:
                logger.debug(f"Removing client-provided PK '{pk_name}' value '{model_data[pk_name]}' as DB likely generates it.")
                model_data.pop(pk_name, None)
            elif pk_name in model_data and model_data[pk_name] is None and not pk_column_info.nullable:
                 # Nếu PK là None nhưng cột không nullable và không phải DB gen -> lỗi tiềm ẩn
                 # Có thể bỏ qua nếu dùng default=uuid.uuid4 trong model SQLAlchemy
                 logger.debug(f"PK '{pk_name}' is None but column seems not nullable and not DB generated. Relying on SQLAlchemy model default.")
                 model_data.pop(pk_name, None) # Bỏ None để default của model chạy

            db_model = self.model_class(**model_data)
            self._db.add(db_model)

            # Flush to send INSERT and get DB-generated values
            if self._is_async:
                await self._db.flush()
                await self._db.refresh(db_model)
            else:
                 self._db.flush() # type: ignore
                 self._db.refresh(db_model) # type: ignore

            mapped_entity = await self._map_model_to_entity(db_model)
            if mapped_entity is None:
                 raise ValueError(f"Failed to map newly added {self.model_class.__name__} back to entity.")
            logger.info(f"Added {type(entity).__name__} ID: {getattr(mapped_entity, 'id', 'N/A')}")
            return mapped_entity
        except Exception as e:
             logger.exception(f"Error adding entity type {type(entity).__name__}: {e}")
             raise # Re-raise after logging

    async def update(self, entity: EntityType) -> Optional[EntityType]:
         entity_id = getattr(entity, 'id', None)
         if entity_id is None:
              logger.error(f"Update failed: {type(entity).__name__} missing 'id'.")
              raise ValueError("Entity must have 'id' for update.")

         logger.debug(f"Updating {self.model_class.__name__} ID: {entity_id}")
         if self._is_async:
             db_model = await self._db.get(self.model_class, entity_id) # type: ignore
         else:
             db_model = self._db.get(self.model_class, entity_id) # type: ignore

         if db_model is None:
             logger.warning(f"Update failed: {self.model_class.__name__} ID {entity_id} not found.")
             return None

         update_data = entity.model_dump(exclude_unset=True, exclude={'id'})
         updated = False
         for key, value in update_data.items():
             if hasattr(db_model, key):
                 if getattr(db_model, key) != value:
                    setattr(db_model, key, value)
                    updated = True
             else:
                 logger.warning(f"'{key}' not on model {self.model_class.__name__}. Skipping.")

         if not updated:
             logger.info(f"No changes for {self.model_class.__name__} ID {entity_id}. Skipping DB flush.")
             return await self._map_model_to_entity(db_model)

         try:
             self._db.add(db_model) # Mark as dirty
             if self._is_async:
                 await self._db.flush()
                 await self._db.refresh(db_model)
             else:
                 self._db.flush() # type: ignore
                 self._db.refresh(db_model) # type: ignore
             logger.info(f"Updated {self.model_class.__name__} ID: {entity_id}")
             return await self._map_model_to_entity(db_model)
         except Exception as e:
             logger.exception(f"Error updating {self.model_class.__name__} ID {entity_id}: {e}")
             raise

    async def delete(self, entity_id: PKType) -> bool: # Use PKType here
        logger.debug(f"Deleting {self.model_class.__name__} ID: {entity_id}")
        obj_to_delete = None
        if self._is_async:
            obj_to_delete = await self._db.get(self.model_class, entity_id) # type: ignore
            if obj_to_delete:
                await self._db.delete(obj_to_delete) # type: ignore
                await self._db.flush() # type: ignore
        else:
             obj_to_delete = self._db.get(self.model_class, entity_id) # type: ignore
             if obj_to_delete:
                 self._db.delete(obj_to_delete) # type: ignore
                 self._db.flush() # type: ignore

        if obj_to_delete:
             logger.info(f"Deleted {self.model_class.__name__} ID: {entity_id}")
             return True
        else:
             logger.warning(f"Delete failed: {self.model_class.__name__} ID {entity_id} not found.")
             return False

    async def count(self) -> int:
         logger.debug(f"Counting total {self.model_class.__name__}")
         stmt = select(func.count()).select_from(self.model_class)
         if self._is_async:
             result = await self._db.execute(stmt) # type: ignore
             count = result.scalar_one_or_none()
         else:
             count = self._db.scalar(stmt) # type: ignore
         return count or 0
