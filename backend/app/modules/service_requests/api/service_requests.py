from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
from backend.app.core.dependencies import get_current_user
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User
from backend.app.modules.service_requests.schemas.service_request import (
    RequestApprovalInput,
    RequestAssignmentCreate,
    RequestCommentCreate,
    RequestRejectionInput,
    RequestReviewInput,
    RequestStatusTransitionInput,
    ServiceRequestCreate,
    ServiceRequestRead,
    ServiceRequestUpdate,
)
from backend.app.modules.service_requests.services import (
    service_request_service as service,
)
from backend.app.modules.user_management.services.authorization_service import (
    has_department_access,
    has_site_access,
)


router = APIRouter(
    prefix="/service-requests",
    tags=["Service Requests"],
)


def _load_request(
    db: Session,
    request_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    for_update: bool = False,
):
    return service.get_service_request(
        db=db,
        request_id=request_id,
        organization_id=organization_id,
        user_id=user_id,
        for_update=for_update,
    )


def _check_target_scope(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    site_id: UUID,
    department_id: UUID | None,
) -> None:
    if not has_site_access(db, user_id, site_id, organization_id):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Site access denied.",
        )

    if department_id is not None and not has_department_access(
        db, user_id, department_id, organization_id
    ):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Department access denied.",
        )


def _rollback_on_error(db: Session, operation):
    try:
        result = operation()
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.post(
    "",
    response_model=ServiceRequestRead,
    status_code=201,
)
def create_request(
    data: ServiceRequestCreate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("service_requests.create")),
    db: Session = Depends(get_db),
):
    if data.organization_id != organization_id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload organization does not match the selected organization.",
        )

    _check_target_scope(
        db,
        current_user.id,
        organization_id,
        data.site_id,
        data.department_id,
    )

    request = _rollback_on_error(
        db,
        lambda: service.create_service_request(
            db, data, current_user.id
        ),
    )
    db.refresh(request)
    return request


@router.get("")
def list_requests(
    organization_id: UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    request_status: str | None = Query(None),
    priority: str | None = Query(None),
    search: str | None = Query(None, max_length=150),
    current_user: User = Depends(require_permission("service_requests.view")),
    db: Session = Depends(get_db),
):
    result = service.list_accessible_service_requests(
        db=db,
        user_id=current_user.id,
        organization_id=organization_id,
        offset=offset,
        limit=limit,
        request_status=request_status,
        priority=priority,
        search=search,
    )

    result["items"] = [
        ServiceRequestRead.model_validate(item).model_dump(mode="json")
        for item in result["items"]
    ]
    return result


@router.get("/{request_id}", response_model=ServiceRequestRead)
def get_request(
    request_id: UUID,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("service_requests.view")),
    db: Session = Depends(get_db),
):
    return _load_request(
        db, request_id, organization_id, current_user.id
    )


@router.patch("/{request_id}", response_model=ServiceRequestRead)
def update_request(
    request_id: UUID,
    data: ServiceRequestUpdate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("service_requests.update")),
    db: Session = Depends(get_db),
):
    request = _load_request(
        db, request_id, organization_id, current_user.id, for_update=True
    )

    changes = data.model_dump(exclude_unset=True)
    target_site = changes.get("site_id", request.site_id)
    target_department = changes.get(
        "department_id", request.department_id
    )

    if target_site is not None:
        _check_target_scope(
            db,
            current_user.id,
            organization_id,
            target_site,
            target_department,
        )

    result = _rollback_on_error(
        db,
        lambda: service.update_service_request(db, request, data),
    )
    db.refresh(result)
    return result


@router.post("/{request_id}/review", response_model=ServiceRequestRead)
def review_request(
    request_id: UUID,
    data: RequestReviewInput,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("service_requests.review")),
    db: Session = Depends(get_db),
):
    request = _load_request(
        db, request_id, organization_id, current_user.id, for_update=True
    )

    result = _rollback_on_error(
        db,
        lambda: service.review_service_request(
            db, request, current_user.id, data.review_note
        ),
    )
    db.refresh(result)
    return result


@router.post("/{request_id}/approve")
def approve_request(
    request_id: UUID,
    data: RequestApprovalInput,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("service_requests.approve")),
    db: Session = Depends(get_db),
):
    request = _load_request(
        db, request_id, organization_id, current_user.id, for_update=True
    )

    approval = _rollback_on_error(
        db,
        lambda: service.record_request_approval(
            db, request, data, current_user.id
        ),
    )
    db.refresh(approval)

    return {
        "id": str(approval.id),
        "request_id": str(approval.request_id),
        "approval_step": approval.approval_step,
        "approver_id": str(approval.approver_id),
        "decision": approval.decision,
        "decision_note": approval.decision_note,
        "decided_at": approval.decided_at,
    }


@router.post("/{request_id}/assign", status_code=201)
def assign_request(
    request_id: UUID,
    data: RequestAssignmentCreate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("service_requests.assign")),
    db: Session = Depends(get_db),
):
    request = _load_request(
        db, request_id, organization_id, current_user.id, for_update=True
    )

    assignment = _rollback_on_error(
        db,
        lambda: service.assign_service_request(
            db, request, data, current_user.id
        ),
    )
    db.refresh(assignment)

    return {
        "id": str(assignment.id),
        "request_id": str(assignment.request_id),
        "assigned_to": str(assignment.assigned_to),
        "assigned_by": str(assignment.assigned_by),
        "assignment_note": assignment.assignment_note,
        "assigned_at": assignment.assigned_at,
        "unassigned_at": assignment.unassigned_at,
    }


@router.post("/{request_id}/reject", response_model=ServiceRequestRead)
def reject_request(
    request_id: UUID,
    data: RequestRejectionInput,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("service_requests.reject")),
    db: Session = Depends(get_db),
):
    request = _load_request(
        db, request_id, organization_id, current_user.id, for_update=True
    )

    result = _rollback_on_error(
        db,
        lambda: service.reject_service_request(
            db, request, data, current_user.id
        ),
    )
    db.refresh(result)
    return result


@router.post("/{request_id}/transition", response_model=ServiceRequestRead)
def transition_request(
    request_id: UUID,
    data: RequestStatusTransitionInput,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("service_requests.transition")),
    db: Session = Depends(get_db),
):
    request = _load_request(
        db, request_id, organization_id, current_user.id, for_update=True
    )

    result = _rollback_on_error(
        db,
        lambda: service.transition_service_request(
            db, request, data, current_user.id
        ),
    )
    db.refresh(result)
    return result


@router.post("/{request_id}/comments", status_code=201)
def add_comment(
    request_id: UUID,
    data: RequestCommentCreate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("service_requests.comment")),
    db: Session = Depends(get_db),
):
    request = _load_request(
        db, request_id, organization_id, current_user.id, for_update=True
    )

    comment = _rollback_on_error(
        db,
        lambda: service.add_request_comment(
            db, request, data, current_user.id
        ),
    )
    db.refresh(comment)

    return {
        "id": str(comment.id),
        "request_id": str(comment.request_id),
        "author_id": str(comment.author_id),
        "content": comment.content,
        "created_at": comment.created_at,
    }

