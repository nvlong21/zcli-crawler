from fastapi import Depends, HTTPException, status
from typing import List, Optional, Annotated, Set, Callable, Awaitable
import logging

# Local imports
from .jwt import get_token_payload, TokenPayload
# Optional: Import get_current_user if DB checks are needed
# from .jwt import get_current_user
# from features.users.domain.entities.user import User as UserEntity # Example User Entity

# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for permissions.py.")

# Type alias for the dependency function created by the factory
PermissionChecker = Callable[..., Awaitable[TokenPayload]] # Or UserEntity if get_current_user used

# --- Permission Dependency Factory ---

def require_permission(
    *, # Force keyword arguments for clarity
    required_roles: Optional[List[str]] = None,
    # Add other permission types if needed, e.g., specific action strings
    # required_permissions: Optional[List[str]] = None,
    allow_superuser: bool = True # Option to automatically allow superusers
) -> PermissionChecker:
    """
    Factory function to create a FastAPI dependency that enforces permission checks.

    Args:
        required_roles: A list of role names. The user MUST have ALL roles in this list.
                        Role matching is case-insensitive.
        # required_permissions: A list of specific permission strings the user needs.
        allow_superuser: If True, users marked as 'is_superuser' (in token or DB)
                         bypass other checks.

    Returns:
        An asynchronous dependency function suitable for FastAPI's `Depends`.
        This function takes the token payload (and optionally the user object)
        and raises HTTPException(403) if permissions are insufficient.
        It returns the payload (or user object) if authorized.
    """

    # Pre-process requirements for efficiency (lowercase sets)
    required_roles_set = {role.lower() for role in required_roles} if required_roles else set()
    # required_permissions_set = set(required_permissions) if required_permissions else set()

    async def _permission_checker(
        # Depends on the validated token payload
        payload: Annotated[TokenPayload, Depends(get_token_payload)],
        # Optionally inject the full user object if permissions require DB checks
        # current_user: Annotated[UserEntity, Depends(get_current_user)] # Uncomment if needed
    ) -> TokenPayload: # Return payload to potentially pass user info implicitly
                       # Change return type to UserEntity if current_user is injected and returned
        """
        Performs the actual permission checks based on the factory's configuration.
        Raises HTTPException(403) on failure.
        """
        user_identifier = payload.sub
        log_extra = {"user_sub": user_identifier, "required_roles": list(required_roles_set)}

        # 1. Check for Superuser Bypass (if enabled)
        is_superuser = False
        if allow_superuser:
            # Check token claim first (e.g., 'is_superuser' boolean claim)
            is_superuser = getattr(payload, 'is_superuser', False) # Assumes 'is_superuser' claim exists
            # OR check DB user object if available and preferred source of truth
            # if 'current_user' in locals() and hasattr(current_user, 'is_superuser'):
            #    is_superuser = current_user.is_superuser

            if is_superuser:
                logger.debug(f"Superuser bypass: Access granted for '{user_identifier}'.", extra=log_extra)
                return payload # Superuser automatically passes

        # 2. Check Required Roles (typically from JWT 'roles' claim)
        if required_roles_set:
            # Get user's roles from token payload (ensure it's a list, default empty)
            user_roles_list = getattr(payload, 'roles', [])
            user_roles_set = {role.lower() for role in user_roles_list} # Case-insensitive comparison

            if not required_roles_set.issubset(user_roles_set):
                missing_roles = required_roles_set - user_roles_set
                error_detail = f"Insufficient permissions. Missing required role(s): {', '.join(sorted(missing_roles))}"
                logger.warning(f"Permission denied for '{user_identifier}': {error_detail}", extra=log_extra)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error_detail
                )
            logger.debug(f"Role check passed for '{user_identifier}'.", extra=log_extra)

        # 3. Check Specific Permissions (Example: if using DB-based permissions)
        # ... (logic remains the same as previous answer) ...


        # If all checks pass, return the payload (or user object)
        logger.debug(f"All permission checks passed for '{user_identifier}'. Access granted.", extra=log_extra)
        # Change return value if returning current_user instead of payload
        return payload

    return _permission_checker


# --- Example Pre-defined Permission Dependencies ---
is_authenticated = Depends(get_token_payload)
is_admin = Depends(require_permission(required_roles=["admin"]))
is_editor = Depends(require_permission(required_roles=["editor"]))
is_moderator_and_publisher = Depends(require_permission(required_roles=["moderator", "publisher"]))
is_superuser_only = Depends(require_permission(required_roles=["superuser"], allow_superuser=False))

