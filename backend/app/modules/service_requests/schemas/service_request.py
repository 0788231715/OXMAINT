from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

RequestPriority = Literal["low", "normal", "high", "urgent"]

RequestStatus = Literal[
    "submitted",
    "under_review",
    "approved",
    "assigned",
    "in_progress",
    "waiting",
    "completed",
    "closed",
    "rejected",
    "cancelled",
]

ApprovalDecision = Literal["approved", "rejected"]

TransitionStatus = Literal[
    "assigned",
    "in_progress",
    "waiting",
    "completed",
    "closed",
    "cancelled",
]

class ServiceRequestCreate(BaseModel):
    organization_id: UUID
    site_id: UUID
    department_id: UUID | None = None
    asset_id: UUID | None = None

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=10000)
    category: str = Field(min_length=2, max_length=50)
    priority: RequestPriority = "normal"
    safety_critical: bool = False

    @field_validator("title", "description", "category")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

class ServiceRequestUpdate(BaseModel):
    site_id: UUID | None = None
    department_id: UUID | None = None
    asset_id: UUID | None = None

    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=5, max_length=10000)
    category: str | None = Field(default=None, min_length=2, max_length=50)
    priority: RequestPriority | None = None
    safety_critical: bool | None = None

    @field_validator("title", "description", "category")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

class ServiceRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    site_id: UUID
    department_id: UUID | None
    asset_id: UUID | None
    requester_id: UUID

    request_number: str
    title: str
    description: str
    category: str
    priority: str
    safety_critical: bool
    status: str

    resolution: str | None
    rejection_reason: str | None
    cancellation_reason: str | None

    reviewed_by: UUID | None
    reviewed_at: datetime | None

    submitted_at: datetime
    completed_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

class ServiceRequestListResponse(BaseModel):
    items: list[ServiceRequestRead]
    total: int
    offset: int
    limit: int

class RequestReviewInput(BaseModel):
    review_note: str | None = Field(default=None, max_length=3000)

    @field_validator("review_note")
    @classmethod
    def clean_review_note(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None

class RequestAssignmentCreate(BaseModel):
    assigned_to: UUID
    assignment_note: str | None = Field(default=None, max_length=3000)

    @field_validator("assignment_note")
    @classmethod
    def clean_assignment_note(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None

class RequestApprovalInput(BaseModel):
    decision: ApprovalDecision
    decision_note: str | None = Field(default=None, max_length=3000)

    @field_validator("decision_note")
    @classmethod
    def clean_decision_note(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None

class RequestRejectionInput(BaseModel):
    reason: str = Field(min_length=3, max_length=3000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A rejection reason is required.")
        return value

class RequestStatusTransitionInput(BaseModel):
    new_status: TransitionStatus
    reason: str | None = Field(default=None, max_length=3000)
    resolution: str | None = Field(default=None, max_length=10000)

    @field_validator("reason", "resolution")
    @classmethod
    def clean_optional_reason(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None

class RequestCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment content cannot be blank.")
        return value

class RequestCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    author_id: UUID
    content: str
    created_at: datetime

class RequestAttachmentMetadataCreate(BaseModel):
    original_filename: str = Field(min_length=1, max_length=255)
    storage_key: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=1, max_length=150)
    size_bytes: int = Field(gt=0)

class RequestAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    uploaded_by: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
