from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssetBase(BaseModel):
    category_id: UUID
    site_id: UUID
    department_id: UUID | None = None
    parent_asset_id: UUID | None = None

    asset_tag: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None

    manufacturer: str | None = Field(default=None, max_length=150)
    model_number: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=150)
    year_manufactured: int | None = Field(default=None, ge=1800, le=2100)

    status: str = "in_service"
    criticality: str = "medium"

    installation_date: date | None = None
    commissioning_date: date | None = None
    warranty_expiry_date: date | None = None

    @field_validator(
        "asset_tag",
        "name",
        "manufacturer",
        "model_number",
        "serial_number",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("asset_tag", "name")
    @classmethod
    def reject_blank_required_text(cls, value):
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        allowed = {
            "in_service",
            "under_maintenance",
            "out_of_service",
            "retired",
        }
        if value not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("criticality")
    @classmethod
    def validate_criticality(cls, value):
        allowed = {"low", "medium", "high", "critical"}
        if value not in allowed:
            raise ValueError(
                f"Criticality must be one of: {', '.join(sorted(allowed))}"
            )
        return value


class AssetCreate(AssetBase):
    organization_id: UUID


class AssetUpdate(BaseModel):
    category_id: UUID | None = None
    site_id: UUID | None = None
    department_id: UUID | None = None
    parent_asset_id: UUID | None = None

    asset_tag: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None

    manufacturer: str | None = Field(default=None, max_length=150)
    model_number: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=150)
    year_manufactured: int | None = Field(default=None, ge=1800, le=2100)

    status: str | None = None
    criticality: str | None = None

    installation_date: date | None = None
    commissioning_date: date | None = None
    warranty_expiry_date: date | None = None

    @field_validator(
        "asset_tag",
        "name",
        "manufacturer",
        "model_number",
        "serial_number",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("asset_tag", "name")
    @classmethod
    def reject_blank_required_text(cls, value):
        if value is not None and not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value is not None and value not in {
            "in_service",
            "under_maintenance",
            "out_of_service",
            "retired",
        }:
            raise ValueError("Invalid asset status.")
        return value

    @field_validator("criticality")
    @classmethod
    def validate_criticality(cls, value):
        if value is not None and value not in {
            "low",
            "medium",
            "high",
            "critical",
        }:
            raise ValueError("Invalid asset criticality.")
        return value


class AssetRead(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssetCategoryCreate(BaseModel):
    organization_id: UUID
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=80)
    description: str | None = None

    @field_validator("name", "code", mode="before")
    @classmethod
    def strip_required_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("name", "code")
    @classmethod
    def reject_blank_text(cls, value):
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class AssetCategoryUpdate(BaseModel):
    """Partial update for an asset category."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value):
        if value is not None and not value:
            raise ValueError("Category name cannot be blank.")
        return value


class AssetCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    code: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

class AssetListResponse(BaseModel):
    """Paginated response for accessible assets."""

    items: list[AssetRead]
    total: int
    offset: int
    limit: int
    page: int
    total_pages: int
    has_more: bool


class AssetCategoryListResponse(BaseModel):
    """Paginated response for organization asset categories."""

    items: list[AssetCategoryRead]
    total: int
    offset: int
    limit: int
    page: int
    total_pages: int
    has_more: bool
