from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


InsightCategory = Literal[
    "assets",
    "service_requests",
    "safety",
    "maintenance",
]
InsightSeverity = Literal["info", "attention", "urgent"]


class GenerateInsightsRequest(BaseModel):
    start_date: date
    end_date: date
    site_id: UUID | None = None
    confirm_external_processing: Literal[True]


class OperationalInsight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=120)
    category: InsightCategory
    severity: InsightSeverity
    evidence: list[str] = Field(min_length=1, max_length=3)
    recommendation: str = Field(min_length=5, max_length=500)


class OperationalInsights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insights: list[OperationalInsight] = Field(max_length=5)


class GeneratedInsightsResponse(BaseModel):
    generated_at: datetime
    start_date: date
    end_date: date
    site_id: UUID | None
    model: str
    insights: list[OperationalInsight]
