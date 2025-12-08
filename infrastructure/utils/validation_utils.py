import re
import logging
from typing import Type, TypeVar, Any, Annotated, Optional
from pydantic import (
    BaseModel, EmailStr, ValidationError, Field, field_validator, validator, AfterValidator
)
from pydantic_core import PydanticCustomError

# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for validation_utils.py.")


# Type variable for Pydantic models
T = TypeVar('T', bound=BaseModel)

# --- Pydantic Payload Validation ---
def validate_payload(payload: dict, schema: Type[T]) -> T:
    """Validates a dictionary payload against a Pydantic schema."""
    try:
        return schema.model_validate(payload) # Pydantic v2 method
    except ValidationError as e:
        logger.debug(f"Payload validation failed for schema {schema.__name__}: {len(e.errors())} errors.")
        raise e # Re-raise the detailed validation error
    except Exception as e:
        logger.exception(f"Unexpected error during payload validation for {schema.__name__}.")
        raise ValueError(f"Unexpected error validating payload: {e}") from e

# --- Common Validation Patterns & Custom Types ---

# Example: Strong Password Check (using AfterValidator for Pydantic v2)
PASSWORD_REGEX = re.compile(
   # Example: 8+ chars, UC, LC, digit, special char [@$!%*?&_#]
   r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_#])[A-Za-z\d@$!%*?&_#]{8,}$"
)
PASSWORD_ERROR_MSG = "Password must be at least 8 characters and include uppercase, lowercase, digit, and special character (@$!%*?&_#)."

def _check_strong_password(password: str) -> str:
    """Internal function to perform the regex check."""
    if not isinstance(password, str): # Should be caught by Pydantic first, but safety check
         raise ValueError('Password must be a string')
    if not PASSWORD_REGEX.match(password):
        # Raise ValueError which AfterValidator converts to a ValidationError
        raise ValueError(PASSWORD_ERROR_MSG)
    return password

# Annotated type for strong passwords
StrongPassword = Annotated[str, AfterValidator(_check_strong_password)]
# Usage in Pydantic model: password: StrongPassword

# Example: Slug Field Type
SlugStr = Annotated[
    str,
    Field(
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-friendly slug: lowercase letters, numbers, hyphens (no start/end hyphen)."
    )
]

# Example: Phone Number Validation (using phonenumbers library)
# Requires: poetry add phonenumbers typing-extensions phonenumbers[phonemetadata]
# from typing_extensions import Annotated # Use this if Python < 3.9
# try:
#     import phonenumbers
#     PHONENUMBERS_AVAILABLE = True
# except ImportError:
#     PHONENUMBERS_AVAILABLE = False
#     logger.warning("phonenumbers library not installed. Phone number validation will be skipped.")
#
# def _validate_phone_number(v: str) -> str:
#     """Internal function for phonenumbers validation."""
#     if not PHONENUMBERS_AVAILABLE: return v # Skip if library missing
#     if not isinstance(v, str): raise ValueError('Phone number must be a string')
#     try:
#         # Parse number - requires international format or specifying region
#         parsed_number = phonenumbers.parse(v, None) # Use region like "US" if needed: parse(v, "US")
#         if not phonenumbers.is_valid_number(parsed_number):
#             raise ValueError("Invalid phone number format or value.")
#         # Return number in E.164 format for consistency
#         return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
#     except phonenumbers.NumberParseException as e:
#         raise ValueError(f"Invalid phone number format: {e}") from e
#     except Exception as e:
#          logger.error(f"Unexpected error validating phone number '{v}': {e}")
#          raise ValueError(f"Error validating phone number.") from e
#
# PhoneNumberStr = Annotated[str, AfterValidator(_validate_phone_number)]
# # Usage in Pydantic model: phone_number: Optional[PhoneNumberStr] = None

# --- Add more validation helpers or custom types as needed ---
