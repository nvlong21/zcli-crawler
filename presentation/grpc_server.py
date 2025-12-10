import asyncio
import grpc
import grpc.aio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Tuple, Type, Any, Callable
import logging
import os # Added os
from pathlib import Path # Added for path handling

# --- Application Imports ---

try:
    from infrastructure.utils.logging_config import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Using basic logger for grpc_server.py.")
try:
    from app.config import settings
    GRPC_SETTINGS_IMPORTED = True
except ImportError:
    logger.error("Cannot import app settings for gRPC server configuration. Using default values.")
    GRPC_SETTINGS_IMPORTED = False
    # Đặt giá trị mặc định vào các biến thay vì class fallback
    _fallback_environment = "development"
    _fallback_grpc_use_tls = False
    _fallback_grpc_shutdown_grace = 5.0
    _fallback_grpc_server_key_path = None
    _fallback_grpc_server_cert_path = None

# --- gRPC Servicer Imports ---
    # from features.audio_crawl.presentation.grpc.audio_crawl_service import AudioCrawlServicer    # from features.audio_crawl.presentation.grpc.audio_crawl_service import AudioCrawlServicer    # from features.audio_crawl.presentation.grpc.audio_crawl_service import AudioCrawlServicer    # from features.audio_crawl.presentation.grpc.audio_crawl_service import AudioCrawlServicer# MARKER: Add gRPC Servicer Imports Here
# Example: from features.users.presentation.grpc.users_service import UserServicer

# --- gRPC Stub Registration Imports ---
    # from infrastructure.grpc import audio_crawl_pb2_grpc    # from infrastructure.grpc import audio_crawl_pb2_grpc    # from infrastructure.grpc import audio_crawl_pb2_grpc    # from infrastructure.grpc import audio_crawl_pb2_grpc# MARKER: Add gRPC Stub Registration Imports Here
# Example: from infrastructure.grpc import users_pb2_grpc


# --- Server State ---
_server: Optional[grpc.aio.Server] = None
_stop_event = asyncio.Event()

# --- Service Registration List (Populated by Markers) ---
_GRPC_SERVICES_TO_REGISTER: List[Tuple[Callable[[Any, grpc.aio.Server], None], Any]] = [
        # (audio_crawl_pb2_grpc.add_AudioCrawlServiceServicer_to_server, AudioCrawlServicer()),        # (audio_crawl_pb2_grpc.add_AudioCrawlServiceServicer_to_server, AudioCrawlServicer()),        # (audio_crawl_pb2_grpc.add_AudioCrawlServiceServicer_to_server, AudioCrawlServicer()),        # (audio_crawl_pb2_grpc.add_AudioCrawlServiceServicer_to_server, AudioCrawlServicer()),    # MARKER: Add Servicer Registration Tuples Here
    # Example: (users_pb2_grpc.add_UserServiceServicer_to_server, UserServicer(dependencies...)),
]

# --- Helper to load TLS credentials ---
def _load_credentials() -> Optional[grpc.ServerCredentials]:
    """Loads TLS server credentials from paths specified in settings."""
    key_path_str = getattr(settings, "GRPC_SERVER_KEY_PATH", _fallback_grpc_server_key_path) if GRPC_SETTINGS_IMPORTED else _fallback_grpc_server_key_path
    cert_path_str = getattr(settings, "GRPC_SERVER_CERT_PATH", _fallback_grpc_server_cert_path) if GRPC_SETTINGS_IMPORTED else _fallback_grpc_server_cert_path

    if not key_path_str or not cert_path_str:
        logger.warning("GRPC_USE_TLS is true, but GRPC_SERVER_KEY_PATH or GRPC_SERVER_CERT_PATH is not set.")
        return None

    key_path = Path(key_path_str)
    cert_path = Path(cert_path_str)

    if not key_path.is_file() or not cert_path.is_file():
        logger.error(f"TLS key/cert file not found at specified paths: Key='{key_path}', Cert='{cert_path}'")
        return None

    try:
        logger.debug(f"Loading TLS key: {key_path}, cert: {cert_path}")
        private_key = key_path.read_bytes()
        certificate_chain = cert_path.read_bytes()
        return grpc.ssl_server_credentials([(private_key, certificate_chain)])
    except Exception as e:
        logger.exception(f"Failed to load TLS credentials: {e}")
        return None


