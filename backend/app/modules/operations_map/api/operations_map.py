from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User
from backend.app.modules.operations_map.schemas.operations_map import (
    OperationsMapRead,
)
from backend.app.modules.operations_map.services.operations_map_service import (
    build_operations_map,
)


router = APIRouter(prefix="/operations-map", tags=["Operations Map"])


@router.get("", response_model=OperationsMapRead)
def get_operations_map(
    organization_id: UUID = Query(...),
    current_user: User = Depends(
        require_permission("operations_map.view")
    ),
    db: Session = Depends(get_db),
):
    return build_operations_map(db, current_user.id, organization_id)
