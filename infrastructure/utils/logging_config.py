import logging
import sys
import json # For JSON formatter
import os
from pythonjsonlogger import jsonlogger # Requires: poetry add python-json-logger

# Import settings using getter to handle potential circular imports during init
try:
    from app.config import get_settings
    settings = get_settings()
    PROJECT_NAME = settings.PROJECT_NAME
    ENVIRONMENT = settings.ENVIRONMENT
except ImportError:
    # Fallback if settings cannot be imported (e.g., during early init or tests)
    print("[Logging Config] Warning: Could not import app settings. Using fallback defaults.")
    PROJECT_NAME = os.getenv("PROJECT_NAME", "fastapi_app")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    # Define fallback get_settings if needed by other modules importing this early
    class FallbackSettings:
        PROJECT_NAME=PROJECT_NAME; ENVIRONMENT=ENVIRONMENT
    def get_settings(): return FallbackSettings()

# Determine log level from environment or config
log_level_str = os.getenv("LOG_LEVEL", "DEBUG" if ENVIRONMENT == "development" else "INFO").upper()
# Validate log level string
valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if log_level_str not in valid_log_levels:
    print(f"[Logging Config] Warning: Invalid LOG_LEVEL '{log_level_str}'. Defaulting to INFO.")
    log_level_str = "INFO"
log_level = logging.getLevelName(log_level_str)


# --- Configure Logger (Root or Specific) ---
# Option 1: Configure a specific logger for the project
# logger = logging.getLogger(PROJECT_NAME)

# Option 2: Configure the root logger (affects libraries unless they have specific handlers)
logger = logging.getLogger() # Get root logger
logger.setLevel(log_level)

# Prevent adding handlers multiple times (e.g., during reloads)
if logger.hasHandlers():
    # In simple cases, removing might be okay, but be cautious if other systems add handlers.
    # A more robust approach is to check if *this specific handler type* already exists.
    # For now, we assume this setup is the primary one.
    print("[Logging Config] Logger already has handlers. Clearing existing handlers.")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

# --- Choose and Configure Formatter/Handler ---

# Default to JSON logging
USE_JSON_LOGGING = os.getenv("USE_JSON_LOGGING", "true").lower() == "true"

log_handler = logging.StreamHandler(sys.stdout) # Log to stdout

if USE_JSON_LOGGING:
    # JSON Formatter (Recommended for production/containers)
    # Add '%(request_id)s' if using RequestIdLogFilter
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] %(message)s',
        # Example: '%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        rename_fields={'levelname': 'level'},
    )
    print(f"[Logging Config] Using JSON formatter. Root level: {log_level_str}")
else:
    # Basic Console Formatter (Simpler for local dev)
    formatter = logging.Formatter(
        "%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s:%(lineno)d) - %(message)s"
    )
    print(f"[Logging Config] Using basic console formatter. Root level: {log_level_str}")

log_handler.setFormatter(formatter)
logger.addHandler(log_handler)

# --- Optional: Add Request ID Filter ---
# Must be done *after* adding the handler
# from .logging_middleware import RequestIdLogFilter # Assuming filter is in middleware file
# logger.addFilter(RequestIdLogFilter())

# --- Set Log Levels for Third-Party Libraries ---
third_party_log_level_str = os.getenv("THIRD_PARTY_LOG_LEVEL", "WARNING" if ENVIRONMENT != "development" else "INFO").upper()
if third_party_log_level_str not in valid_log_levels: third_party_log_level_str = "WARNING"
third_party_log_level = logging.getLevelName(third_party_log_level_str)

print(f"[Logging Config] Setting third-party library log level to: {third_party_log_level_str}")
logging.getLogger("uvicorn").setLevel(third_party_log_level)
logging.getLogger("uvicorn.error").setLevel(logging.INFO) # Keep uvicorn errors more visible
logging.getLogger("uvicorn.access").setLevel(third_party_log_level) # Access logs often verbose
logging.getLogger("sqlalchemy").setLevel(third_party_log_level)
# Uncomment to see SQL queries in dev:
# if ENVIRONMENT == "development": logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
logging.getLogger("alembic").setLevel(logging.INFO) # Keep alembic info
logging.getLogger("httpx").setLevel(third_party_log_level)
logging.getLogger("httpcore").setLevel(third_party_log_level)
logging.getLogger("redis").setLevel(third_party_log_level)
logging.getLogger("passlib").setLevel(logging.WARNING) # Reduce passlib verbosity

# Example log to confirm setup
# logger.info(f"Logging initialized for '{PROJECT_NAME}'. Level: {log_level_str}. Env: {ENVIRONMENT}.")
