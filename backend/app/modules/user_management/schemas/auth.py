from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=150)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("A display name is required.")
        value = value.strip()
        if not value:
            raise ValueError("A display name is required.")
        return value
