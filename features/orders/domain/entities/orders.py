from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime

# --- Optional Imports ---
# Import Value Objects if used
# from .value_objects import UordersAttribute

# Import Base Domain Event class if using domain events
# from infrastructure.bus.domain_event import DomainEvent # Example path

class Uorders(BaseModel):
    """
    Domain Model representing a Uorders.
    This class defines the structure and invariants for a orders.
    It should contain business logic specific to the entity itself.
    """
    # Pydantic V2 configuration
    model_config = ConfigDict(
        from_attributes=True,       # Allow creating from ORM models
        validate_assignment=True,   # Validate fields on assignment
        extra='forbid',             # Disallow fields not defined here
        # arbitrary_types_allowed=True, # If using non-standard types like DomainEvents
    )

    # --- Fields ---
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Name of the orders")
    description: Optional[str] = Field(None, description="Optional description")

    # Example Value Object field
    # attribute: UordersAttribute

    # Timestamps are often managed by the database/BaseModel,
    # but can be included if needed for domain logic or validation.
    # They are populated when mapping from the DB model.
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    # --- Domain Events (Optional Example) ---
    # _domain_events: List[DomainEvent] = PrivateAttr(default_factory=list)
    #
    # def register_event(self, event: DomainEvent):
    #     self._domain_events.append(event)
    #
    # def pull_domain_events(self) -> List[DomainEvent]:
    #     events = list(self._domain_events)
    #     self._domain_events.clear()
    #     return events

    # --- Domain Logic Methods ---
    # Example: Method enforcing a business rule
    def update_name(self, new_name: str):
        """Updates the name if it meets validation criteria."""
        if not new_name or len(new_name) > 100:
            raise ValueError("Invalid name provided.")
        if new_name != self.name:
             self.name = new_name
             # Optionally register a domain event
             # self.register_event(UordersNameChanged(id=self.id, new_name=new_name))
        return self

    # Add other methods embodying business logic specific to this entity...
