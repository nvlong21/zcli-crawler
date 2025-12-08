from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.config import settings
from infrastructure.utils.logging_config import logger

# Determine if using async based on URL scheme/driver
db_url_str = str(settings.DATABASE_URL)  # Ensure it's a string
use_async = "sqlite+aiosqlite" in db_url_str or "postgresql+asyncpg" in db_url_str

# Initialize placeholders for engine and session factories
SessionLocal: Optional[sessionmaker[Session]] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None
sync_engine = None  # Will be set to Engine if sync
async_engine = None  # Will be set to AsyncEngine if async

@event.listens_for(Engine, "connect") # Hook vào sự kiện connect của *bất kỳ* Engine nào
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Applies PRAGMA settings for SQLite connections."""
    # Lấy engine từ connection_record hoặc dbapi_connection (tùy phiên bản/context)
    # Cách an toàn là kiểm tra dialect của engine được liên kết
    # Trong context sync, dbapi_connection.engine hoặc connection_record.creator().engine thường có sẵn
    # Trong context async, mọi thứ phức tạp hơn. Cách tiếp cận đơn giản nhất là kiểm tra trực tiếp dbapi_connection
    # nếu nó là đối tượng connection của sqlite3.
    # Hoặc, chỉ áp dụng nếu engine tương ứng (sync_engine/async_engine) là SQLite.

    is_sqlite = False
    if sync_engine and sync_engine.dialect.name == "sqlite":
        # Nếu đây là kết nối từ sync_engine và là sqlite
        is_sqlite = True
    elif async_engine and async_engine.dialect.name == "sqlite":
        # Nếu đây là kết nối từ async_engine và là sqlite
        # Lưu ý: AsyncEngine cũng có thuộc tính dialect
        is_sqlite = True
    # Fallback check nếu engine không rõ ràng (ít xảy ra với hook này)
    elif hasattr(dbapi_connection, "execute"): # Check if it looks like a DBAPI connection
         try:
             # Cố gắng thực thi một lệnh chỉ hoạt động trên SQLite
             cur = dbapi_connection.cursor()
             cur.execute("SELECT sqlite_version()")
             is_sqlite = True
             cur.close()
             logger.debug("Detected SQLite via version check.")
         except Exception:
             is_sqlite = False # Không phải SQLite hoặc lỗi khác

    if is_sqlite:
        logger.debug("Applying SQLite PRAGMA settings...")
        cursor = None # Khởi tạo cursor là None
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout = 5000;") # Wait 5s if locked
            cursor.execute("PRAGMA synchronous = NORMAL;")
            # cursor.execute("PRAGMA foreign_keys = ON;") # Bật foreign key constraints nếu cần
            logger.info("SQLite PRAGMAs applied: journal_mode=WAL, busy_timeout=5000, synchronous=NORMAL")
        except Exception as e:
             logger.error(f"Failed to set SQLite PRAGMAs: {e}", exc_info=True)
        finally:
             if cursor:
                 cursor.close()
    # else: # Log nếu không phải sqlite (optional)
    #     logger.debug("Skipping SQLite PRAGMAs for non-SQLite connection.")

try:
    if use_async:
        logger.info(f"Initializing Async Database Engine for: {db_url_str}...")
        from sqlalchemy.ext.asyncio import AsyncEngine
        async_engine: AsyncEngine = create_async_engine(
            db_url_str,
            echo=(settings.ENVIRONMENT == "development"),  # Log SQL in dev
            pool_pre_ping=True,
            pool_size=getattr(settings, "DB_POOL_SIZE", 5),
            max_overflow=getattr(settings, "DB_MAX_OVERFLOW", 10),
        )
        AsyncSessionLocal = async_sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        logger.info("Async Database Engine and AsyncSessionLocal configured.")
    else:
        logger.info(f"Initializing Sync Database Engine for: {db_url_str}...")
        from sqlalchemy import Engine
        sync_engine: Engine = create_engine(
            db_url_str,
            echo=(settings.ENVIRONMENT == "development"),
            pool_pre_ping=True,
            pool_size=getattr(settings, "DB_POOL_SIZE", 5),
            max_overflow=getattr(settings, "DB_MAX_OVERFLOW", 10),
        )
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=sync_engine,
            class_=Session
        )
        logger.info("Sync Database Engine and SessionLocal configured.")

except Exception as e:
    logger.exception(f"FATAL: Database initialization failed: {e}")
    raise RuntimeError(f"Database initialization failed: {e}") from e

# --- Table Creation Functions (for tests/initial setup) ---
async def create_db_and_tables_async():
    """Creates all tables defined in Base metadata (async version)."""
    if not async_engine:
        logger.error("Async engine not initialized, cannot create tables.")
        return
    from .base_model import Base  # Import Base here
    logger.info("Attempting to create database tables (async)...")
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created successfully (async).")
    except Exception as e:
        logger.exception(f"Failed to create tables (async): {e}")

def create_db_and_tables_sync():
    """Creates all tables defined in Base metadata (sync version)."""
    if not sync_engine:
        logger.error("Sync engine not initialized, cannot create tables.")
        return
    from .base_model import Base  # Import Base here
    logger.info("Attempting to create database tables (sync)...")
    try:
        Base.metadata.create_all(bind=sync_engine)
        logger.info("Tables created successfully (sync).")
    except Exception as e:
        logger.exception(f"Failed to create tables (sync): {e}")

# --- Engine Disposal Function (called during application shutdown) ---
async def close_db_connections():
    """Dispose of database engine connections."""
    if async_engine:
        logger.info("Disposing async database engine...")
        await async_engine.dispose()
        logger.info("Async database engine disposed.")
    if sync_engine:
        logger.info("Disposing sync database engine...")
        sync_engine.dispose()  # Sync dispose is synchronous
        logger.info("Sync database engine disposed.")
