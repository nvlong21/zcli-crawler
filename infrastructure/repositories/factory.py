from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Type, TypeVar, Dict, Any, Union, Callable # Added Callable
from pydantic import BaseModel # For EntityType hint
import logging
import uuid # Import uuid for PKType hint

# Local imports
from .base_repository import BaseRepositoryInterface, BaseRepository # Import Base classes
# from app.config import settings # Import if needed for config-based factory logic

# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for repo factory.")

# --- Import Domain Entities ---  
from features.audio_crawl.domain.entities.audio_crawl import AudioCrawl as AudioCrawlEntity
# MARKER: Add Domain Entity Imports Here
from features.orders.domain.entities.orders import Orders as OrdersEntity
from features.users.domain.entities.user import User as UserEntity

# --- Import Concrete Repository Implementations ---
from infrastructure.repositories.audio_crawl_repository import AudioCrawlRepository
from infrastructure.repositories.user_repository import UserRepository           
from infrastructure.repositories.orders_repository import OrdersRepository



# --- Type Variables ---
EntityType = TypeVar('EntityType', bound=BaseModel) # Domain Entity (Pydantic Model)
ModelType = TypeVar('ModelType') # DB Model (SQLAlchemy Base subclass)
RepoImpl = TypeVar('RepoImpl', bound=BaseRepository) # Concrete Repository Implementation class
PKType = Union[int, str, uuid.UUID] # Primary Key Type Union


# --- Repository Mapping ---
# Maps Domain Entity Type -> Concrete Repository Implementation Class
_repository_map: Dict[Type[EntityType], Type[RepoImpl]] = {
        AudioCrawlEntity: AudioCrawlRepository,        
        AudioCrawlEntity: AudioCrawlRepository,        
        AudioCrawlEntity: AudioCrawlRepository,        
        AudioCrawlEntity: AudioCrawlRepository,    # MARKER: Add Repository Mappings Here
        OrdersEntity: OrdersRepository,
        UserEntity:UserRepository
}

# --- Custom Exception ---
class RepositoryFactoryError(ValueError):
    """Custom exception for repository factory errors."""
    pass

# --- Factory Function ---
def get_repository(
    entity_type: Type[EntityType],
    db_session: Union[Session, AsyncSession] # Accept either sync or async session
) -> BaseRepositoryInterface[ModelType, EntityType]: # Return the Interface (PKType removed from generic here)
    """
    Factory function to get a repository instance for a given domain entity type.

    Args:
        entity_type: The domain entity class (e.g., UserEntity).
        db_session: The SQLAlchemy session (sync or async) to inject.

    Returns:
        An instance of the concrete repository implementation for the entity type,
        typed as the BaseRepositoryInterface.

    Raises:
        RepositoryFactoryError: If no repository mapping is found or instantiation fails.
    """
    logger.debug(f"Requesting repository for entity type: {entity_type.__name__}")

    # Look up the concrete repository class from the map
    repo_class = _repository_map.get(entity_type)

    if repo_class is None:
        logger.error(f"No repository implementation registered for entity type: {entity_type.__name__}")
        registered_keys = [k.__name__ for k in _repository_map.keys()]
        raise RepositoryFactoryError(
            f"Repository implementation not found for {entity_type.__name__}. "
            f"Registered types: {registered_keys}. "
            "Ensure it's registered in infrastructure/repositories/factory.py."
        )

    # Instantiate the repository with the provided session
    try:
        instance = repo_class(db_session) # BaseRepository handles session type union
        logger.debug(f"Instantiated repository: {repo_class.__name__} for {entity_type.__name__}")
        return instance # Type checker might expect narrower type, but should work
    except Exception as e:
        logger.exception(f"Error instantiating repository {repo_class.__name__} for {entity_type.__name__}: {e}")
        raise RepositoryFactoryError(
            f"Error instantiating repository {repo_class.__name__}: {e}"
        ) from e

# Note: Feature generation scripts need to insert lines at MARKER comments.
