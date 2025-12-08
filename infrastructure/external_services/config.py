# Re-export specific settings from the main config for clarity and potentially
# easier mocking in tests.
from app.config import settings
# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for ext svc config.")


logger.debug("Loading external service configurations...")

# Email Service (gRPC Example)
EMAIL_SERVICE_URL = settings.EMAIL_SERVICE_URL
EMAIL_SERVICE_TOKEN = settings.EMAIL_SERVICE_TOKEN
EMAIL_SENDER_ADDRESS = settings.EMAIL_SENDER_ADDRESS
logger.debug(f"Email Service URL: {EMAIL_SERVICE_URL}")

# Payment Service (HTTP Example)
PAYMENT_SERVICE_URL = settings.PAYMENT_SERVICE_URL
PAYMENT_API_KEY = settings.PAYMENT_API_KEY
logger.debug(f"Payment Service URL: {PAYMENT_SERVICE_URL}")

# Notification Service (HTTP Example)
NOTIFICATION_SERVICE_URL = settings.NOTIFICATION_SERVICE_URL
NOTIFICATION_API_KEY = settings.NOTIFICATION_API_KEY
logger.debug(f"Notification Service URL: {NOTIFICATION_SERVICE_URL}")

# Add other service configs as needed

# Alternatively, define specific Pydantic models per service if config is complex:
# from pydantic_settings import BaseSettings, SettingsConfigDict
# from pydantic import Field, AnyHttpUrl
# class PaymentServiceConfig(BaseSettings):
#     model_config = SettingsConfigDict(env_file='.env', extra='ignore')
#
#     url: AnyHttpUrl = Field(..., alias='PAYMENT_SERVICE_URL')
#     api_key: str = Field(..., alias='PAYMENT_API_KEY')
#     timeout: int = 15
#
# try:
#    payment_config = PaymentServiceConfig()
# except Exception as e:
#    logger.error(f"Failed to load PaymentServiceConfig: {e}")
#    # Handle error appropriately (e.g., set defaults, raise critical error)
#    payment_config = None # Example fallback
