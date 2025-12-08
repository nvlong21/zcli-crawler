from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime

class User(BaseModel):
    """Domain Model for a User."""
    model_config = ConfigDict(from_attributes=True, validate_assignment=True, extra='ignore')
    id: UUID = Field(default_factory=uuid4)
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    roles: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
