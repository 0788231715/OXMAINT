from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select

from backend.app.database.models.identity import (
    User,
    UserDepartmentAccess,
    UserSiteAccess,
)
from backend.app.database.models.organization import (
    Department,
    Organization,
    Site,
)


def organization_record_scope(
    model: type,
    user_id: UUID,
    organization_id: UUID,
    site_id: UUID | None = None,
) -> list:
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
            UserSiteAccess.site_id == model.site_id,
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
            UserDepartmentAccess.department_id == model.department_id,
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
        model.organization_id == organization_id,
        active_organization,
        or_(system_admin.is_(True), site_access),
        or_(
            system_admin.is_(True),
            model.department_id.is_(None),
            department_access,
        ),
    ]
    if site_id is not None:
        conditions.append(model.site_id == site_id)
    return conditions
