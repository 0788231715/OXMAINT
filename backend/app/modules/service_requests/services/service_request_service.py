from datetime import datetime, timezone
from secrets import token_hex
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.database.models.asset import Asset
from backend.app.database.models.identity import (
    User,
    UserDepartmentAccess,
    UserSiteAccess,
)
from backend.app.database.models.organization import (
    Department,
    Organization,
    Site,
)
from backend.app.database.models.service_request import (
    RequestApproval,
    RequestAssignment,
    RequestComment,
    RequestStatusHistory,
    ServiceRequest,
)
from backend.app.modules.service_requests.schemas.service_request import (
    RequestApprovalInput,
    RequestAssignmentCreate,
    RequestCommentCreate,
    RequestRejectionInput,
    RequestStatusTransitionInput,
    ServiceRequestCreate,
    ServiceRequestUpdate,
)
from backend.app.modules.user_management.services.authorization_service import (
    has_department_access,
    has_permission,
    has_site_access,
)


TERMINAL_STATUSES = {"closed", "rejected", "cancelled"}

ALLOWED_TRANSITIONS = {
    "submitted": {"cancelled"},
    "under_review": {"cancelled"},
    "approved": {"cancelled"},
    "assigned": {"in_progress", "waiting", "cancelled"},
    "in_progress": {"waiting", "completed", "cancelled"},
    "waiting": {"in_progress", "cancelled"},
    "completed": {"closed"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _error(code: int, message: str) -> None:
    raise HTTPException(status_code=code, detail=message)


def _requires_manager_approval(request: ServiceRequest) -> bool:
    return request.priority in {"high", "urgent"} or request.safety_critical


def _get_request(
    db: Session,
    request_id: UUID,
    organization_id: UUID,
    for_update: bool = False,
) -> ServiceRequest:
    statement = select(ServiceRequest).where(
        ServiceRequest.id == request_id,
        ServiceRequest.organization_id == organization_id,
    )

    if for_update:
        statement = statement.with_for_update()

    request = db.scalar(statement)

    if request is None:
        _error(status.HTTP_404_NOT_FOUND, "Service request not found.")

    return request


def _validate_request_scope(
    db: Session,
    organization_id: UUID,
    site_id: UUID,
    department_id: UUID | None,
    asset_id: UUID | None,
) -> None:
    organization = db.get(Organization, organization_id)

    if organization is None or not organization.is_active:
        _error(status.HTTP_404_NOT_FOUND, "Active organization not found.")

    site = db.get(Site, site_id)

    if (
        site is None
        or not site.is_active
        or site.organization_id != organization_id
    ):
        _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The selected site is not active in this organization.",
        )

    if department_id is not None:
        department = db.get(Department, department_id)

        if (
            department is None
            or not department.is_active
            or department.organization_id != organization_id
        ):
            _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "The selected department is not active in this organization.",
            )

    if asset_id is not None:
        asset = db.get(Asset, asset_id)

        if (
            asset is None
            or not asset.is_active
            or asset.organization_id != organization_id
        ):
            _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "The selected asset is not active in this organization.",
            )

        if asset.site_id != site_id:
            _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "The asset must belong to the selected site.",
            )

        if (
            department_id is not None
            and asset.department_id is not None
            and asset.department_id != department_id
        ):
            _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "The asset does not belong to the selected department.",
            )


def _validate_user(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)

    if user is None or not user.is_active:
        _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The selected user is not active.",
        )

    return user


def _record_status_change(
    db: Session,
    request: ServiceRequest,
    changed_by: UUID,
    new_status: str,
    reason: str | None = None,
) -> None:
    previous_status = request.status

    if previous_status == new_status:
        _error(
            status.HTTP_409_CONFLICT,
            "The request is already in this status.",
        )

    request.status = new_status

    db.add(
        RequestStatusHistory(
            request_id=request.id,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason,
        )
    )


def create_service_request(
    db: Session,
    data: ServiceRequestCreate,
    requester_id: UUID,
) -> ServiceRequest:
    _validate_user(db, requester_id)

    _validate_request_scope(
        db,
        data.organization_id,
        data.site_id,
        data.department_id,
        data.asset_id,
    )

    request = ServiceRequest(
        organization_id=data.organization_id,
        site_id=data.site_id,
        department_id=data.department_id,
        asset_id=data.asset_id,
        requester_id=requester_id,
        request_number=f"SR-{_now():%Y%m%d}-{token_hex(3).upper()}",
        title=data.title,
        description=data.description,
        category=data.category,
        priority=data.priority,
        safety_critical=data.safety_critical,
        status="submitted",
    )

    db.add(request)
    db.flush()

    db.add(
        RequestStatusHistory(
            request_id=request.id,
            previous_status=None,
            new_status="submitted",
            changed_by=requester_id,
            reason="Request submitted.",
        )
    )

    db.flush()
    return request


