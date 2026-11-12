from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


SynchronizationOperationType = Literal[
    "service_request.create",
    "service_request.transition",
    "incident.create",
    "incident.update",
    "maintenance_work_order.create",
    "maintenance_work_order.transition",
]


class SynchronizationOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: UUID
    organization_id: UUID
    operation_type: SynchronizationOperationType
    record_id: UUID | None = None
    created_at: datetime
    payload: dict[str, Any]


class SynchronizationOperationResult(BaseModel):
    operation_id: UUID
    status: Literal["synced"] = "synced"
    duplicate: bool = False
    result: dict[str, Any]