async def serve_grpc():
    """Configures and starts the asynchronous gRPC server."""
    global _server
    if _server: logger.warning("gRPC server already running/starting."); return
    if not _GRPC_SERVICES_TO_REGISTER: logger.info("No gRPC services registered. Server not starting."); _stop_event.set(); return

    # --- Create Server ---
    # TODO: Configure interceptors, thread pool, options from settings
    server_options = [
        # ('grpc.so_reuseport', 1), # May help with scaling across cores
    ]
    server = grpc.aio.server(options=server_options)
    _server = server

    # --- Register Services ---
    for add_func, instance in _GRPC_SERVICES_TO_REGISTER:
        try: add_func(instance, server); logger.info(f"Registered gRPC servicer: {type(instance).__name__}")
        except Exception as e: logger.exception(f"Failed register gRPC servicer {type(instance).__name__}"); await stop_grpc_server(); return

    # --- Configure Port and Credentials ---
    listen_addr = os.getenv("GRPC_LISTEN_ADDR", "[::]:50051")
    use_tls = getattr(settings, "GRPC_USE_TLS", _fallback_grpc_use_tls) if GRPC_SETTINGS_IMPORTED else _fallback_grpc_use_tls
    current_environment = getattr(settings, "ENVIRONMENT", _fallback_environment) if GRPC_SETTINGS_IMPORTED else _fallback_environment
    credentials_loaded = False

    try:
        if use_tls:
            logger.info(f"Attempting secure gRPC server on {listen_addr}...")
            server_credentials = _load_credentials()
            if server_credentials:
                server.add_secure_port(listen_addr, server_credentials)
                logger.info(f"gRPC server listening securely on {listen_addr}")
                credentials_loaded = True
            else:
                # Error loading credentials logged in _load_credentials
                raise ValueError("Failed to load TLS credentials.")
        else:
            server.add_insecure_port(listen_addr)
            logger.warning(f"gRPC server starting INSECURELY on {listen_addr} (TLS disabled).")
            credentials_loaded = True # Insecure counts as "loaded" for startup logic
    except Exception as e:
        logger.error(f"Failed config gRPC port: {e}", exc_info=True)
        # Handle critical failure in production if TLS required but failed
        if settings.ENVIRONMENT == "production" and use_tls:
             logger.critical("Cannot start gRPC server: Secure configuration failed in production.")
             await stop_grpc_server(); raise RuntimeError("Failed secure gRPC start") from e
        # Fallback for non-prod or non-TLS required scenarios
        logger.warning("Proceeding with potentially insecure gRPC setup due to config error.")
        if not use_tls and not credentials_loaded: # Add insecure port if TLS wasn't attempted or failed non-prod
             try: server.add_insecure_port(listen_addr); credentials_loaded=True
             except Exception as port_err: logger.error(f"Failed to add insecure port after TLS failure: {port_err}")

    if not credentials_loaded: # If neither secure nor insecure port could be added
        logger.critical("Failed to add any gRPC listening port. Server cannot start.")
        await stop_grpc_server()
        return

    # --- Start Server and Wait ---
    try: await server.start(); logger.info(f"gRPC server started successfully on {listen_addr}."); await _stop_event.wait()
    except Exception as e: logger.exception(f"gRPC server runtime error: {e}")
    finally:
        logger.info("gRPC server shutting down...")
        if _server:
             shutdown_grace = float(getattr(settings, "GRPC_SHUTDOWN_GRACE", _fallback_grpc_shutdown_grace) if GRPC_SETTINGS_IMPORTED else _fallback_grpc_shutdown_grace)
             await _server.stop(grace=shutdown_grace); logger.info("gRPC server stopped.")
        _server = None; _stop_event.clear()

async def stop_grpc_server():
    global _server
    if _server and not _stop_event.is_set(): logger.info("Stop signal for gRPC server."); _stop_event.set()
    elif _stop_event.is_set(): logger.debug("gRPC stop already initiated.")
    else: logger.debug("No active gRPC server to stop.")

# Note: This module relies on being imported and called from main app lifecycle.
