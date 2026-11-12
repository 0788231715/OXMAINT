from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from backend.app.database.models.identity import (
    Role,
    User,
    UserRoleAssignment,
)
from backend.app.database.models.maintenance_work_order import (
    MaintenanceWorkOrder,
)
from backend.app.database.models.work_order_assignment import WorkOrderAssignment
from backend.app.modules.coordination.schemas.coordination import (
    WorkOrderAssignmentCreate,
)
from backend.app.modules.maintenance_calendar.services import (
    work_order_service,
)
from backend.app.modules.user_management.services.authorization_service import (
    has_department_access,
    has_site_access,
)


TECHNICIAN_ROLE_CODE = "maintenance_technician"


def _error(code: int, detail: str) -> None:
    raise HTTPException(status_code=code, detail=detail)


def _eligible_technicians(
    db: Session,
    work_order: MaintenanceWorkOrder,
    actor_id: UUID,
) -> list[User]:
    if not has_site_access(
        db, actor_id, work_order.site_id, work_order.organization_id
    ):
        _error(status.HTTP_403_FORBIDDEN, "Site access denied.")
    if work_order.department_id is not None and not has_department_access(
        db, actor_id, work_order.department_id, work_order.organization_id
    ):
        _error(status.HTTP_403_FORBIDDEN, "Department access denied.")

    now = datetime.now(timezone.utc)
    candidates = list(
        db.scalars(
            select(User)
            .join(UserRoleAssignment, UserRoleAssignment.user_id == User.id)
            .join(Role, Role.id == UserRoleAssignment.role_id)
            .where(
                User.is_active.is_(True),
                UserRoleAssignment.organization_id == work_order.organization_id,
                Role.code == TECHNICIAN_ROLE_CODE,
                Role.is_active.is_(True),
                (
                    UserRoleAssignment.expires_at.is_(None)
                    | (UserRoleAssignment.expires_at > now)
                ),
            )
            .order_by(User.display_name, User.id)
        ).all()
    )
    return [
        technician
        for technician in candidates
        if has_site_access(
            db, technician.id, work_order.site_id, work_order.organization_id
        )
        and (
            work_order.department_id is None
            or has_department_access(
                db,
                technician.id,
                work_order.department_id,
                work_order.organization_id,
            )
        )
    ]


def list_coordination_work_orders(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    offset: int = 0,
    limit: int = 25,
    work_order_status: str | None = None,
    search: str | None = None,
) -> dict:
    page = work_order_service.list_accessible_work_orders(
        db=db,
        user_id=user_id,
        organization_id=organization_id,
        offset=offset,
        limit=limit,
        work_order_status=work_order_status,
        search=search,
    )
    ids = [item.id for item in page["items"]]
    latest_assignments: dict[UUID, dict] = {}
    if ids:
        Assignee = aliased(User)
        Assigner = aliased(User)
        assignments = db.execute(
            select(
                WorkOrderAssignment,
                Assignee.display_name,
                Assigner.display_name,
            )
            .join(Assignee, Assignee.id == WorkOrderAssignment.assigned_to)
            .join(Assigner, Assigner.id == WorkOrderAssignment.assigned_by)
            .where(WorkOrderAssignment.work_order_id.in_(ids))
            .order_by(
                WorkOrderAssignment.work_order_id,
                WorkOrderAssignment.assigned_at.desc(),
                WorkOrderAssignment.id.desc(),
            )
        ).all()
        for assignment, assignee_name, assigner_name in assignments:
            latest_assignments.setdefault(
                assignment.work_order_id,
                {
                    "id": assignment.id,
                    "work_order_id": assignment.work_order_id,
                    "assigned_to": assignment.assigned_to,
                    "assigned_by": assignment.assigned_by,
                    "assignee_name": assignee_name,
                    "assigner_name": assigner_name,
                    "handoff_note": assignment.handoff_note,
                    "assigned_at": assignment.assigned_at,
                },
            )

    return {
        **page,
        "items": [
            {
                "work_order": work_order,
                "current_assignment": latest_assignments.get(work_order.id),
            }
            for work_order in page["items"]
        ],
    }


def list_technicians(
    db: Session,
    work_order: MaintenanceWorkOrder,
    actor_id: UUID,
) -> list[User]:
    return _eligible_technicians(db, work_order, actor_id)


def assign_work_order(
    db: Session,
    work_order: MaintenanceWorkOrder,
    actor_id: UUID,
    data: WorkOrderAssignmentCreate,
) -> WorkOrderAssignment:
    technician = next(
        (
            item
            for item in _eligible_technicians(db, work_order, actor_id)
            if item.id == data.assigned_to
        ),
        None,
    )
    if technician is None:
        _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Choose an active maintenance technician with access to this work order's site and department.",
        )

    current = db.scalar(
        select(WorkOrderAssignment)
        .where(WorkOrderAssignment.work_order_id == work_order.id)
        .order_by(
            WorkOrderAssignment.assigned_at.desc(),
            WorkOrderAssignment.id.desc(),
        )
        .limit(1)
    )
    if current is not None and current.assigned_to == technician.id:
        _error(
            status.HTTP_409_CONFLICT,
            "This technician is already assigned to the work order.",
        )

    assignment = WorkOrderAssignment(
        work_order_id=work_order.id,
        assigned_to=technician.id,
        assigned_by=actor_id,
        handoff_note=data.handoff_note,
        assigned_at=datetime.now(timezone.utc),
    )
    db.add(assignment)
    db.flush()
    assignment.assignee_name = technician.display_name
    actor = db.get(User, actor_id)
    assignment.assigner_name = actor.display_name if actor else ""
    return assignment


def list_assignment_history(
    db: Session,
    work_order_id: UUID,
) -> list[dict]:
    Assignee = aliased(User)
    Assigner = aliased(User)
    assignments = db.execute(
        select(
            WorkOrderAssignment,
            Assignee.display_name,
            Assigner.display_name,
        )
        .join(Assignee, Assignee.id == WorkOrderAssignment.assigned_to)
        .join(Assigner, Assigner.id == WorkOrderAssignment.assigned_by)
        .where(WorkOrderAssignment.work_order_id == work_order_id)
        .order_by(
            WorkOrderAssignment.assigned_at.desc(),
            WorkOrderAssignment.id.desc(),
        )
    ).all()
    result = []
    for assignment, assignee_name, assigner_name in assignments:
        result.append(
            {
                "id": assignment.id,
                "work_order_id": assignment.work_order_id,
                "assigned_to": assignment.assigned_to,
                "assigned_by": assignment.assigned_by,
                "assignee_name": assignee_name,
                "assigner_name": assigner_name,
                "handoff_note": assignment.handoff_note,
                "assigned_at": assignment.assigned_at,
            }
        )
    return result


def get_work_order(
    db: Session, work_order_id: UUID, organization_id: UUID, user_id: UUID
) -> MaintenanceWorkOrder:
    return work_order_service.get_work_order(
        db, work_order_id, organization_id, user_id
    )
