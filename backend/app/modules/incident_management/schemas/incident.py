from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


IncidentSeverity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["reported", "investigating", "resolved", "closed"]
IncidentCategory = Literal[
    "safety",
    "near_miss",
    "equipment_damage",
    "environmental",
    "security",
    "other",
]


class IncidentCreate(BaseModel):
    organization_id: UUID
    site_id: UUID
    department_id: UUID | None = None
    asset_id: UUID | None = None
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=10000)
    category: IncidentCategory = "other"
    severity: IncidentSeverity = "medium"
    occurred_at: datetime

    @field_validator("title", "description")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class IncidentUpdate(BaseModel):
    site_id: UUID | None = None
    department_id: UUID | None = None
    asset_id: UUID | None = None
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=5, max_length=10000)
    category: IncidentCategory | None = None
    severity: IncidentSeverity | None = None
    status: IncidentStatus | None = None
    occurred_at: datetime | None = None
    resolution: str | None = Field(default=None, max_length=10000)

    @field_validator("title", "description")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("resolution")
    @classmethod
    def clean_resolution(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def reject_null_required_updates(self) -> "IncidentUpdate":
        for field in ("title", "description", "category", "severity", "occurred_at"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        return self


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    site_id: UUID
    department_id: UUID | None
    asset_id: UUID | None
    reported_by: UUID
    incident_number: str
    title: str
    description: str
    category: str
    severity: str
    status: str
    occurred_at: datetime
    resolution: str | None
    created_at: datetime
    updated_at: datetime


class IncidentListResponse(BaseModel):
    items: list[IncidentRead]
    total: int
    offset: int
    limit: int
    has_more: bool
