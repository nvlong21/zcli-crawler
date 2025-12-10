import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any # Added Any for BaseAppException detail

from fastapi import FastAPI, Request, status, HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# from fastapi.middleware.trustedhost import TrustedHostMiddleware # Optional

# --- Core Application Imports ---
# Use try-except for robustness during template generation/testing
try:
    from app.config import settings
    from infrastructure.utils.logging_config import logger
    from app.exceptions import BaseAppException # Chỉ import Base là đủ cho handler chính
    from infrastructure.middleware.logging_middleware import LoggingMiddleware
    from infrastructure.cache.factory import close_cache_connections
    from infrastructure.database.session import close_db_connections, create_db_and_tables_async, create_db_and_tables_sync

    # from infrastructure.external_services.factory import close_all_external_clients
    # from .grpc_server import serve_grpc, stop_grpc_server
    CORE_IMPORTS_OK = True
except ImportError as e:
    print(f"[main.py] CRITICAL IMPORT ERROR: {e}. Cannot start application.")
    # Có thể exit ở đây hoặc để FastAPI tự lỗi khi khởi chạy
    # exit(1) # Thoát ngay nếu import cốt lõi thất bại
    # Hoặc định nghĩa các fallback tối thiểu để template hợp lệ, nhưng sẽ lỗi runtime
    logger = logging.getLogger("main_fallback_critical"); logger.addHandler(logging.StreamHandler())
    logger.critical(f"Core module import failed: {e}. Application will likely fail.")
    class SettingsFallback: PROJECT_NAME="FAILED_LOAD"; VERSION="0.0.0"; ENVIRONMENT="error"; API_V1_STR="/api/v1"; CORS_ORIGINS=[]
    settings = SettingsFallback()
    class BaseAppException(Exception): status_code=500; detail="Config Error"
    class LoggingMiddleware: # Dummy
        def __init__(self, app): self.app = app
        async def __call__(self, scope, receive, send): await self.app(scope, receive, send)
    async def close_cache_connections(): pass
    async def close_db_connections(): pass
    CORE_IMPORTS_OK = False # Đánh dấu import thất bại

# --- API Router Imports ---
from features.audio_crawl.presentation.api.v1.audio_crawl_api import router as audio_crawl_router
from features.users.presentation.api.v1.auth_api import router as auth_router                 
from features.users.presentation.api.v1.users_api import router as users_crud_router                 
from features.orders.presentation.api.v1.orders_api import router as orders_router# Example: from features.users.presentation.api.v0.users_api import router as users_router
# Example: from features.users.presentation.api.v0.auth_api import router as auth_router

# --- Application Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.info(f"Starting up {settings.PROJECT_NAME} v{settings.VERSION} (Env: {settings.ENVIRONMENT})...")
    # --- Startup Actions ---
    startup_checks_passed = True
    try:
        # Example: Check DB connection readiness (lightweight check)
        # Relying on pool pre-ping or initial config load success might be enough.
        # Add a specific check like `SELECT 1` if needed.
        logger.info("Database connections seem available (based on config load/pre-ping).")
    except Exception as e:
        logger.critical(f"Database check failed on startup: {e}", exc_info=True)
        startup_checks_passed = False

    try:
        # Example: Check Cache connection readiness
        from infrastructure.cache.factory import get_cache
        cache = get_cache()
        if not await cache.ping(): raise ConnectionError("Cache ping failed")
        logger.info(f"Cache ({type(cache).__name__}) connection check successful.")
    except Exception as e:
        # Decide if cache failure is critical
        logger.error(f"Cache connection check failed on startup: {e}", exc_info=True)
        # startup_checks_passed = False # Uncomment if cache is critical

    if not startup_checks_passed:
        raise RuntimeError("Application startup failed due to unmet critical dependencies.")

    # Example: Start background gRPC server
    # grpc_server_task = None
    # if getattr(settings, 'ENABLE_GRPC_SERVER', False):
    #      grpc_server_task = asyncio.create_task(serve_grpc())
    #      logger.info("gRPC server starting in background...")

    logger.info("Application startup sequence finished.")
    yield # Application runs here
    # --- Shutdown Actions ---
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")

    # Example: Stop background gRPC server
    # if grpc_server_task:
    #     logger.info("Stopping gRPC server...")
    #     await stop_grpc_server()
    #     try: await asyncio.wait_for(grpc_server_task, timeout=5.0)
    #     except asyncio.TimeoutError: logger.warning("gRPC server shutdown timed out.")
    #     except Exception as e: logger.error(f"Error during gRPC server shutdown: {e}", exc_info=True)

    # Close connections gracefully
    await close_cache_connections()
    await close_db_connections()
    # await close_all_external_clients() # If implemented

    logger.info("Application shutdown complete.")

# --- FastAPI App Instance ---
# Configure OpenAPI/Docs URLs based on environment
openapi_url = f"{settings.API_V1_STR}/openapi.json" if settings.ENVIRONMENT != 'production' else None
docs_url = "/docs" if settings.ENVIRONMENT != 'production' else None
redoc_url = "/redoc" if settings.ENVIRONMENT != 'production' else None
if settings.POSTGRES_ASYNC_ENABLED:
    create_db_and_tables_async()
else:
    create_db_and_tables_sync()
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="FastAPI project generated by script", # Placeholder replaced here
    version=settings.VERSION,
    openapi_url=openapi_url,
    docs_url=docs_url,
    redoc_url=redoc_url,
    lifespan=lifespan,
    # root_path=settings.ROOT_PATH, # If running behind reverse proxy with path prefix
    # --- Add other OpenAPI metadata ---
    # contact={"name": "API Support", "email": "dev@example.com"},
    # license_info={"name": "Apache 2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0.html"},
)

