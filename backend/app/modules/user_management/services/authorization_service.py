from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models.identity import (
    Permission,
    Role,
    RolePermission,
    User,
    UserDepartmentAccess,
    UserRoleAssignment,
    UserSiteAccess,
)
from backend.app.database.models.organization import (
    Department,
    Organization,
    Site,
)


def _is_system_admin(db: Session, user_id: UUID) -> bool:
    return bool(
        db.scalar(
            select(User.is_system_admin).where(User.id == user_id)
        )
    )


def has_permission(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    permission_code: str,
) -> bool:
    """Check whether a user has an active permission in an active organization."""

    if _is_system_admin(db, user_id):
        return db.scalar(
            select(Organization.id).where(
                Organization.id == organization_id,
                Organization.is_active.is_(True),
            )
        ) is not None

    now = datetime.now(timezone.utc)

    statement = (
        select(Permission.id)
        .join(
            RolePermission,
            RolePermission.permission_id == Permission.id,
        )
        .join(
            Role,
            Role.id == RolePermission.role_id,
        )
        .join(
            UserRoleAssignment,
            UserRoleAssignment.role_id == Role.id,
        )
        .join(
            Organization,
            Organization.id == UserRoleAssignment.organization_id,
        )
        .where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.organization_id == organization_id,
            Organization.is_active.is_(True),
            Permission.code == permission_code,
            Role.is_active.is_(True),
            (
                UserRoleAssignment.expires_at.is_(None)
                | (UserRoleAssignment.expires_at > now)
            ),
        )
        .limit(1)
    )

    return db.scalar(statement) is not None


def has_department_access(
    db: Session,
    user_id: UUID,
    department_id: UUID,
    organization_id: UUID,
) -> bool:
    """Check access to an active department in an active organization."""

    if _is_system_admin(db, user_id):
        return db.scalar(
            select(Department.id)
            .join(Organization, Organization.id == Department.organization_id)
            .where(
                Department.id == department_id,
                Department.organization_id == organization_id,
                Department.is_active.is_(True),
                Organization.is_active.is_(True),
            )
        ) is not None

    now = datetime.now(timezone.utc)

    statement = (
        select(UserDepartmentAccess.id)
        .join(
            Department,
            Department.id == UserDepartmentAccess.department_id,
        )
        .join(
            Organization,
            Organization.id == Department.organization_id,
        )
        .where(
            UserDepartmentAccess.user_id == user_id,
            UserDepartmentAccess.department_id == department_id,
            Department.organization_id == organization_id,
            Department.is_active.is_(True),
            Organization.is_active.is_(True),
            (
                UserDepartmentAccess.expires_at.is_(None)
                | (UserDepartmentAccess.expires_at > now)
            ),
        )
        .limit(1)
    )

    return db.scalar(statement) is not None


def has_site_access(
    db: Session,
    user_id: UUID,
    site_id: UUID,
    organization_id: UUID,
) -> bool:
    """Check access to an active site in an active organization."""

    if _is_system_admin(db, user_id):
        return db.scalar(
            select(Site.id)
            .join(Organization, Organization.id == Site.organization_id)
            .where(
                Site.id == site_id,
                Site.organization_id == organization_id,
                Site.is_active.is_(True),
                Organization.is_active.is_(True),
            )
        ) is not None

    now = datetime.now(timezone.utc)

    statement = (
        select(UserSiteAccess.id)
        .join(
            Site,
            Site.id == UserSiteAccess.site_id,
        )
        .join(
            Organization,
            Organization.id == Site.organization_id,
        )
        .where(
            UserSiteAccess.user_id == user_id,
            UserSiteAccess.site_id == site_id,
            Site.organization_id == organization_id,
            Site.is_active.is_(True),
            Organization.is_active.is_(True),
            (
                UserSiteAccess.expires_at.is_(None)
                | (UserSiteAccess.expires_at > now)
            ),
        )
        .limit(1)
    )

    return db.scalar(statement) is not None
