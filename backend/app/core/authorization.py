from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User
from backend.app.modules.user_management.services.authorization_service import (
    has_permission,
)


def require_permission(permission_code: str):
    """Require an authenticated user to hold a permission in an organization."""

    if not permission_code or not permission_code.strip():
        raise ValueError("Permission code cannot be empty.")

    def permission_dependency(
        organization_id: UUID = Query(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        allowed = has_permission(
            db=db,
            user_id=current_user.id,
            organization_id=organization_id,
            permission_code=permission_code,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return permission_dependency
