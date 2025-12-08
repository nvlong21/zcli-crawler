from sqlalchemy.orm import declarative_base, Mapped, mapped_column, DeclarativeBase
from sqlalchemy import MetaData, func, DateTime # Add DateTime and func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID # Example for PG UUID
from sqlalchemy import TypeDecorator, CHAR # For generic UUID type
import uuid # Import Python's uuid module

from datetime import datetime, timezone # Import timezone
from typing import Any

# Define naming conventions for database constraints for consistency
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Create metadata with the naming convention
metadata_obj = MetaData(naming_convention=convention)

# --- Generic UUID Type ---
class UUIDType(TypeDecorator):
    impl = CHAR(32) # Default fallback to CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        # Add checks for other dialects with native UUID support (MySQL, SQL Server)
        # elif dialect.name == 'mysql': return dialect.type_descriptor(CHAR(36)) # Example MySQL UUID stores as CHAR(36)
        else:
            return dialect.type_descriptor(CHAR(32)) # Store as hex without dashes

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value) # PG driver handles UUID object when as_uuid=True
        else:
            if isinstance(value, uuid.UUID):
                return value.hex # Store as hex string without dashes
            else: # Try to convert if it's a string representation
                try: return uuid.UUID(value).hex
                except (ValueError, TypeError, AttributeError): return value # Pass invalid value to DB

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        # For PG with as_uuid=True, value should already be a UUID object
        if isinstance(value, uuid.UUID):
            return value
        # For other dialects or if PG returns string, try converting hex/string to UUID
        try:
             # Try parsing hex first (CHAR(32)) then standard format (CHAR(36))
             if len(str(value)) == 32: return uuid.UUID(hex=str(value))
             else: return uuid.UUID(str(value))
        except (ValueError, TypeError, AttributeError):
             # Return original value if conversion fails
             return value

# --- Base Class for Models ---
class Base(DeclarativeBase):
    """Base class for SQLAlchemy models using Declarative Mapping with Type Annotation."""
    __abstract__ = True
    metadata = metadata_obj # Associate metadata for Alembic and naming conventions

    # Define common columns using Mapped and mapped_column
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Define type annotation map for custom types like UUIDType
    # Ensures Mapped[uuid.UUID] uses our custom type decorator
    type_annotation_map = {
        uuid.UUID: UUIDType
    }
