from sqlalchemy import String, Text, ForeignKey # Add other types as needed
from sqlalchemy.orm import Mapped, mapped_column, relationship
# Use specific UUID type if needed, or rely on Base's type_annotation_map
# from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import UUID as PythonUUID
from typing import Optional, TYPE_CHECKING

# Import Base and custom types from common location
from infrastructure.database.base_model import Base #, UUIDType

# Example relationship import (adjust based on actual relationships)
# if TYPE_CHECKING:
#     from .user_model import User # Import related model for type hinting

class Orders(Base):
    """SQLAlchemy ORM Model for the 'orders' table."""
    __tablename__ = "orders" # Database table name

    # Primary Key - Use uuid.UUID type hint, rely on Base's type_annotation_map for DB type
    id: Mapped[PythonUUID] = mapped_column(primary_key=True, default=PythonUUID, index=True)

    # Columns based on domain entity fields
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps (created_at, updated_at) are inherited from the Base class

    # --- Example Relationships ---
    # owner_id: Mapped[PythonUUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # owner: Mapped["User"] = relationship(back_populates="orders")

    def __repr__(self) -> str:
        return f"<Orders(id={self.id!r}, name={self.name!r})>"
