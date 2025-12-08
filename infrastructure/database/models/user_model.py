from sqlalchemy import String, Boolean, JSON # Use JSON for roles list
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID as PythonUUID, uuid4
from typing import List

from infrastructure.database.base_model import Base, UUIDType # Use custom UUIDType

class User(Base):
    __tablename__ = "users"
    id: Mapped[PythonUUID] = mapped_column(UUIDType, primary_key=True, default=uuid4, index=True) # Use UUIDType
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    roles: Mapped[List[str]] = mapped_column(JSON, default=[], nullable=False, server_default='[]')
    # Timestamps inherited
    def __repr__(self): return f"<User(id={self.id!r}, username='{self.username!r}')>"