def update_service_request(
    db: Session,
    request: ServiceRequest,
    data: ServiceRequestUpdate,
) -> ServiceRequest:
    if request.status in TERMINAL_STATUSES:
        _error(
            status.HTTP_409_CONFLICT,
            "A closed, rejected, or cancelled request cannot be edited.",
        )

    changes = data.model_dump(exclude_unset=True)

    if not changes:
        return request

    target_site_id = changes.get("site_id", request.site_id)
    target_department_id = changes.get(
        "department_id", request.department_id
    )
    target_asset_id = changes.get("asset_id", request.asset_id)

    _validate_request_scope(
        db,
        request.organization_id,
        target_site_id,
        target_department_id,
        target_asset_id,
    )

    for field, value in changes.items():
        setattr(request, field, value)

    db.flush()
    return request


def get_service_request(
    db: Session,
    request_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    for_update: bool = False,
) -> ServiceRequest:
    request = _get_request(
        db, request_id, organization_id, for_update=for_update
    )

    if not has_site_access(
        db, user_id, request.site_id, organization_id
    ):
        _error(status.HTTP_403_FORBIDDEN, "Site access denied.")

    if request.department_id is not None and not has_department_access(
        db, user_id, request.department_id, organization_id
    ):
        _error(status.HTTP_403_FORBIDDEN, "Department access denied.")

    return request


def list_accessible_service_requests(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    offset: int = 0,
    limit: int = 50,
    request_status: str | None = None,
    priority: str | None = None,
    search: str | None = None,
):
    now = _now()
    system_admin = (
        select(User.is_system_admin)
        .where(User.id == user_id)
        .scalar_subquery()
    )
    active_organization = select(Organization.id).where(
        Organization.id == organization_id,
        Organization.is_active.is_(True),
    ).exists()

    site_access = (
        select(UserSiteAccess.id)
        .join(Site, Site.id == UserSiteAccess.site_id)
        .join(Organization, Organization.id == Site.organization_id)
        .where(
            UserSiteAccess.user_id == user_id,
            Site.organization_id == organization_id,
            UserSiteAccess.site_id == ServiceRequest.site_id,
            Site.is_active.is_(True),
            Organization.is_active.is_(True),
            or_(
                UserSiteAccess.expires_at.is_(None),
                UserSiteAccess.expires_at > now,
            ),
        )
        .exists()
    )

    department_access = (
        select(UserDepartmentAccess.id)
        .join(
            Department,
            Department.id == UserDepartmentAccess.department_id,
        )
        .join(Organization, Organization.id == Department.organization_id)
        .where(
            UserDepartmentAccess.user_id == user_id,
            Department.organization_id == organization_id,
            UserDepartmentAccess.department_id
            == ServiceRequest.department_id,
            Department.is_active.is_(True),
            Organization.is_active.is_(True),
            or_(
                UserDepartmentAccess.expires_at.is_(None),
                UserDepartmentAccess.expires_at > now,
            ),
        )
        .exists()
    )

    conditions = [
        ServiceRequest.organization_id == organization_id,
        active_organization,
        or_(system_admin.is_(True), site_access),
        or_(
            system_admin.is_(True),
            ServiceRequest.department_id.is_(None),
            department_access,
        ),
    ]

    if request_status is not None:
        conditions.append(ServiceRequest.status == request_status)

    if priority is not None:
        conditions.append(ServiceRequest.priority == priority)

    if search:
        term = f"%{search.strip()}%"
        conditions.append(
            or_(
                ServiceRequest.request_number.ilike(term),
                ServiceRequest.title.ilike(term),
                ServiceRequest.description.ilike(term),
            )
        )

    total = db.scalar(
        select(func.count(ServiceRequest.id)).where(*conditions)
    ) or 0

    items = db.scalars(
        select(ServiceRequest)
        .where(*conditions)
        .order_by(ServiceRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def review_service_request(
    db: Session,
    request: ServiceRequest,
    reviewer_id: UUID,
    review_note: str | None = None,
) -> ServiceRequest:
    if request.status != "submitted":
        _error(
            status.HTTP_409_CONFLICT,
            "Only submitted requests can enter review.",
        )

    _validate_user(db, reviewer_id)

    request.reviewed_by = reviewer_id
    request.reviewed_at = _now()

    _record_status_change(
        db,
        request,
        reviewer_id,
        "under_review",
        review_note,
    )

    if review_note:
        db.add(
            RequestComment(
                request_id=request.id,
                author_id=reviewer_id,
                content=f"Review note: {review_note}",
            )
        )

    db.flush()
    return request


def assign_service_request(
    db: Session,
    request: ServiceRequest,
    data: RequestAssignmentCreate,
    assigned_by: UUID,
) -> RequestAssignment:
    if request.status not in {"under_review", "approved", "assigned"}:
        _error(
            status.HTTP_409_CONFLICT,
            "The request must be under review, approved, or already assigned.",
        )

    if _requires_manager_approval(request):
        decisions = db.scalars(
            select(RequestApproval).where(
                RequestApproval.request_id == request.id,
                RequestApproval.approval_step == 1,
            )
        ).all()

        if any(decision.decision == "rejected" for decision in decisions):
            _error(
                status.HTTP_409_CONFLICT,
                "A manager rejection is recorded; assignment is blocked pending review.",
            )

        if not any(decision.decision == "approved" for decision in decisions):
            _error(
                status.HTTP_409_CONFLICT,
                "Manager approval is required before this request can be assigned.",
            )

    assignee = _validate_user(db, data.assigned_to)

    if not has_site_access(
        db, assignee.id, request.site_id, request.organization_id
    ):
        _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The assignee does not have access to the request site.",
        )

    if request.department_id is not None and not has_department_access(
        db,
        assignee.id,
        request.department_id,
        request.organization_id,
    ):
        _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The assignee does not have access to the request department.",
        )

    _validate_user(db, assigned_by)

    now = _now()

    active_assignments = db.scalars(
        select(RequestAssignment)
        .where(
            RequestAssignment.request_id == request.id,
            RequestAssignment.unassigned_at.is_(None),
        )
        .with_for_update()
    ).all()

    for assignment in active_assignments:
        assignment.unassigned_at = now

    assignment = RequestAssignment(
        request_id=request.id,
        assigned_to=data.assigned_to,
        assigned_by=assigned_by,
        assignment_note=data.assignment_note,
    )

    db.add(assignment)

    if request.status != "assigned":
        _record_status_change(
            db,
            request,
            assigned_by,
            "assigned",
            data.assignment_note,
        )

    db.flush()
    return assignment


