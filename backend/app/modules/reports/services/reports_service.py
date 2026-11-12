from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.database.models.asset import Asset
from backend.app.database.models.incident import Incident
from backend.app.database.models.maintenance_work_order import (
    MaintenanceWorkOrder,
)
from backend.app.database.models.organization import Site
from backend.app.database.models.service_request import ServiceRequest
from backend.app.modules.user_management.services.data_scope_service import (
    organization_record_scope,
)


ASSET_STATUSES = (
    "in_service",
    "under_maintenance",
    "out_of_service",
    "retired",
)
REQUEST_STATUSES = (
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
)
INCIDENT_SEVERITIES = ("critical", "high", "medium", "low")
WORK_ORDER_STATUSES = (
    "scheduled",
    "in_progress",
    "waiting",
    "completed",
    "cancelled",
)
OPEN_REQUEST_STATUSES = (
    "submitted",
    "under_review",
    "approved",
    "assigned",
    "in_progress",
    "waiting",
)


def _counts_by(
    db: Session,
    field,
    conditions: list,
    values: tuple[str, ...],
    date_field=None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> tuple[dict[str, int], int]:
    statement = select(field, func.count()).where(*conditions)
    if date_field is not None:
        statement = statement.where(
            date_field >= start_at,
            date_field < end_at,
        )
    grouped = {
        str(label): count
        for label, count in db.execute(statement.group_by(field)).all()
    }
    return (
        {value: grouped.get(value, 0) for value in values},
        sum(grouped.values()),
    )


def _daily_counts(
    db: Session,
    date_field,
    conditions: list,
    start_at: datetime,
    end_at: datetime,
) -> dict[date, int]:
    rows = db.execute(
        select(func.date(date_field), func.count())
        .where(
            *conditions,
            date_field >= start_at,
            date_field < end_at,
        )
        .group_by(func.date(date_field))
    ).all()
    return {
        (
            value
            if isinstance(value, date)
            else date.fromisoformat(str(value)[:10])
        ): count
        for value, count in rows
    }


def build_reports_snapshot(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    start_date: date,
    end_date: date,
    site_id: UUID | None = None,
) -> dict:
    start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_at = datetime.combine(
        end_date + timedelta(days=1), time.min, tzinfo=timezone.utc
    )

    asset_conditions = organization_record_scope(
        Asset, user_id, organization_id, site_id
    ) + [Asset.is_active.is_(True)]
    request_conditions = organization_record_scope(
        ServiceRequest, user_id, organization_id, site_id
    )
    incident_conditions = organization_record_scope(
        Incident, user_id, organization_id, site_id
    )
    work_order_conditions = organization_record_scope(
        MaintenanceWorkOrder, user_id, organization_id, site_id
    )

    asset_status, asset_total = _counts_by(
        db, Asset.status, asset_conditions, ASSET_STATUSES
    )
    request_status, request_total = _counts_by(
        db,
        ServiceRequest.status,
        request_conditions,
        REQUEST_STATUSES,
        ServiceRequest.submitted_at,
        start_at,
        end_at,
    )
    incident_severity, incident_total = _counts_by(
        db,
        Incident.severity,
        incident_conditions,
        INCIDENT_SEVERITIES,
        Incident.occurred_at,
        start_at,
        end_at,
    )
    incident_status, _ = _counts_by(
        db,
        Incident.status,
        incident_conditions,
        ("reported", "investigating", "resolved", "closed"),
        Incident.occurred_at,
        start_at,
        end_at,
    )
    work_order_status, work_order_total = _counts_by(
        db,
        MaintenanceWorkOrder.status,
        work_order_conditions,
        WORK_ORDER_STATUSES,
        MaintenanceWorkOrder.scheduled_at,
        start_at,
        end_at,
    )

    request_trend = _daily_counts(
        db,
        ServiceRequest.submitted_at,
        request_conditions,
        start_at,
        end_at,
    )
    incident_trend = _daily_counts(
        db,
        Incident.occurred_at,
        incident_conditions,
        start_at,
        end_at,
    )
    work_order_trend = _daily_counts(
        db,
        MaintenanceWorkOrder.scheduled_at,
        work_order_conditions,
        start_at,
        end_at,
    )

    return {
        "generated_at": datetime.now(timezone.utc),
        "start_date": start_date,
        "end_date": end_date,
        "site_id": site_id,
        "summary": {
            "assets": asset_total,
            "requests": request_total,
            "open_requests": sum(
                request_status[value] for value in OPEN_REQUEST_STATUSES
            ),
            "incidents": incident_total,
            "open_incidents": (
                incident_status["reported"] + incident_status["investigating"]
            ),
            "work_orders": work_order_total,
            "completed_work_orders": work_order_status["completed"],
        },
        "asset_status": [
            {"label": label, "count": asset_status[label]}
            for label in ASSET_STATUSES
        ],
        "request_status": [
            {"label": label, "count": request_status[label]}
            for label in REQUEST_STATUSES
        ],
        "incident_severity": [
            {"label": label, "count": incident_severity[label]}
            for label in INCIDENT_SEVERITIES
        ],
        "work_order_status": [
            {"label": label, "count": work_order_status[label]}
            for label in WORK_ORDER_STATUSES
        ],
        "daily_trend": [
            {
                "date": day,
                "requests": request_trend.get(day, 0),
                "incidents": incident_trend.get(day, 0),
                "work_orders": work_order_trend.get(day, 0),
            }
            for day in (
                start_date + timedelta(days=offset)
                for offset in range((end_date - start_date).days + 1)
            )
        ],
    }
