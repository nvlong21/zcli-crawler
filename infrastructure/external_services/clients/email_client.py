from typing import Dict, Optional, Type
import grpc # Required for Status Code access
import logging

# Configuration
from ..config import EMAIL_SERVICE_URL, EMAIL_SERVICE_TOKEN, EMAIL_SENDER_ADDRESS
from .grpc_client import BaseGrpcClient, ExternalServiceError
# Use configured logger if available
try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import infrastructure logger, using basic logger for email_client.py.")


# --- Import generated gRPC code ---
try:
    # Adjust path if your generated code is elsewhere
    from infrastructure.grpc import email_pb2
    from infrastructure.grpc import email_pb2_grpc
    GENERATED_EMAIL_CODE_AVAILABLE = True
    logger.debug("Successfully imported generated gRPC code for EmailService.")
except ImportError:
    GENERATED_EMAIL_CODE_AVAILABLE = False
    logger.warning("Generated gRPC code for email service (email_pb2*.py) not found. EmailClient will be unavailable.")
    # Define dummy classes to avoid runtime errors if client is instantiated check fails
    class email_pb2: SendEmailRequest=None; SendEmailResponse=None # type: ignore
    class email_pb2_grpc: EmailServiceStub=None # type: ignore


class EmailClient(BaseGrpcClient):
    """gRPC client for the Email Service."""

    def __init__(self, default_timeout: Optional[float] = 10.0):
        if not GENERATED_EMAIL_CODE_AVAILABLE:
             raise ImportError("Cannot initialize EmailClient: Required gRPC generated code missing.")

        super().__init__(
            service_url=EMAIL_SERVICE_URL,
            service_name="EmailService",
            default_timeout=default_timeout
        )
        self._auth_token = EMAIL_SERVICE_TOKEN
        logger.info(f"EmailClient initialized for {EMAIL_SERVICE_URL}")

    def _get_stub_class(self) -> Type:
        """Returns the generated EmailServiceStub class."""
        if not email_pb2_grpc or not hasattr(email_pb2_grpc, 'EmailServiceStub'):
             raise RuntimeError("email_pb2_grpc.EmailServiceStub module is not available.")
        return email_pb2_grpc.EmailServiceStub

    def _prepare_auth_metadata(self) -> Optional[Dict[str, str]]:
        """Prepares the authorization metadata using the configured token."""
        if not self._auth_token:
            logger.warning(f"Email service token not configured for {self.service_name}. Request unauthenticated.")
            return None
        return {"authorization": f"Bearer {self._auth_token}"}

    async def send_email(self, to: str, subject: str, body_html: str, body_text: Optional[str] = None, from_addr: Optional[str] = None) -> bool:
        """
        Calls the SendEmail RPC method on the external email service.

        Args:
            to: Recipient email address.
            subject: Email subject.
            body_html: HTML content of the email.
            body_text: Optional plain text version of the email.
            from_addr: Optional sender address override. Uses configured default if None.

        Returns:
            True if the email service accepted the request, False otherwise.

        Raises:
            ExternalServiceError: If the gRPC call fails or the service returns an error status.
            RuntimeError: If gRPC generated code is missing.
            ValueError: If sender address is not configured or provided.
        """
        if not email_pb2 or not hasattr(email_pb2, 'SendEmailRequest'):
            raise RuntimeError("email_pb2.SendEmailRequest is not available.")

        sender = from_addr or EMAIL_SENDER_ADDRESS
        if not sender:
             logger.error("Cannot send email: No sender address configured or provided.")
             raise ValueError("Sender address is required.")

        request = email_pb2.SendEmailRequest(
            to=to,
            subject=subject,
            body_html=body_html,
            body_text=body_text or "", # Ensure text body is at least empty string
            from_address=sender
        )
        metadata = self._prepare_auth_metadata()

        log_extra = {"recipient": to, "subject": subject, "sender": sender}
        logger.info(f"Attempting to send email via {self.service_name}", extra=log_extra)

        try:
            response: email_pb2.SendEmailResponse = await self.call(
                method="SendEmail", data=request, headers=metadata
            )

            success = getattr(response, 'success', False)
            message_id = getattr(response, 'message_id', 'N/A')
            error_message = getattr(response, 'error_message', None)

            if success:
                logger.info(f"Email accepted by {self.service_name} for delivery to {to} (ID: {message_id})", extra=log_extra)
                return True
            else:
                logger.warning(f"{self.service_name} reported failure sending email to {to}. Reason: {error_message or 'Unknown'}", extra=log_extra)
                # Decide: return False or raise an exception based on the error?
                # raise ExternalServiceError(f"Email service failed: {error_message}", service_name=self.service_name)
                return False

        except ExternalServiceError as e:
             logger.error(f"Failed to send email to {to} via {self.service_name}: {e}", extra=log_extra)
             raise e # Re-raise gRPC/communication errors
        except Exception as e:
             logger.exception(f"Unexpected error sending email via {self.service_name} to {to}", extra=log_extra)
             raise ExternalServiceError(f"Unexpected error: {e}", service_name=self.service_name, original_exception=e) from e
