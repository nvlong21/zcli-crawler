# Alembic environment configuration script (Dynamically Generated)
import os
import sys
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, engine_from_config
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# --- Project-Specific Setup ---
# Add project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import settings and Base AFTER adjusting path
try:
    from app.config import settings
    from infrastructure.database.base_model import Base # Import your Base
except ImportError as e:
     print(f"[Migrations env.py] ERROR importing project modules: {e}")
     sys.exit(1)

# --- Dynamically Import All SQLAlchemy Models ---
# Ensure Alembic detects all tables defined using the Base metadata.
try:
    print("[Migrations env.py] Importing detected models...")
    # Insert the generated import lines here
    from infrastructure.database.models.orders_model import Uorders
    
    print("[Migrations env.py] Model imports completed.")
except ImportError as e:
    print(f"[Migrations env.py] ERROR importing models: {e}. Check model files and __init__.py.")
    sys.exit(1)

# --- Alembic Configuration ---
config = context.config

# Interpret the config file for Python logging if present
if config.config_file_name:
    fileConfig(config.config_file_name)
else:
    # Basic logging if alembic.ini logging section is not used/found
    import logging
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('alembic').setLevel(logging.INFO)

# --- Target Metadata ---
target_metadata = Base.metadata
print(f"[Migrations env.py] Using metadata from: {Base.__module__}.{Base.__name__}")

# --- Database URL ---
db_url = str(settings.DATABASE_URL)
if not db_url:
    print("[Migrations env.py] ERROR: DATABASE_URL not set in settings.")
    sys.exit(1)
config.set_main_option("sqlalchemy.url", db_url)
print(f"[Migrations env.py] Configured Alembic DB URL (scheme: {settings.DATABASE_URL})")

# --- Migration Runtime Functions ---
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    print("[Migrations env.py] Running migrations offline...")
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"}, compare_type=True, compare_server_default=True,
    )
    with context.begin_transaction(): context.run_migrations()
    print("[Migrations env.py] Offline migrations finished.")

def do_run_migrations(connection) -> None:
    """Helper to configure context and run migrations."""
    context.configure(
        connection=connection, target_metadata=target_metadata,
        compare_type=True, compare_server_default=True,
        # include_schemas=True, # If using schemas
        # version_table_schema=target_metadata.schema, # If needed
    )
    with context.begin_transaction(): context.run_migrations()

async def run_migrations_online_async() -> None:
    """Run migrations in 'online' mode using async engine."""
    print("[Migrations env.py] Running migrations online (async)...")
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"), poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()
    print("[Migrations env.py] Async online migrations finished.")

def run_migrations_online_sync() -> None:
     """Run migrations in 'online' mode using sync engine."""
     print("[Migrations env.py] Running migrations online (sync)...")
     connectable = engine_from_config(
         config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool,
     )
     with connectable.connect() as connection: do_run_migrations(connection)
     print("[Migrations env.py] Sync online migrations finished.")

# --- Main Execution Logic ---
use_async_driver = "aiosqlite" in db_url or "asyncpg" in db_url
if context.is_offline_mode():
    run_migrations_offline()
else:
    if use_async_driver:
        asyncio.run(run_migrations_online_async())
    else:
         run_migrations_online_sync()

print("[Migrations env.py] env.py execution complete.")
