from typing import Generator, Type, Annotated, AsyncGenerator, TypeVar, Union, Any, Callable # Added Callable
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from functools import lru_cache
import logging

# --- Core Application Imports ---
from app.config import settings # Import loaded settings instance

# --- Infrastructure Abstractions & Factories ---
# Database
from infrastructure.database.session import SessionLocal, AsyncSessionLocal # Sync and Async session factories
from infrastructure.uow import AbstractUnitOfWork, UnitOfWork, AsyncUnitOfWork # UoW Abstraction + Implementations
# Repository
from infrastructure.repositories.base_repository import BaseRepositoryInterface # Repo Interface
from infrastructure.repositories.factory import get_repository, RepositoryFactoryError # Repo Factory
# Cache
from infrastructure.cache.base_cache import BaseCache # Cache Interface
from infrastructure.cache.factory import get_cache # Cache Factory
# External Services
from infrastructure.external_services.clients.base_client import BaseClient # Ext Client Interface
from infrastructure.external_services.factory import get_external_client, ServiceName # Ext Client Factory + Literal Type
# Security & Utils
from infrastructure.utils.security import PasswordHasher # Security Util
# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for dependencies.py.")


# --- Type Variables for Generics ---
T = TypeVar('T') # Generic type
ModelType = TypeVar('ModelType') # DB Model type (SQLAlchemy)
EntityType = TypeVar('EntityType') # Domain Entity type (Pydantic)

# --- Database Session Dependency Providers ---

# Synchronous Session Provider
def get_db_session_sync() -> Generator[Session, None, None]:
    """Dependency provider for a synchronous SQLAlchemy session."""
    if SessionLocal is None:
        logger.error("Synchronous SessionLocal is not initialized. Check database configuration and session.py.")
        raise RuntimeError("Synchronous DB session factory not available.")
    db: Session = SessionLocal()
    logger.debug(f"DB Sync Session [{id(db)}] created.")
    try:
        yield db
    finally:
        logger.debug(f"DB Sync Session [{id(db)}] closed.")
        db.close()

# Asynchronous Session Provider
async def get_db_session_async() -> AsyncGenerator[AsyncSession, None]:
    """Dependency provider for an asynchronous SQLAlchemy session."""
    if AsyncSessionLocal is None:
        logger.error("Asynchronous AsyncSessionLocal is not initialized. Check database configuration and session.py.")
        raise RuntimeError("Asynchronous DB session factory not available.")
    session: AsyncSession = AsyncSessionLocal()
    logger.debug(f"DB Async Session [{id(session)}] created.")
    try:
        yield session
        # Transactions are typically managed by UoW or endpoint logic
    except Exception as e:
        logger.exception(f"DB Async Session [{id(session)}] rolling back due to unhandled exception: {e}")
        await session.rollback()
        raise # Re-raise the exception for FastAPI/middleware to handle
    finally:
        logger.debug(f"DB Async Session [{id(session)}] closed.")
        await session.close()

# Determine default session type based on configured DATABASE_URL
db_url_str = str(settings.DATABASE_URL)
IS_ASYNC_DB = "aiosqlite" in db_url_str or "asyncpg" in db_url_str

if IS_ASYNC_DB:
    DefaultSessionDep = get_db_session_async
    DBSession = Annotated[AsyncSession, Depends(DefaultSessionDep)]
    logger.info("Default Database Session Dependency: Async")
else:
    DefaultSessionDep = get_db_session_sync
    DBSession = Annotated[Session, Depends(DefaultSessionDep)]
    logger.info("Default Database Session Dependency: Sync")


# --- Unit of Work Dependency Providers ---

# Synchronous UoW Provider
def get_uow_sync(session: Annotated[Session, Depends(get_db_session_sync)]) -> AbstractUnitOfWork:
    """Dependency provider for a synchronous Unit of Work."""
    return UnitOfWork(session)

# Asynchronous UoW Provider
async def get_uow_async(session: Annotated[AsyncSession, Depends(get_db_session_async)]) -> AbstractUnitOfWork:
    """Dependency provider for an asynchronous Unit of Work."""
    return AsyncUnitOfWork(session)

# Choose default UoW based on session type
if IS_ASYNC_DB:
     DefaultUoWDep = get_uow_async
     UoW = Annotated[AsyncUnitOfWork, Depends(DefaultUoWDep)]
     logger.info("Default Unit of Work Dependency: Async")
