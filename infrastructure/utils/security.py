from passlib.context import CryptContext
from functools import lru_cache # Not strictly needed for static methods but good pattern
import logging

# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for security.py.")


# Configure the CryptContext for password hashing
pwd_context = CryptContext(
    schemes=["bcrypt"], # Use bcrypt as the default and recommended scheme
    deprecated="auto", # Automatically mark older hashes for re-hashing
    # bcrypt__rounds=12 # Optional: Adjust bcrypt rounds if needed (default is often fine)
)

logger.debug(f"Password context configured with schemes: {pwd_context.schemes}")

class PasswordHasher:
    """Provides password hashing and verification using passlib."""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain password against a stored hash."""
        if not plain_password or not hashed_password:
             logger.debug("Password verification skipped: Empty plain or hashed password provided.")
             return False
        try:
            # verify() checks the hash and handles deprecated schemes
            is_valid = pwd_context.verify(plain_password, hashed_password)
            if not is_valid:
                 logger.debug("Password verification failed: Incorrect password.")
            # Optional: Check if hash needs update and log/handle if necessary
            # needs_update = is_valid and pwd_context.needs_update(hashed_password)
            # if needs_update: logger.info("Password hash needs update.")
            return is_valid
        except Exception as e:
            # Log errors during verification (e.g., malformed hash, unsupported algorithm)
            logger.error(f"Error during password verification: {e.__class__.__name__}", exc_info=True)
            return False # Treat verification errors as failure

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hashes a plain password using the configured default scheme."""
        if not password:
             raise ValueError("Cannot hash an empty password.")
        try:
            # hash() uses the default scheme ('bcrypt' in this case)
            hashed = pwd_context.hash(password)
            logger.debug("Password hashed successfully.")
            return hashed
        except Exception as e:
             logger.error(f"Error hashing password: {e.__class__.__name__}", exc_info=True)
             raise ValueError("Could not hash password due to an internal error.") from e