def record_request_approval(
    db: Session,
    request: ServiceRequest,
    data: RequestApprovalInput,
    approver_id: UUID,
    approval_step: int = 1,
) -> RequestApproval:
    if request.status in TERMINAL_STATUSES:
        _error(
            status.HTTP_409_CONFLICT,
            "A terminal request cannot receive an approval decision.",
        )

    if request.requester_id == approver_id:
        _error(
            status.HTTP_403_FORBIDDEN,
            "A requester cannot approve their own request.",
        )

    _validate_user(db, approver_id)

    if not has_permission(
        db,
        approver_id,
        request.organization_id,
        "service_requests.approve",
    ):
        _error(
            status.HTTP_403_FORBIDDEN,
            "Manager approval permission is required to record this decision.",
        )

    existing = db.scalar(
        select(RequestApproval).where(
            RequestApproval.request_id == request.id,
            RequestApproval.approval_step == approval_step,
            RequestApproval.approver_id == approver_id,
        )
    )

    if existing is not None:
        _error(
            status.HTTP_409_CONFLICT,
            "This approver has already recorded a decision for this step.",
        )

    approval = RequestApproval(
        request_id=request.id,
        approval_step=approval_step,
        approver_id=approver_id,
        decision=data.decision,
        decision_note=data.decision_note,
        decided_at=_now(),
    )

    db.add(approval)

    if data.decision == "approved" and request.status == "under_review":
        _record_status_change(
            db,
            request,
            approver_id,
            "approved",
            data.decision_note,
        )

    db.flush()
    return approval


def reject_service_request(
    db: Session,
    request: ServiceRequest,
    data: RequestRejectionInput,
    rejected_by: UUID,
) -> ServiceRequest:
    if request.status not in {"submitted", "under_review"}:
        _error(
            status.HTTP_409_CONFLICT,
            "Only submitted or under-review requests can be rejected.",
        )

    _validate_user(db, rejected_by)

    request.rejection_reason = data.reason

    _record_status_change(
        db,
        request,
        rejected_by,
        "rejected",
        data.reason,
    )

    db.flush()
    return request


def transition_service_request(
    db: Session,
    request: ServiceRequest,
    data: RequestStatusTransitionInput,
    changed_by: UUID,
) -> ServiceRequest:
    current_status = request.status
    new_status = data.new_status

    if current_status in TERMINAL_STATUSES:
        _error(
            status.HTTP_409_CONFLICT,
            "A terminal request cannot change status.",
        )

    allowed = ALLOWED_TRANSITIONS.get(current_status, set())

    if new_status not in allowed:
        _error(
            status.HTTP_409_CONFLICT,
            f"Transition from '{current_status}' to '{new_status}' is not allowed.",
        )

    _validate_user(db, changed_by)

    if new_status == "completed" and not data.resolution:
        _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A resolution is required before completing a request.",
        )

    if new_status == "closed":
        if not request.resolution:
            _error(
                status.HTTP_409_CONFLICT,
                "A request must have a recorded resolution before closure.",
            )

    if new_status == "completed":
        request.resolution = data.resolution
        request.completed_at = _now()

    if new_status == "cancelled":
        if not data.reason:
            _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "A cancellation reason is required.",
            )
        request.cancellation_reason = data.reason

    if new_status == "closed":
        request.closed_at = _now()

    _record_status_change(
        db,
        request,
        changed_by,
        new_status,
        data.reason,
    )

    db.flush()
    return request


def add_request_comment(
    db: Session,
    request: ServiceRequest,
    data: RequestCommentCreate,
    author_id: UUID,
) -> RequestComment:
    if request.status in TERMINAL_STATUSES:
        _error(
            status.HTTP_409_CONFLICT,
            "Comments cannot be added to a terminal request.",
        )

    _validate_user(db, author_id)

    comment = RequestComment(
        request_id=request.id,
        author_id=author_id,
        content=data.content,
    )

    db.add(comment)
    db.flush()
    return comment


