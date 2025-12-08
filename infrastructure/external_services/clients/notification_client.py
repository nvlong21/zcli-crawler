from typing import Any, Dict, Optional, List, Union
import logging

# Configuration
from ..config import NOTIFICATION_SERVICE_URL, NOTIFICATION_API_KEY
# Base HTTP Client
from .http_client import HTTPClient, ExternalServiceError
# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for notification_client.py.")


class NotificationClient(HTTPClient):
    """HTTP client specifically for the Notification Service."""

    def __init__(self, default_timeout: Optional[float] = 5.0): # Shorter timeout for notifications
        if not NOTIFICATION_API_KEY:
            logger.warning("NOTIFICATION_API_KEY is not configured. Notification client calls may fail.")
            api_key_value = "MISSING_API_KEY"
        else:
            api_key_value = NOTIFICATION_API_KEY

        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Adjust auth header based on the notification service's requirements
            "X-API-KEY": api_key_value # Example: Using X-API-KEY header
        }

        super().__init__(
            base_url=str(NOTIFICATION_SERVICE_URL), # Ensure base_url is string
            service_name="NotificationService",
            default_headers=default_headers,
            default_timeout=default_timeout
        )
        logger.info(f"NotificationClient initialized for {NOTIFICATION_SERVICE_URL}")

    # --- Notification Service Specific Methods ---
    async def send_notification(
        self,
        channel: str, # e.g., 'email', 'sms', 'push', 'webhook'
        recipient: Union[str, Dict, List[str]], # Format depends on channel/service
        template_id: Optional[str] = None,
        subject: Optional[str] = None, # For email
        content: Optional[Union[str, Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None, # Template variables
        **kwargs # Other service-specific options
    ) -> Dict[str, Any]:
        """Sends a notification via the external notification service."""
        if channel == 'email' and not subject and not template_id:
             raise ValueError("Subject is required for email channel when not using a template.")
        if not content and not template_id:
             raise ValueError("Either content or template_id must be provided.")

        endpoint = "/v1/send" # Example endpoint

        payload = {
            "channel": channel, "recipient": recipient, "template_id": template_id,
            "subject": subject, "content": content, "context": context or {},
            "options": kwargs
        }
        # Remove None values and empty options dict before sending
        payload = {k: v for k, v in payload.items() if v is not None}
        if not payload.get("options"): payload.pop("options", None)

        log_extra = {"channel": channel, "template_id": template_id, "subject": subject}
        logger.info(f"Attempting to send notification via {self.service_name}", extra=log_extra)
        logger.debug(f"Notification payload keys: {list(payload.keys())}", extra=log_extra) # Avoid logging PII

        try:
            response_data = await self.post(endpoint=endpoint, data=payload)
            response_id = response_data.get('id', response_data.get('message_id', 'N/A'))
            response_status = response_data.get('status', 'N/A')
            logger.info(f"Notification sent via {self.service_name}. Response ID: {response_id}, Status: {response_status}", extra={**log_extra, "response_id": response_id})
            return response_data
        except ExternalServiceError as e:
            logger.error(f"Failed to send notification via {self.service_name}: {e}", extra=log_extra)
            raise
        except Exception as e:
            logger.exception(f"Unexpected error sending notification via {self.service_name}", extra=log_extra)
            raise ExternalServiceError(f"Unexpected error: {e}", service_name=self.service_name, original_exception=e) from e

    # Add other notification methods (get status, schedule, cancel) here...