# --- Middleware Configuration (Order matters!) ---

# 0. Trusted Hosts (Security - uncomment and configure properly in production)
# from fastapi.middleware.trustedhost import TrustedHostMiddleware
# app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*.example.com", "localhost", "127.0.0.1"]) # Example

# 1. CORS Middleware
if settings.CORS_ORIGINS:
    logger.info(f"Configuring CORS for origins: {settings.CORS_ORIGINS}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS], # Ensure strings
        allow_credentials=True,
        allow_methods=["*"], # Or specify ["GET", "POST", ...]
        allow_headers=["*"], # Or specify specific headers
    )
else:
     logger.warning("CORS is not configured (CORS_ORIGINS not set). Cross-origin requests may be blocked.")

# 2. Logging Middleware (Adds request ID, logs summary)
app.add_middleware(LoggingMiddleware)

# 3. GZip Middleware (Compresses large responses)
app.add_middleware(GZipMiddleware, minimum_size=500) # Adjust minimum size if needed


# --- Custom Exception Handlers ---
# These provide consistent JSON error responses.

@app.exception_handler(BaseAppException) # Catch custom app exceptions
async def base_app_exception_handler(request: Request, exc: BaseAppException):
    req_id = getattr(request.state, 'request_id', None)
    lvl = logging.INFO if exc.status_code < 500 else logging.ERROR
    logger.log(lvl, f"Handled App Exception: {type(exc).__name__}({exc.status_code}) - {exc.detail}", extra={"request_id": req_id})
    content_detail: Any = exc.detail
    return JSONResponse(status_code=exc.status_code, content={"detail": content_detail}, headers=getattr(exc, 'headers', None))

@app.exception_handler(FastAPIHTTPException) # Catch FastAPI/Starlette HTTP exceptions
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    req_id = getattr(request.state, 'request_id', None)
    lvl = logging.WARNING if 400 <= exc.status_code < 500 else logging.ERROR
    logger.log(lvl, f"HTTPException: {exc.status_code} - {exc.detail}", extra={"request_id": req_id})
    content_detail: Any = exc.detail
    return JSONResponse(status_code=exc.status_code, content={"detail": content_detail}, headers=exc.headers)

@app.exception_handler(RequestValidationError) # Catch Pydantic validation errors
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, 'request_id', None)
    # Log a summary instead of the full potentially large errors list
    error_summary = [{"loc": str(err.get("loc")), "msg": err.get("msg"), "type": err.get("type")} for err in exc.errors()]
    logger.warning("Request validation failed", extra={"request_id": req_id, "url": str(request.url), "method": request.method, "errors_summary": error_summary})
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors()}) # Return full errors

@app.exception_handler(Exception) # Generic fallback for unexpected errors
async def generic_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, 'request_id', None)
    logger.exception(f"Unhandled Server Exception (ID: {req_id})", exc_info=exc, extra={"request_id": req_id, "url": str(request.url), "method": request.method})
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "An internal server error occurred."})

# --- API Router Includes ---
# Feature routers are included here. The generator script adds lines below the marker.

app.include_router(audio_crawl_router, prefix=settings.API_V1_STR)   
app.include_router(users_crud_router, prefix=settings.API_V1_STR)               
app.include_router(auth_router, prefix=settings.API_V1_STR)                 
app.include_router(orders_router, prefix=settings.API_V1_STR)


# --- Root Endpoint & Health Check ---
@app.get("/", tags=["_Service"], include_in_schema=False)
async def root_endpoint():
    """Redirects root path to API documentation (if enabled)."""
    if docs_url:
        return RedirectResponse(url=docs_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    else:
        return {"message": f"Welcome to the {settings.PROJECT_NAME} API!"}

@app.get("/health", tags=["_Service"], status_code=status.HTTP_200_OK)
async def health_check_endpoint() -> Dict[str, str]:
    """Performs a basic health check of the service."""
    # TODO: Add more comprehensive checks (DB, Cache pings) if needed
    # Ensure checks are lightweight and have timeouts.
    # Example:
    # try:
    #     await get_cache().ping() # Assuming ping is implemented and fast
    #     # Add DB ping if necessary
    # except Exception as e:
    #     logger.error(f"Health check dependency failure: {e}")
    #     raise HTTPException(status_code=503, detail="Service Unavailable")
    return {"status": "ok", "version": settings.VERSION, "environment": settings.ENVIRONMENT}

# --- Main execution block (for development server) ---
if __name__ == "__main__":
    import uvicorn
    from infrastructure.crawler import create_application
    logger.info("Starting Uvicorn directly for development...")
    # Use os.getenv to make host/port configurable via environment
    run_host = os.getenv("HOST", "0.0.0.0")
    run_port = int(os.getenv("PORT", "8008"))
    app = create_application()
    videoEntries = app.youtube_search("politics", 2)
    # video_ids = app.bilibili_search("politics", 1)
    uniqueIds = app.filter_duplicate(videoEntries)
    # print(uniqueIds)
    asyncio.run(app.download_and_upload_audio(uniqueIds)) 

    uvicorn.run(
        "presentation.main:app", # Path to the FastAPI app instance
        host=run_host,
        port=8008,
        reload=(settings.ENVIRONMENT == "development"), # Enable auto-reload in dev
        log_config=None, # Use logger configured via logging_config.py
        # workers=1 # Keep workers=1 for reload mode
    )
