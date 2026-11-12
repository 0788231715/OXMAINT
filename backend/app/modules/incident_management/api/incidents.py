from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User
from backend.app.modules.incident_management.schemas.incident import (
    IncidentCreate,
    IncidentListResponse,
    IncidentRead,
    IncidentSeverity,
    IncidentStatus,
    IncidentUpdate,
)
from backend.app.modules.incident_management.services import (
    incident_service as service,
)
from backend.app.modules.user_management.services.authorization_service import (
    has_department_access,
    has_site_access,
)


router = APIRouter(prefix="/incidents", tags=["Incidents"])


def _commit_or_rollback(db: Session, operation):
    try:
        result = operation()
        db.commit()
        db.refresh(result)
        return result
    except Exception:
        db.rollback()
        raise


def _check_scope(
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


@router.post("", response_model=IncidentRead, status_code=201)
def create_incident(
    data: IncidentCreate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("incidents.create")),
    db: Session = Depends(get_db),
):
    if data.organization_id != organization_id:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Payload organization does not match the selected organization.",
        )

    _check_scope(
        db,
        current_user.id,
        organization_id,
        data.site_id,
        data.department_id,
    )
    incident = _commit_or_rollback(
        db, lambda: service.create_incident(db, data, current_user.id)
    )
    return incident


@router.get("", response_model=IncidentListResponse)
def list_incidents(
    organization_id: UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    incident_status: IncidentStatus | None = Query(None, alias="status"),
    severity: IncidentSeverity | None = Query(None),
    search: str | None = Query(None, max_length=150),
    current_user: User = Depends(require_permission("incidents.view")),
    db: Session = Depends(get_db),
):
    return service.list_accessible_incidents(
        db=db,
        user_id=current_user.id,
        organization_id=organization_id,
        offset=offset,
        limit=limit,
        incident_status=incident_status,
        severity=severity,
        search=search,
    )


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(
    incident_id: UUID,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("incidents.view")),
    db: Session = Depends(get_db),
):
    incident = service.get_incident(
        db, incident_id, organization_id, current_user.id
    )
    return incident


@router.patch("/{incident_id}", response_model=IncidentRead)
def update_incident(
    incident_id: UUID,
    data: IncidentUpdate,
    organization_id: UUID = Query(...),
    current_user: User = Depends(require_permission("incidents.update")),
    db: Session = Depends(get_db),
):
    incident = service.get_incident(
        db, incident_id, organization_id, current_user.id, for_update=True
    )
    changes = data.model_dump(exclude_unset=True)
    _check_scope(
        db,
        current_user.id,
        organization_id,
        changes.get("site_id", incident.site_id),
        changes.get("department_id", incident.department_id),
    )
    result = _commit_or_rollback(
        db, lambda: service.update_incident(db, incident, data)
    )
    return result
