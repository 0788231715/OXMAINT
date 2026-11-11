from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User
from backend.app.modules.user_management.schemas.users import (
    UserRegistrationInput,
    UserRegistrationRead,
)
from backend.app.modules.user_management.services.user_service import (
    TECHNICIAN_ROLE_CODE,
    register_technician,
)


router = APIRouter(prefix="/users", tags=["User Management"])


@router.post("", response_model=UserRegistrationRead, status_code=201)
def register_user(
    data: UserRegistrationInput,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("users.create")),
    db: Session = Depends(get_db),
):
    try:
        user = register_technician(
            db=db,
            organization_id=organization_id,
            registering_user=current_user,
            data=data,
        )
        db.commit()
        db.refresh(user)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user or access assignment with these details already exists.",
        ) from error
    except Exception:
        db.rollback()
        raise

    return UserRegistrationRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role_code=TECHNICIAN_ROLE_CODE,
        organization_id=organization_id,
    )