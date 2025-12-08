from functools import lru_cache
from typing import Literal, Dict, Type

from .clients.base_client import BaseClient
from .clients.email_client import EmailClient
from .clients.payment_client import PaymentClient
from .clients.notification_client import NotificationClient
# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for ext svc factory.")


# Define literal types for known services for better type hinting
ServiceName = Literal["email", "payment", "notification"]

# Map service names to their client implementation classes
_client_map: Dict[ServiceName, Type[BaseClient]] = {
    "email": EmailClient,
    "payment": PaymentClient,
    "notification": NotificationClient,
}

# Cache client instances using lru_cache for reuse within a request/process
@lru_cache(maxsize=None)
def get_external_client(service_name: ServiceName) -> BaseClient:
    """
    Factory function to get or create an external service client instance.
    Uses lru_cache to ensure singleton instances per service type.

    Args:
        service_name: The type of service client required ('email', 'payment', etc.).

    Returns:
        An instance of the requested BaseClient implementation.

    Raises:
        ValueError: If an unsupported or unconfigured service type is requested.
        ImportError: If required dependencies (like gRPC generated code) are missing.
        RuntimeError: For other unexpected initialization errors.
    """
    logger.debug(f"Requesting external client for service: '{service_name}'")

    client_class = _client_map.get(service_name)

    if client_class is None:
        logger.error(f"Unsupported external service type requested: {service_name}")
        raise ValueError(f"Unsupported external service type: '{service_name}'. Available: {list(_client_map.keys())}")

    try:
        # Instantiate the client class. Assumes constructors handle config internally.
        instance = client_class()
        # Check if instance was already cached
        # cache_info = get_external_client.cache_info() # Python 3.9+
        # is_cached = cache_info.hits > 0 and service_name in cache_info.cache # Complex check
        # log_prefix = "Returning cached " if is_cached else "Instantiated new "
        logger.info(f"Returning instance of {client_class.__name__} for service '{service_name}'")
        return instance
    except ImportError as e:
         logger.error(f"Failed to initialize client for '{service_name}' due to missing dependency or code: {e}", exc_info=True)
         raise ImportError(f"Could not create client for '{service_name}'. Check dependencies and generated code. Original error: {e}") from e
    except Exception as e:
         logger.exception(f"Unexpected error creating client for '{service_name}': {e}")
         raise RuntimeError(f"Could not create client for '{service_name}'. Check configuration and logs.") from e

async def close_all_external_clients():
     """Calls the close method on all known client types if they were instantiated."""
     logger.info("Attempting to close all external service clients...")
     closed_count = 0
     errors = []
     # We need to check the cache or iterate through known types
     cache_dict = get_external_client.__wrapped__.__dict__.get('__cache', {}) # Access cache internals (fragile)

     for args, client_instance in cache_dict.items():
         service_name = args[0] # service_name is the first arg to get_external_client
         if hasattr(client_instance, 'close') and callable(client_instance.close):
             try:
                 logger.debug(f"Closing client for service '{service_name}'...")
                 await client_instance.close()
                 closed_count += 1
             except Exception as e:
                 error_msg = f"Error closing client for service '{service_name}': {e}"
                 logger.error(error_msg)
                 errors.append(error_msg)

     get_external_client.cache_clear() # Clear the cache after attempting close
     logger.info(f"External service clients closed: {closed_count}. Errors: {len(errors)}.")
     if errors:
         logger.error(f"Errors occurred during client closure: {'; '.join(errors)}")
