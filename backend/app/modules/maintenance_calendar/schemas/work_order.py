from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MaintenanceWorkOrderType = Literal["preventive", "corrective"]
MaintenanceWorkOrderPriority = Literal["low", "normal", "high", "urgent"]
MaintenanceWorkOrderStatus = Literal[
    "scheduled", "in_progress", "waiting", "completed", "cancelled"
]


class MaintenanceWorkOrderCreate(BaseModel):
    organization_id: UUID
    asset_id: UUID
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=10000)
    work_order_type: MaintenanceWorkOrderType
    priority: MaintenanceWorkOrderPriority = "normal"
    scheduled_at: datetime

    @field_validator("title", "description")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class MaintenanceWorkOrderTransition(BaseModel):
    status: MaintenanceWorkOrderStatus
    completion_note: str | None = Field(default=None, max_length=10000)

    @field_validator("completion_note")
    @classmethod
    def clean_completion_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class MaintenanceWorkOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    asset_id: UUID
    site_id: UUID
    department_id: UUID | None
    created_by: UUID
    work_order_number: str
    title: str
    description: str
    work_order_type: str
    priority: str
    status: str
    scheduled_at: datetime
    completion_note: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MaintenanceWorkOrderListResponse(BaseModel):
    items: list[MaintenanceWorkOrderRead]
    total: int
    offset: int
    limit: int
    has_more: bool
