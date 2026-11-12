from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User
from backend.app.modules.synchronization.schemas.synchronization import (
    SynchronizationOperation,
    SynchronizationOperationResult,
)
from backend.app.modules.synchronization.services.synchronization_service import (
    process_synchronization_operation,
)


router = APIRouter(
    prefix="/synchronization",
    tags=["Synchronization"],
)


@router.post(
    "/operations",
    response_model=SynchronizationOperationResult,
)
def synchronize_operation(
    operation: SynchronizationOperation,
    organization_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if operation.organization_id != organization_id:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload organization does not match the selected organization.",
        )
    return process_synchronization_operation(db, current_user, operation)
