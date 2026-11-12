from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.modules.maintenance_calendar.schemas.work_order import (
    MaintenanceWorkOrderRead,
)


class WorkOrderAssignmentCreate(BaseModel):
    assigned_to: UUID
    handoff_note: str | None = Field(default=None, max_length=5000)

    @field_validator("handoff_note")
    @classmethod
    def clean_handoff_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class WorkOrderAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_order_id: UUID
    assigned_to: UUID
    assigned_by: UUID
    assignee_name: str
    assigner_name: str
    handoff_note: str | None
    assigned_at: datetime


class CoordinationWorkOrderRead(BaseModel):
    work_order: MaintenanceWorkOrderRead
    current_assignment: WorkOrderAssignmentRead | None


class CoordinationWorkOrderListResponse(BaseModel):
    items: list[CoordinationWorkOrderRead]
    total: int
    offset: int
    limit: int
    has_more: bool


class CoordinationTechnicianRead(BaseModel):
    id: UUID
    display_name: str
    email: str


class WorkOrderAssignmentHistoryResponse(BaseModel):
    items: list[WorkOrderAssignmentRead]
