import abc
from typing import Union
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
import logging

# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for uow.py.")


class AbstractUnitOfWork(abc.ABC):
    """Abstract Base Class for the Unit of Work pattern."""

    async def __aenter__(self):
        """Enter the async runtime context and return the UoW instance."""
        logger.debug(f"Entering UoW context ({type(self).__name__})")
        # Optional: Begin transaction explicitly if needed by DB driver/session setup
        # await self._session.begin() # Example if session doesn't auto-begin
        return self

    async def __aexit__(self, exc_type, exc_val, traceback):
        """Exit the async runtime context, handling commit or rollback."""
        if exc_type:
            logger.warning(f"Exception occurred within UoW context: {exc_type.__name__}. Rolling back.", exc_info=exc_val)
            try:
                await self.rollback()
            except Exception as rb_exc:
                 logger.exception(f"Exception during UoW rollback: {rb_exc}")
                 # Decide how to handle rollback errors (log? raise?)
            # Do not suppress the original exception by default
        else:
            logger.debug("Committing UoW context.")
            try:
                await self.commit()
            except Exception as commit_exc:
                 logger.exception(f"Exception during UoW commit. Rolling back. Error: {commit_exc}")
                 try:
                     await self.rollback()
                 except Exception as rb_exc_on_commit_fail:
                      logger.exception(f"Exception during UoW rollback after commit failure: {rb_exc_on_commit_fail}")
                 raise commit_exc # Re-raise the original commit exception
        logger.debug(f"Exiting UoW context ({type(self).__name__})")

    @abc.abstractmethod
    async def commit(self):
        """Commit the current transaction."""
        raise NotImplementedError

    @abc.abstractmethod
    async def rollback(self):
        """Roll back the current transaction."""
        raise NotImplementedError

    # Optional: Repository accessors if UoW manages repository instances
    # @property
    # @abc.abstractmethod
    # def users(self) -> UserRepositoryInterface: raise NotImplementedError


class UnitOfWork(AbstractUnitOfWork):
    """Synchronous Unit of Work implementation using SQLAlchemy Session."""

    def __init__(self, session: Session):
        self._session = session

    # Although using async context managers, the actual operations are sync
    async def commit(self):
        """Commits the transaction using the sync session."""
        try:
            self._session.commit()
            logger.debug("Sync session commit successful.")
        except Exception as e:
             logger.error(f"Sync session commit failed: {e}", exc_info=True)
             raise # Re-raise commit errors

    async def rollback(self):
        """Rolls back the transaction using the sync session."""
        try:
            self._session.rollback()
            logger.debug("Sync session rollback successful.")
        except Exception as e:
             logger.error(f"Sync session rollback failed: {e}", exc_info=True)
             raise # Re-raise rollback errors


class AsyncUnitOfWork(AbstractUnitOfWork):
    """Asynchronous Unit of Work implementation using SQLAlchemy AsyncSession."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def commit(self):
        """Commits the transaction using the async session."""
        try:
            await self._session.commit()
            logger.debug("Async session commit successful.")
        except Exception as e:
             logger.error(f"Async session commit failed: {e}", exc_info=True)
             raise # Re-raise commit errors

    async def rollback(self):
        """Rolls back the transaction using the async session."""
        try:
            await self._session.rollback()
            logger.debug("Async session rollback successful.")
        except Exception as e:
             logger.error(f"Async session rollback failed: {e}", exc_info=True)
             raise # Re-raise rollback errors
