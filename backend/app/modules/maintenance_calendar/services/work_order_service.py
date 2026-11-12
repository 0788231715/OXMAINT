from datetime import datetime, timezone
from secrets import token_hex
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.database.models.asset import Asset
from backend.app.database.models.identity import (
    User,
    UserDepartmentAccess,
    UserSiteAccess,
)
from backend.app.database.models.maintenance_work_order import (
    MaintenanceWorkOrder,
)
from backend.app.database.models.organization import (
    Department,
    Organization,
    Site,
)
from backend.app.modules.maintenance_calendar.schemas.work_order import (
    MaintenanceWorkOrderCreate,
    MaintenanceWorkOrderTransition,
    MaintenanceWorkOrderType,
)
from backend.app.modules.user_management.services.authorization_service import (
    has_department_access,
    has_site_access,
)


ALLOWED_TRANSITIONS = {
    "scheduled": {"in_progress", "cancelled"},
    "in_progress": {"waiting", "completed", "cancelled"},
    "waiting": {"in_progress", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


def _error(code: int, detail: str) -> None:
    raise HTTPException(status_code=code, detail=detail)


def _load_accessible_asset(
    db: Session,
    asset_id: UUID,
    organization_id: UUID,
    user_id: UUID,
) -> Asset:
    asset = db.scalar(
        select(Asset)
        .join(Organization, Organization.id == Asset.organization_id)
        .where(
            Asset.id == asset_id,
            Asset.organization_id == organization_id,
            Asset.is_active.is_(True),
            Organization.is_active.is_(True),
        )
    )
    if asset is None:
        _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The selected asset is not active in this organization.",
        )
    if not has_site_access(db, user_id, asset.site_id, organization_id):
        _error(status.HTTP_403_FORBIDDEN, "Site access denied.")
    if asset.department_id is not None and not has_department_access(
        db, user_id, asset.department_id, organization_id
    ):
        _error(status.HTTP_403_FORBIDDEN, "Department access denied.")
    return asset


def create_work_order(
    db: Session,
    data: MaintenanceWorkOrderCreate,
    created_by: UUID,
) -> MaintenanceWorkOrder:
    asset = _load_accessible_asset(
        db, data.asset_id, data.organization_id, created_by
    )
    work_order = MaintenanceWorkOrder(
        organization_id=data.organization_id,
        asset_id=asset.id,
        site_id=asset.site_id,
        department_id=asset.department_id,
        created_by=created_by,
        work_order_number=(
            f"WO-{datetime.now(timezone.utc):%Y%m%d}-{token_hex(3).upper()}"
        ),
        title=data.title,
        description=data.description,
        work_order_type=data.work_order_type,
        priority=data.priority,
        status="scheduled",
        scheduled_at=data.scheduled_at,
    )
    db.add(work_order)
    db.flush()
    return work_order


def _ensure_work_order_scope(
    db: Session,
    work_order: MaintenanceWorkOrder,
    user_id: UUID,
    organization_id: UUID,
) -> None:
    if not has_site_access(db, user_id, work_order.site_id, organization_id):
        _error(status.HTTP_403_FORBIDDEN, "Site access denied.")
    if work_order.department_id is not None and not has_department_access(
        db, user_id, work_order.department_id, organization_id
    ):
        _error(status.HTTP_403_FORBIDDEN, "Department access denied.")


def get_work_order(
    db: Session,
    work_order_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    for_update: bool = False,
) -> MaintenanceWorkOrder:
    statement = select(MaintenanceWorkOrder).where(
        MaintenanceWorkOrder.id == work_order_id,
        MaintenanceWorkOrder.organization_id == organization_id,
    )
    if for_update:
        statement = statement.with_for_update()
    work_order = db.scalar(statement)
    if work_order is None:
        _error(status.HTTP_404_NOT_FOUND, "Maintenance work order not found.")

    _ensure_work_order_scope(db, work_order, user_id, organization_id)
    return work_order


def transition_work_order(
    db: Session,
    work_order: MaintenanceWorkOrder,
    data: MaintenanceWorkOrderTransition,
) -> MaintenanceWorkOrder:
    if data.status == work_order.status:
        _error(
            status.HTTP_409_CONFLICT,
            "The work order is already in this status.",
        )
    if data.status not in ALLOWED_TRANSITIONS[work_order.status]:
        _error(
            status.HTTP_409_CONFLICT,
            f"A work order cannot move from {work_order.status} to {data.status}.",
        )
    if data.status == "completed" and not data.completion_note:
        _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "A completion note is required before completing a work order.",
        )

    work_order.status = data.status
    if data.completion_note is not None:
        work_order.completion_note = data.completion_note
    if data.status == "completed":
        work_order.completed_at = datetime.now(timezone.utc)
    db.flush()
    return work_order


def list_accessible_work_orders(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    offset: int = 0,
    limit: int = 25,
    work_order_status: str | None = None,
    work_order_type: MaintenanceWorkOrderType | None = None,
    search: str | None = None,
) -> dict:
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
        .join(Site, Site.id == UserSiteAccess.site_id)
        .where(
            UserSiteAccess.user_id == user_id,
            UserSiteAccess.site_id == MaintenanceWorkOrder.site_id,
            Site.organization_id == organization_id,
            Site.is_active.is_(True),
            or_(
                UserSiteAccess.expires_at.is_(None),
                UserSiteAccess.expires_at > now,
            ),
        )
        .exists()
    )
    department_access = (
        select(UserDepartmentAccess.id)
        .join(
            Department,
            Department.id == UserDepartmentAccess.department_id,
        )
        .where(
            UserDepartmentAccess.user_id == user_id,
            UserDepartmentAccess.department_id
            == MaintenanceWorkOrder.department_id,
            Department.organization_id == organization_id,
            Department.is_active.is_(True),
            or_(
                UserDepartmentAccess.expires_at.is_(None),
                UserDepartmentAccess.expires_at > now,
            ),
        )
        .exists()
    )
    conditions = [
        MaintenanceWorkOrder.organization_id == organization_id,
        active_organization,
        or_(system_admin.is_(True), site_access),
        or_(
            system_admin.is_(True),
            MaintenanceWorkOrder.department_id.is_(None),
            department_access,
        ),
    ]
    if work_order_status is not None:
        conditions.append(MaintenanceWorkOrder.status == work_order_status)
    if work_order_type is not None:
        conditions.append(
            MaintenanceWorkOrder.work_order_type == work_order_type
        )
    term = search.strip() if search else ""
    if term:
        term = f"%{term}%"
        conditions.append(
            or_(
                MaintenanceWorkOrder.work_order_number.ilike(term),
                MaintenanceWorkOrder.title.ilike(term),
                MaintenanceWorkOrder.description.ilike(term),
            )
        )

    total = db.scalar(
        select(func.count(MaintenanceWorkOrder.id)).where(*conditions)
    ) or 0
    items = list(
        db.scalars(
            select(MaintenanceWorkOrder)
            .where(*conditions)
            .order_by(
                MaintenanceWorkOrder.scheduled_at.asc(),
                MaintenanceWorkOrder.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(items) < total,
    }
