from typing import Any, Dict, Optional
import logging

# Configuration
from ..config import PAYMENT_SERVICE_URL, PAYMENT_API_KEY
# Base HTTP Client
from .http_client import HTTPClient, ExternalServiceError
# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for payment_client.py.")


class PaymentClient(HTTPClient):
    """HTTP client specifically configured for the Payment Service."""

    def __init__(self, default_timeout: Optional[float] = 15.0): # Longer timeout for payments
        if not PAYMENT_API_KEY:
            logger.warning("PAYMENT_API_KEY is not configured. Payment client calls may fail authentication.")
            auth_header_value = "MISSING_API_KEY"
        else:
             # Adjust auth scheme as needed (Bearer, ApiKey, Basic, X-Api-Key header, etc.)
             auth_header_value = f"ApiKey {PAYMENT_API_KEY}" # Example: Custom ApiKey scheme

        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": auth_header_value
            # Or use a different header like "X-API-KEY": PAYMENT_API_KEY
        }

        super().__init__(
            base_url=str(PAYMENT_SERVICE_URL), # Ensure base_url is string
            service_name="PaymentService",
            default_headers=default_headers,
            default_timeout=default_timeout
        )
        logger.info(f"PaymentClient initialized for {PAYMENT_SERVICE_URL}")

    # --- Payment Service Specific Methods ---
    async def create_charge(
        self,
        amount: int, # Amount in cents/smallest currency unit
        currency: str, # e.g., "usd", "eur"
        source: str, # e.g., card token "tok_...", payment method ID "pm_..."
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        customer_id: Optional[str] = None, # Example optional field
        capture: bool = True # Example: whether to capture immediately
    ) -> Dict[str, Any]:
        """Calls the payment service endpoint to create a payment charge."""
        endpoint = "/v1/charges" # Example endpoint
        payload = { "amount": amount, "currency": currency.lower(), "source": source, "capture": capture }
        if description: payload["description"] = description
        if metadata: payload["metadata"] = metadata
        if customer_id: payload["customer"] = customer_id # Check actual API key name

        log_extra = {"amount": amount, "currency": currency, "capture": capture}
        logger.info(f"Attempting to create charge via {self.service_name}", extra=log_extra)

        try:
            response_data = await self.post(endpoint=endpoint, data=payload)
            charge_id = response_data.get('id', 'N/A')
            charge_status = response_data.get('status', 'N/A')
            logger.info(f"Charge created via {self.service_name}. ID: {charge_id}, Status: {charge_status}", extra={**log_extra, "charge_id": charge_id})
            return response_data
        except ExternalServiceError as e:
            logger.error(f"Failed to create charge via {self.service_name}: {e}", extra=log_extra)
            raise # Re-raise the original error
        except Exception as e:
            logger.exception(f"Unexpected error during charge creation via {self.service_name}", extra=log_extra)
            raise ExternalServiceError(f"Unexpected error: {e}", service_name=self.service_name, original_exception=e) from e

    async def retrieve_charge(self, charge_id: str) -> Dict[str, Any]:
        """Calls the payment service endpoint to retrieve details of a specific charge."""
        endpoint = f"/v1/charges/{charge_id}" # Example endpoint
        log_extra = {"charge_id": charge_id}
        logger.info(f"Attempting to retrieve charge via {self.service_name}", extra=log_extra)

        try:
            response_data = await self.get(endpoint=endpoint)
            retrieved_status = response_data.get('status', 'N/A')
            logger.info(f"Charge retrieved via {self.service_name}. ID: {charge_id}, Status: {retrieved_status}", extra=log_extra)
            return response_data
        except ExternalServiceError as e:
            if e.status_code == 404:
                logger.warning(f"Charge not found via {self.service_name}: ID {charge_id}", extra=log_extra)
            else:
                logger.error(f"Failed to retrieve charge via {self.service_name}: {e}", extra=log_extra)
            raise
        except Exception as e:
            logger.exception(f"Unexpected error retrieving charge via {self.service_name}", extra=log_extra)
            raise ExternalServiceError(f"Unexpected error: {e}", service_name=self.service_name, original_exception=e) from e

    # Add other payment methods (capture, refund, list, etc.) here...
