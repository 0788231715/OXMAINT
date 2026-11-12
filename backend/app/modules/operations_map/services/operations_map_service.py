from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.database.models.asset import Asset
from backend.app.database.models.identity import User, UserSiteAccess
from backend.app.database.models.incident import Incident
from backend.app.database.models.maintenance_work_order import (
    MaintenanceWorkOrder,
)
from backend.app.database.models.organization import Organization, Site
from backend.app.database.models.service_request import ServiceRequest
from backend.app.modules.operations_map.schemas.operations_map import (
    OperationsMapRead,
)
from backend.app.modules.user_management.services.data_scope_service import (
    organization_record_scope,
)


ASSET_STATUSES = (
    "in_service",
    "under_maintenance",
    "out_of_service",
    "retired",
)
OPEN_REQUEST_STATUSES = (
    "submitted",
    "under_review",
    "approved",
    "assigned",
    "in_progress",
    "waiting",
)
OPEN_INCIDENT_STATUSES = ("reported", "investigating")
HIGH_SEVERITIES = ("high", "critical")
OPEN_WORK_ORDER_STATUSES = ("scheduled", "in_progress", "waiting")


def _accessible_sites(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
) -> list[Site]:
    now = datetime.now(timezone.utc)
    system_admin = (
        select(User.is_system_admin).where(User.id == user_id).scalar_subquery()
    )
    active_organization = select(Organization.id).where(
        Organization.id == organization_id,
        Organization.is_active.is_(True),
    ).exists()
    site_access = (
        select(UserSiteAccess.id)
        .where(
            UserSiteAccess.user_id == user_id,
            UserSiteAccess.site_id == Site.id,
            or_(
                UserSiteAccess.expires_at.is_(None),
                UserSiteAccess.expires_at > now,
            ),
        )
        .exists()
    )
    return list(
        db.scalars(
            select(Site)
            .where(
                Site.organization_id == organization_id,
                Site.is_active.is_(True),
                active_organization,
                or_(system_admin.is_(True), site_access),
            )
            .order_by(Site.name, Site.id)
        ).all()
    )


def _status_counts(
    db: Session,
    model: type,
    status_field,
    user_id: UUID,
    organization_id: UUID,
    extra_conditions: tuple = (),
) -> dict[UUID, dict[str, int]]:
    rows = db.execute(
        select(model.site_id, status_field, func.count())
        .where(
            *organization_record_scope(model, user_id, organization_id),
            *extra_conditions,
        )
        .group_by(model.site_id, status_field)
    ).all()
    counts: dict[UUID, dict[str, int]] = {}
    for site_id, status, count in rows:
        counts.setdefault(site_id, {})[status] = count
    return counts


def _incident_counts(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
) -> tuple[dict[UUID, dict[str, int]], dict[UUID, int]]:
    rows = db.execute(
        select(Incident.site_id, Incident.status, Incident.severity, func.count())
        .where(*organization_record_scope(Incident, user_id, organization_id))
        .group_by(Incident.site_id, Incident.status, Incident.severity)
    ).all()
    status_counts: dict[UUID, dict[str, int]] = {}
    high_severity: dict[UUID, int] = {}
    for site_id, incident_status, severity, count in rows:
        by_status = status_counts.setdefault(site_id, {})
        by_status[incident_status] = by_status.get(incident_status, 0) + count
        if incident_status in OPEN_INCIDENT_STATUSES and severity in HIGH_SEVERITIES:
            high_severity[site_id] = high_severity.get(site_id, 0) + count
    return status_counts, high_severity


def build_operations_map(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
) -> OperationsMapRead:
    sites = _accessible_sites(db, user_id, organization_id)
    assets = _status_counts(
        db,
        Asset,
        Asset.status,
        user_id,
        organization_id,
        (Asset.is_active.is_(True),),
    )
    requests = _status_counts(
        db, ServiceRequest, ServiceRequest.status, user_id, organization_id
    )
    incidents, high_severity = _incident_counts(
        db, user_id, organization_id
    )
    work_orders = _status_counts(
        db,
        MaintenanceWorkOrder,
        MaintenanceWorkOrder.status,
        user_id,
        organization_id,
    )

    now = datetime.now(timezone.utc)
    overdue_rows = db.execute(
        select(MaintenanceWorkOrder.site_id, func.count())
        .where(
            *organization_record_scope(
                MaintenanceWorkOrder, user_id, organization_id
            ),
            MaintenanceWorkOrder.status.in_(OPEN_WORK_ORDER_STATUSES),
            MaintenanceWorkOrder.scheduled_at < now,
        )
        .group_by(MaintenanceWorkOrder.site_id)
    ).all()
    overdue = {site_id: count for site_id, count in overdue_rows}

    site_items = []
    for site in sites:
        asset_status = assets.get(site.id, {})
        request_status = requests.get(site.id, {})
        incident_status = incidents.get(site.id, {})
        work_order_status = work_orders.get(site.id, {})
        site_items.append(
            {
                "site_id": site.id,
                "name": site.name,
                "code": site.code,
                "address": site.address,
                "assets": sum(asset_status.values()),
                "asset_status": {
                    status: asset_status.get(status, 0)
                    for status in ASSET_STATUSES
                },
                "open_requests": sum(
                    request_status.get(status, 0)
                    for status in OPEN_REQUEST_STATUSES
                ),
                "open_incidents": sum(
                    incident_status.get(status, 0)
                    for status in OPEN_INCIDENT_STATUSES
                ),
                "high_severity_incidents": high_severity.get(site.id, 0),
                "open_work_orders": sum(
                    work_order_status.get(status, 0)
                    for status in OPEN_WORK_ORDER_STATUSES
                ),
                "overdue_work_orders": overdue.get(site.id, 0),
            }
        )

    return OperationsMapRead(
        generated_at=now,
        summary={
            "sites": len(site_items),
            "assets": sum(item["assets"] for item in site_items),
            "open_requests": sum(item["open_requests"] for item in site_items),
            "open_incidents": sum(item["open_incidents"] for item in site_items),
            "overdue_work_orders": sum(
                item["overdue_work_orders"] for item in site_items
            ),
        },
        sites=site_items,
    )
