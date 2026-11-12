from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SiteOperationsMapRead(BaseModel):
    site_id: UUID
    name: str
    code: str
    address: str | None
    assets: int
    asset_status: dict[str, int]
    open_requests: int
    open_incidents: int
    high_severity_incidents: int
    open_work_orders: int
    overdue_work_orders: int


class OperationsMapSummary(BaseModel):
    sites: int
    assets: int
    open_requests: int
    open_incidents: int
    overdue_work_orders: int


class OperationsMapRead(BaseModel):
    generated_at: datetime
    summary: OperationsMapSummary
    sites: list[SiteOperationsMapRead]
