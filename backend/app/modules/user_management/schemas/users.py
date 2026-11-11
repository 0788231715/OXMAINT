import re
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class UserRegistrationInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=150)
    initial_password: str = Field(min_length=12, max_length=128)
    site_ids: list[UUID] = Field(min_length=1, max_length=50)
    department_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("A valid email address is required.")
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("A valid email address is required.")
        return value

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("A display name is required.")
        value = value.strip()
        if not value:
            raise ValueError("A display name is required.")
        return value

    @field_validator("site_ids", "department_ids")
    @classmethod
    def require_unique_ids(cls, values: list[UUID]) -> list[UUID]:
        if len(values) != len(set(values)):
            raise ValueError("Duplicate location IDs are not allowed.")
        return values


class UserRegistrationRead(BaseModel):
    id: UUID
    email: str
    display_name: str
    role_code: str
    organization_id: UUID