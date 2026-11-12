from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class ReportCount(BaseModel):
    label: str
    count: int


class ReportDailyTrend(BaseModel):
    date: date
    requests: int
    incidents: int
    work_orders: int


class ReportSummary(BaseModel):
    assets: int
    requests: int
    open_requests: int
    incidents: int
    open_incidents: int
    work_orders: int
    completed_work_orders: int


class ReportsSnapshot(BaseModel):
    generated_at: datetime
    start_date: date
    end_date: date
    site_id: UUID | None
    summary: ReportSummary
    asset_status: list[ReportCount]
    request_status: list[ReportCount]
    incident_severity: list[ReportCount]
    work_order_status: list[ReportCount]
    daily_trend: list[ReportDailyTrend]
