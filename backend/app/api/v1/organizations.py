from datetime import datetime, timezone
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
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
from backend.app.modules.user_management.services.authorization_service import (
    has_permission,
)


router = APIRouter(prefix="/organizations", tags=["Organizations"])


class OrganizationProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=50)
    description: str | None = Field(max_length=5000)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("An organization name is required.")
        value = value.strip()
        if not value:
            raise ValueError("An organization name is required.")
        return value

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("An organization code is required.")
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]+", value):
            raise ValueError(
                "Organization codes may contain only letters, numbers, hyphens, and underscores."
            )
        return value

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is not None and not isinstance(value, str):
            raise ValueError("Organization description must be text.")
        if value is None:
            return None
        return value.strip() or None


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


@router.put("")
def update_organization_profile(
    data: OrganizationProfileUpdate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("organizations.update")),
    db: Session = Depends(get_db),
):
    organization = db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.is_active.is_(True),
        )
    )
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    organization.name = data.name
    organization.code = data.code
    organization.description = data.description
    try:
        db.commit()
        db.refresh(organization)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this code already exists.",
        ) from error

    return {
        "id": str(organization.id),
        "name": organization.name,
        "code": organization.code,
        "description": organization.description,
        "can_register_users": current_user.is_system_admin
        or has_permission(db, current_user.id, organization.id, "users.create"),
        "can_update": current_user.is_system_admin
        or has_permission(
            db, current_user.id, organization.id, "organizations.update"
        ),
    }


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