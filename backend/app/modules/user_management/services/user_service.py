from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.security import hash_password
from backend.app.database.models.identity import (
    Role,
    User,
    UserDepartmentAccess,
    UserRoleAssignment,
    UserSiteAccess,
)
from backend.app.database.models.organization import Organization
from backend.app.modules.user_management.schemas.users import UserRegistrationInput
from backend.app.modules.user_management.services.authorization_service import (
    has_department_access,
    has_site_access,
)


TECHNICIAN_ROLE_CODE = "maintenance_technician"


def register_technician(
    db: Session,
    organization_id: UUID,
    registering_user: User,
    data: UserRegistrationInput,
) -> User:
    organization = db.get(Organization, organization_id)
    if organization is None or not organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active organization not found.",
        )

    existing_user = db.scalar(
        select(User.id).where(User.email == data.email)
    )
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    role = db.scalar(
        select(Role).where(
            Role.code == TECHNICIAN_ROLE_CODE,
            Role.is_active.is_(True),
        )
    )
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The maintenance technician role is not configured.",
        )

    for site_id in data.site_ids:
        if not has_site_access(
            db, registering_user.id, site_id, organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only grant sites you can access.",
            )

    for department_id in data.department_ids:
        if not has_department_access(
            db, registering_user.id, department_id, organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only grant departments you can access.",
            )

    user = User(
        email=data.email,
        display_name=data.display_name,
        password_hash=hash_password(data.initial_password),
        is_active=True,
    )
    db.add(user)
    db.flush()

    db.add(
        UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            organization_id=organization_id,
            granted_by=registering_user.id,
        )
    )
    db.add_all(
        [
            UserSiteAccess(
                user_id=user.id,
                site_id=site_id,
                granted_by=registering_user.id,
            )
            for site_id in data.site_ids
        ]
    )
    db.add_all(
        [
            UserDepartmentAccess(
                user_id=user.id,
                department_id=department_id,
                granted_by=registering_user.id,
            )
            for department_id in data.department_ids
        ]
    )
    db.flush()
    return user