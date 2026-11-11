from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.database.models.identity import Role, User, UserRoleAssignment
from backend.app.database.models.organization import Organization
from backend.app.config import settings
from backend.app.database.connection import get_db
from backend.app.modules.user_management.schemas.auth import TokenResponse
from backend.app.modules.user_management.services.auth_service import (
    authenticate_user,
    generate_user_access_token,
)
from backend.app.modules.user_management.services.authorization_service import (
    has_permission,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(
        db=db,
        email=credentials.username,
        password=credentials.password,
    )

    access_token = generate_user_access_token(user)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.get("/me")
def get_authenticated_user(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "display_name": current_user.display_name,
        "is_active": current_user.is_active,
        "is_system_admin": current_user.is_system_admin,
    }


@router.get("/organizations")
def get_user_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    statement = select(Organization.id, Organization.name, Organization.code).where(
        Organization.is_active.is_(True)
    )
    if not current_user.is_system_admin:
        statement = (
            statement
            .join(
                UserRoleAssignment,
                UserRoleAssignment.organization_id == Organization.id,
            )
            .join(Role, Role.id == UserRoleAssignment.role_id)
            .where(
                UserRoleAssignment.user_id == current_user.id,
                Role.is_active.is_(True),
                (
                    UserRoleAssignment.expires_at.is_(None)
                    | (UserRoleAssignment.expires_at > now)
                ),
            )
            .distinct()
        )
    organizations = db.execute(statement.order_by(Organization.name.asc())).all()

    return [
        {
            "id": str(row.id),
            "name": row.name,
            "code": row.code,
            "can_register_users": current_user.is_system_admin
            or has_permission(db, current_user.id, row.id, "users.create"),
        }
        for row in organizations
    ]