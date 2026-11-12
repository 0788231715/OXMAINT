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
from backend.app.database.models.incident import Incident
from backend.app.database.models.organization import (
    Department,
    Organization,
    Site,
)
from backend.app.modules.incident_management.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
)
from backend.app.modules.user_management.services.authorization_service import (
    has_department_access,
    has_site_access,
)


ALLOWED_TRANSITIONS = {
    "reported": {"investigating", "resolved"},
    "investigating": {"resolved"},
    "resolved": {"closed"},
    "closed": set(),
}


def _error(code: int, detail: str) -> None:
    raise HTTPException(status_code=code, detail=detail)


def _validate_references(
    db: Session,
    organization_id: UUID,
    site_id: UUID,
    department_id: UUID | None,
    asset_id: UUID | None,
) -> None:
    organization = db.get(Organization, organization_id)
    site = db.get(Site, site_id)
    if (
        organization is None
        or not organization.is_active
        or site is None
        or not site.is_active
        or site.organization_id != organization_id
    ):
        _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The selected site is not active in this organization.",
        )

    if department_id is not None:
        department = db.get(Department, department_id)
        if (
            department is None
            or not department.is_active
            or department.organization_id != organization_id
        ):
            _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "The selected department is not active in this organization.",
            )

    if asset_id is not None:
        asset = db.get(Asset, asset_id)
        if (
            asset is None
            or not asset.is_active
            or asset.organization_id != organization_id
            or asset.site_id != site_id
            or (
                asset.department_id is not None
                and asset.department_id != department_id
            )
        ):
            _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "The selected asset is unavailable in this incident's location.",
            )


def create_incident(
    db: Session,
    data: IncidentCreate,
    reported_by: UUID,
) -> Incident:
    user = db.get(User, reported_by)
    if user is None or not user.is_active:
        _error(
            status.HTTP_403_FORBIDDEN,
            "An active user is required to report an incident.",
        )

    _validate_references(
        db,
        data.organization_id,
        data.site_id,
        data.department_id,
        data.asset_id,
    )

    incident = Incident(
        organization_id=data.organization_id,
        site_id=data.site_id,
        department_id=data.department_id,
        asset_id=data.asset_id,
        reported_by=reported_by,
        incident_number=f"INC-{datetime.now(timezone.utc):%Y%m%d}-{token_hex(3).upper()}",
        title=data.title,
        description=data.description,
        category=data.category,
        severity=data.severity,
        status="reported",
        occurred_at=data.occurred_at,
    )
    db.add(incident)
    db.flush()
    return incident


def _ensure_incident_scope(
    db: Session,
    incident: Incident,
    user_id: UUID,
    organization_id: UUID,
) -> None:
    if not has_site_access(db, user_id, incident.site_id, organization_id):
        _error(status.HTTP_403_FORBIDDEN, "Site access denied.")
    if incident.department_id is not None and not has_department_access(
        db, user_id, incident.department_id, organization_id
    ):
        _error(status.HTTP_403_FORBIDDEN, "Department access denied.")


def get_incident(
    db: Session,
    incident_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    for_update: bool = False,
) -> Incident:
    statement = select(Incident).where(
        Incident.id == incident_id,
        Incident.organization_id == organization_id,
    )
    if for_update:
        statement = statement.with_for_update()
    incident = db.scalar(statement)
    if incident is None:
        _error(status.HTTP_404_NOT_FOUND, "Incident not found.")

    _ensure_incident_scope(db, incident, user_id, organization_id)
    return incident


def update_incident(
    db: Session,
    incident: Incident,
    data: IncidentUpdate,
) -> Incident:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return incident
    if "status" in changes and changes["status"] is None:
        _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Incident status cannot be null.",
        )

    site_id = changes.get("site_id", incident.site_id)
    department_id = changes.get("department_id", incident.department_id)
    asset_id = changes.get("asset_id", incident.asset_id)
    _validate_references(
        db,
        incident.organization_id,
        site_id,
        department_id,
        asset_id,
    )

    new_status = changes.get("status", incident.status)
    if new_status != incident.status and new_status not in ALLOWED_TRANSITIONS[
        incident.status
    ]:
        _error(
            status.HTTP_409_CONFLICT,
            f"An incident cannot move from {incident.status} to {new_status}.",
        )

    resolution = changes.get("resolution", incident.resolution)
    if new_status in {"resolved", "closed"} and not resolution:
        _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "A resolution is required before an incident can be resolved or closed.",
        )

    for field, value in changes.items():
        setattr(incident, field, value)
    db.flush()
    return incident


def list_accessible_incidents(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    offset: int = 0,
    limit: int = 25,
    incident_status: str | None = None,
    severity: str | None = None,
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
            UserSiteAccess.site_id == Incident.site_id,
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
            UserDepartmentAccess.department_id == Incident.department_id,
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
        Incident.organization_id == organization_id,
        active_organization,
        or_(system_admin.is_(True), site_access),
        or_(
            system_admin.is_(True),
            Incident.department_id.is_(None),
            department_access,
        ),
    ]
    if incident_status is not None:
        conditions.append(Incident.status == incident_status)
    if severity is not None:
        conditions.append(Incident.severity == severity)
    term = search.strip() if search else ""
    if term:
        term = f"%{term}%"
        conditions.append(
            or_(
                Incident.incident_number.ilike(term),
                Incident.title.ilike(term),
                Incident.description.ilike(term),
            )
        )

    total = db.scalar(
        select(func.count(Incident.id)).where(*conditions)
    ) or 0
    items = list(
        db.scalars(
            select(Incident)
            .where(*conditions)
            .order_by(Incident.occurred_at.desc(), Incident.id.desc())
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
