from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.database.connection import get_db
from backend.app.database.models.identity import (
    Role,
    User,
    UserDepartmentAccess,
    UserRoleAssignment,
    UserSiteAccess,
)
from backend.app.database.models.organization import Department, Organization, Site


router = APIRouter(prefix="/organizations", tags=["Organizations"])


def _require_organization_access(db: Session, user_id: UUID, organization_id: UUID) -> None:
    is_system_admin = db.scalar(
        select(User.is_system_admin).where(User.id == user_id)
    )
    if is_system_admin:
        active_organization = db.scalar(
            select(Organization.id).where(
                Organization.id == organization_id,
                Organization.is_active.is_(True),
            )
        )
        if active_organization is not None:
            return

    now = datetime.now(timezone.utc)
    access = db.scalar(
        select(UserRoleAssignment.id)
        .join(Role, Role.id == UserRoleAssignment.role_id)
        .join(Organization, Organization.id == UserRoleAssignment.organization_id)
        .where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.organization_id == organization_id,
            UserRoleAssignment.expires_at.is_(None)
            | (UserRoleAssignment.expires_at > now),
            Role.is_active.is_(True),
            Organization.is_active.is_(True),
        )
        .limit(1)
    )
    if access is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization access denied.",
        )


@router.get("/{organization_id}/sites")
def list_accessible_sites(
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_organization_access(db, current_user.id, organization_id)
    statement = select(Site).where(
        Site.organization_id == organization_id,
        Site.is_active.is_(True),
    )
    if not current_user.is_system_admin:
        now = datetime.now(timezone.utc)
        statement = (
            statement
            .join(UserSiteAccess, UserSiteAccess.site_id == Site.id)
            .where(
                UserSiteAccess.user_id == current_user.id,
                (
                    UserSiteAccess.expires_at.is_(None)
                    | (UserSiteAccess.expires_at > now)
                ),
            )
        )
    sites = db.scalars(statement.order_by(Site.name.asc())).all()

    return [{"id": str(site.id), "name": site.name, "code": site.code} for site in sites]


@router.get("/{organization_id}/departments")
def list_accessible_departments(
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_organization_access(db, current_user.id, organization_id)
    statement = select(Department).where(
        Department.organization_id == organization_id,
        Department.is_active.is_(True),
    )
    if not current_user.is_system_admin:
        now = datetime.now(timezone.utc)
        statement = (
            statement
            .join(
                UserDepartmentAccess,
                UserDepartmentAccess.department_id == Department.id,
            )
            .where(
                UserDepartmentAccess.user_id == current_user.id,
                (
                    UserDepartmentAccess.expires_at.is_(None)
                    | (UserDepartmentAccess.expires_at > now)
                ),
            )
        )
    departments = db.scalars(statement.order_by(Department.name.asc())).all()

    return [
        {"id": str(department.id), "name": department.name, "code": department.code}
        for department in departments
    ]