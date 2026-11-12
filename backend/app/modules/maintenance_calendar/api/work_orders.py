from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User
from backend.app.modules.maintenance_calendar.schemas.work_order import (
    MaintenanceWorkOrderCreate,
    MaintenanceWorkOrderListResponse,
    MaintenanceWorkOrderRead,
    MaintenanceWorkOrderStatus,
    MaintenanceWorkOrderTransition,
    MaintenanceWorkOrderType,
)
from backend.app.modules.maintenance_calendar.services import (
    work_order_service as service,
)


router = APIRouter(
    prefix="/maintenance/work-orders",
    tags=["Maintenance Work Orders"],
)


def _commit_or_rollback(db: Session, operation):
    try:
        result = operation()
        db.commit()
        db.refresh(result)
        return result
    except Exception:
        db.rollback()
        raise


@router.post("", response_model=MaintenanceWorkOrderRead, status_code=201)
def create_work_order(
    data: MaintenanceWorkOrderCreate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("maintenance.create")),
    db: Session = Depends(get_db),
):
    if data.organization_id != organization_id:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Payload organization does not match the selected organization.",
        )

    work_order = _commit_or_rollback(
        db, lambda: service.create_work_order(db, data, current_user.id)
    )
    return work_order


@router.get("", response_model=MaintenanceWorkOrderListResponse)
def list_work_orders(
    organization_id: UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    work_order_status: MaintenanceWorkOrderStatus | None = Query(
        None, alias="status"
    ),
    work_order_type: MaintenanceWorkOrderType | None = Query(
        None, alias="type"
    ),
    search: str | None = Query(None, max_length=150),
    current_user: User = Depends(require_permission("maintenance.view")),
    db: Session = Depends(get_db),
):
    return service.list_accessible_work_orders(
        db=db,
        user_id=current_user.id,
        organization_id=organization_id,
        offset=offset,
        limit=limit,
        work_order_status=work_order_status,
        work_order_type=work_order_type,
        search=search,
    )


@router.get("/{work_order_id}", response_model=MaintenanceWorkOrderRead)
def get_work_order(
    work_order_id: UUID,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("maintenance.view")),
    db: Session = Depends(get_db),
):
    return service.get_work_order(
        db, work_order_id, organization_id, current_user.id
    )


@router.post(
    "/{work_order_id}/transition",
    response_model=MaintenanceWorkOrderRead,
)
def transition_work_order(
    work_order_id: UUID,
    data: MaintenanceWorkOrderTransition,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("maintenance.transition")),
    db: Session = Depends(get_db),
):
    work_order = service.get_work_order(
        db, work_order_id, organization_id, current_user.id, for_update=True
    )
    updated = _commit_or_rollback(
        db,
        lambda: service.transition_work_order(db, work_order, data),
    )
    return updated