else:
     DefaultUoWDep = get_uow_sync
     UoW = Annotated[UnitOfWork, Depends(DefaultUoWDep)]
     logger.info("Default Unit of Work Dependency: Sync")


# --- Repository Dependency Factory ---

# Factory function to create a dependency *provider* for a specific repository type
def get_repo(
    entity_type: Type[EntityType]
) -> Callable[[DBSession], BaseRepositoryInterface[Any, EntityType]]:
    """
    Returns a dependency function (provider) that, when called by FastAPI,
    will inject the correct repository instance for the given entity type,
    using the default session type (DBSession).

    Args:
        entity_type: The Pydantic domain entity class.

    Returns:
        A callable suitable for use with FastAPI's Depends().
    """
    def _get_specific_repository(
        # Depends on the resolved default session type (Sync/Async)
        session: DBSession
    ) -> BaseRepositoryInterface[Any, EntityType]:
        """This inner function is the actual dependency injected by FastAPI."""
        try:
            # Pass the entity type and the resolved session instance to the factory
            # The type ignore might be needed if the factory expects a more specific
            # session type than the Union inferred from DBSession.
            repo = get_repository(entity_type, session) # type: ignore
            logger.debug(f"Repository [{type(repo).__name__}] injected for entity [{entity_type.__name__}] with session [{id(session)}]")
            return repo
        except RepositoryFactoryError as e:
            logger.error(f"Failed dependency resolution: Could not get repository for {entity_type.__name__}: {e}")
            # Raise HTTPException to provide a clear API error response
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal configuration error: Repository for '{entity_type.__name__}' is not available."
            ) from e
        except Exception as e:
            logger.exception(f"Unexpected error resolving repository dependency for {entity_type.__name__}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while resolving repository dependency."
            ) from e

    return _get_specific_repository

# --- Cache Dependency ---
# Directly uses the cache factory, which returns a singleton instance
CacheDep = Annotated[BaseCache, Depends(get_cache)]

# --- External Client Dependency Providers ---
# Creates dependencies for specific external clients using the factory

def get_email_client_dep() -> BaseClient:
    """Dependency provider for the Email client."""
    return get_external_client("email")

def get_payment_client_dep() -> BaseClient:
    """Dependency provider for the Payment client."""
    return get_external_client("payment")

def get_notification_client_dep() -> BaseClient:
    """Dependency provider for the Notification client."""
    return get_external_client("notification")

# Annotated dependencies for easy injection
EmailClientDep = Annotated[BaseClient, Depends(get_email_client_dep)]
PaymentClientDep = Annotated[BaseClient, Depends(get_payment_client_dep)]
NotificationClientDep = Annotated[BaseClient, Depends(get_notification_client_dep)]

# --- Security Dependency Providers ---
@lru_cache() # Cache the PasswordHasher instance for performance
def get_password_hasher() -> PasswordHasher:
    """Dependency provider for the PasswordHasher."""
    return PasswordHasher()

PasswordHasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]

# --- Common Authentication Dependencies ---
# Import after other dependencies are defined
try:
    from infrastructure.auth.jwt import get_token_payload, TokenPayload
    # from infrastructure.auth.permissions import is_authenticated, is_admin # Import common checks if defined

    # Basic dependency to ensure a valid token exists and get its payload
    Authenticated = Annotated[TokenPayload, Depends(get_token_payload)]

    # Optional: Define get_current_user here if User feature is always present
    # from features.users.domain.entities.user import User as UserEntity # Example import
    # # Need a way to get the specific User repository here
    # def get_user_repo_direct(session: DBSession) -> BaseRepositoryInterface[Any, UserEntity]:
    #      return get_repository(UserEntity, session) # type: ignore
    # UserRepoDep = Annotated[BaseRepositoryInterface[Any, UserEntity], Depends(get_user_repo_direct)]
    #
    # async def get_current_user(payload: Authenticated, user_repo: UserRepoDep) -> UserEntity: ... # Implement fetch logic

except ImportError:
    logger.warning("Could not import JWT/Permission dependencies. Authentication endpoints/checks might fail.")
    # Define dummy types if needed to prevent downstream import errors
    class TokenPayload: pass # Dummy
    Authenticated = Annotated[TokenPayload, Depends(lambda: None)] # Dummy dependency

