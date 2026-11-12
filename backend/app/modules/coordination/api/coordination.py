from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User
from backend.app.modules.coordination.schemas.coordination import (
    CoordinationTechnicianRead,
    CoordinationWorkOrderListResponse,
    WorkOrderAssignmentCreate,
    WorkOrderAssignmentHistoryResponse,
    WorkOrderAssignmentRead,
)
from backend.app.modules.coordination.services import (
    coordination_service as service,
)
from backend.app.modules.maintenance_calendar.schemas.work_order import (
    MaintenanceWorkOrderStatus,
)


router = APIRouter(prefix="/coordination", tags=["Coordination"])


def _commit_or_rollback(db: Session, operation):
    try:
        result = operation()
        db.commit()
        db.refresh(result)
        return result
    except Exception:
        db.rollback()
        raise


@router.get(
    "/work-orders",
    response_model=CoordinationWorkOrderListResponse,
)
def list_work_orders(
    organization_id: UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    work_order_status: MaintenanceWorkOrderStatus | None = Query(
        None, alias="status"
    ),
    search: str | None = Query(None, max_length=150),
    current_user: User = Depends(require_permission("coordination.view")),
    db: Session = Depends(get_db),
):
    return service.list_coordination_work_orders(
        db,
        current_user.id,
        organization_id,
        offset,
        limit,
        work_order_status,
        search,
    )


@router.get(
    "/work-orders/{work_order_id}/technicians",
    response_model=list[CoordinationTechnicianRead],
)
def list_work_order_technicians(
    work_order_id: UUID,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("coordination.view")),
    db: Session = Depends(get_db),
):
    work_order = service.get_work_order(
        db, work_order_id, organization_id, current_user.id
    )
    technicians = service.list_technicians(db, work_order, current_user.id)
    return [
        {
            "id": technician.id,
            "display_name": technician.display_name,
            "email": technician.email,
        }
        for technician in technicians
    ]


@router.get(
    "/work-orders/{work_order_id}/history",
    response_model=WorkOrderAssignmentHistoryResponse,
)
def get_work_order_assignment_history(
    work_order_id: UUID,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("coordination.view")),
    db: Session = Depends(get_db),
):
    work_order = service.get_work_order(
        db, work_order_id, organization_id, current_user.id
    )
    return {
        "items": service.list_assignment_history(db, work_order.id)
    }


@router.post(
    "/work-orders/{work_order_id}/assign",
    response_model=WorkOrderAssignmentRead,
    status_code=201,
)
def assign_work_order(
    work_order_id: UUID,
    data: WorkOrderAssignmentCreate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("coordination.assign")),
    db: Session = Depends(get_db),
):
    work_order = service.get_work_order(
        db, work_order_id, organization_id, current_user.id
    )
    assignment = _commit_or_rollback(
        db,
        lambda: service.assign_work_order(
            db, work_order, current_user.id, data
        ),
    )
    return assignment
