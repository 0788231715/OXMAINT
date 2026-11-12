import hashlib
import json
from typing import Any, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.database.models.identity import User
from backend.app.database.models.synchronization import SynchronizationReceipt
from backend.app.modules.incident_management.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
)
from backend.app.modules.incident_management.services import (
    incident_service,
)
from backend.app.modules.maintenance_calendar.schemas.work_order import (
    MaintenanceWorkOrderCreate,
    MaintenanceWorkOrderTransition,
)
from backend.app.modules.maintenance_calendar.services import (
    work_order_service,
)
from backend.app.modules.service_requests.schemas.service_request import (
    RequestStatusTransitionInput,
    ServiceRequestCreate,
)
from backend.app.modules.service_requests.services import (
    service_request_service,
)
from backend.app.modules.synchronization.schemas.synchronization import (
    SynchronizationOperation,
    SynchronizationOperationResult,
)
from backend.app.modules.user_management.services.authorization_service import (
    has_department_access,
    has_permission,
    has_site_access,
)


ModelT = TypeVar("ModelT", bound=BaseModel)


_REQUIRED_PERMISSIONS = {
    "service_request.create": "service_requests.create",
    "service_request.transition": "service_requests.transition",
    "incident.create": "incidents.create",
    "incident.update": "incidents.update",
    "maintenance_work_order.create": "maintenance.create",
    "maintenance_work_order.transition": "maintenance.transition",
}


def _payload(schema: type[ModelT], payload: dict[str, Any]) -> ModelT:
    try:
        return schema.model_validate(payload)
    except ValidationError as error:
        details = [
            {
                "loc": item["loc"],
                "msg": item["msg"],
                "type": item["type"],
            }
            for item in error.errors()
        ]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=details,
        ) from error


def _check_permission(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    operation_type: str,
) -> None:
    permission = _REQUIRED_PERMISSIONS[operation_type]
    if not has_permission(db, user_id, organization_id, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission required: {permission}.",
        )


def _check_target_scope(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    site_id: UUID,
    department_id: UUID | None,
) -> None:
    if not has_site_access(db, user_id, site_id, organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Site access denied.",
        )
    if department_id is not None and not has_department_access(
        db, user_id, department_id, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Department access denied.",
        )


def _result_reference(record_id: UUID) -> dict[str, str]:
    return {"record_id": str(record_id)}


def _apply_operation(
    db: Session,
    user_id: UUID,
    operation: SynchronizationOperation,
) -> dict[str, Any]:
    operation_type = operation.operation_type
    payload = operation.payload

    if operation_type == "service_request.create":
        data = _payload(ServiceRequestCreate, payload)
        if data.organization_id != operation.organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payload organization does not match the queued operation.",
            )
        _check_target_scope(
            db,
            user_id,
            operation.organization_id,
            data.site_id,
            data.department_id,
        )
        result = service_request_service.create_service_request(
            db, data, user_id
        )
        return _result_reference(result.id)

    if operation_type == "service_request.transition":
        if operation.record_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A service request ID is required for this operation.",
            )
        data = _payload(RequestStatusTransitionInput, payload)
        record = service_request_service.get_service_request(
            db,
            operation.record_id,
            operation.organization_id,
            user_id,
            for_update=True,
        )
        result = service_request_service.transition_service_request(
            db, record, data, user_id
        )
        return _result_reference(result.id)

    if operation_type == "incident.create":
        data = _payload(IncidentCreate, payload)
        if data.organization_id != operation.organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payload organization does not match the queued operation.",
            )
        _check_target_scope(
            db,
            user_id,
            operation.organization_id,
            data.site_id,
            data.department_id,
        )
        result = incident_service.create_incident(db, data, user_id)
        return _result_reference(result.id)

    if operation_type == "incident.update":
        if operation.record_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An incident ID is required for this operation.",
            )
        data = _payload(IncidentUpdate, payload)
        record = incident_service.get_incident(
            db,
            operation.record_id,
            operation.organization_id,
            user_id,
            for_update=True,
        )
        changes = data.model_dump(exclude_unset=True)
        _check_target_scope(
            db,
            user_id,
            operation.organization_id,
            changes.get("site_id", record.site_id),
            changes.get("department_id", record.department_id),
        )
        result = incident_service.update_incident(db, record, data)
        return _result_reference(result.id)

    if operation_type == "maintenance_work_order.create":
        data = _payload(MaintenanceWorkOrderCreate, payload)
        if data.organization_id != operation.organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payload organization does not match the queued operation.",
            )
        result = work_order_service.create_work_order(db, data, user_id)
        return _result_reference(result.id)

    if operation_type == "maintenance_work_order.transition":
        if operation.record_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A work order ID is required for this operation.",
            )
        data = _payload(MaintenanceWorkOrderTransition, payload)
        record = work_order_service.get_work_order(
            db,
            operation.record_id,
            operation.organization_id,
            user_id,
            for_update=True,
        )
        result = work_order_service.transition_work_order(db, record, data)
        return _result_reference(result.id)

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Unsupported synchronization operation.",
    )


def _payload_hash(operation: SynchronizationOperation) -> str:
    value = json.dumps(
        operation.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _existing_receipt(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    operation_id: UUID,
) -> SynchronizationReceipt | None:
    return db.scalar(
        select(SynchronizationReceipt).where(
            SynchronizationReceipt.user_id == user_id,
            SynchronizationReceipt.organization_id == organization_id,
            SynchronizationReceipt.operation_id == operation_id,
        )
    )


def process_synchronization_operation(
    db: Session,
    user: User,
    operation: SynchronizationOperation,
) -> SynchronizationOperationResult:
    payload_hash = _payload_hash(operation)
    existing = _existing_receipt(
        db, user.id, operation.organization_id, operation.operation_id
    )
    if existing is not None:
        if (
            existing.operation_type != operation.operation_type
            or existing.payload_hash != payload_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This operation ID was already used with different data.",
            )
        return SynchronizationOperationResult(
            operation_id=operation.operation_id,
            duplicate=True,
            result=existing.result,
        )

    _check_permission(
        db,
        user.id,
        operation.organization_id,
        operation.operation_type,
    )

    try:
        with db.begin_nested():
            result = _apply_operation(db, user.id, operation)
            db.add(
                SynchronizationReceipt(
                    user_id=user.id,
                    organization_id=operation.organization_id,
                    operation_id=operation.operation_id,
                    operation_type=operation.operation_type,
                    payload_hash=payload_hash,
                    result=result,
                )
            )
            db.flush()
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing_receipt(
            db, user.id, operation.organization_id, operation.operation_id
        )
        if existing is not None and existing.payload_hash == payload_hash:
            return SynchronizationOperationResult(
                operation_id=operation.operation_id,
                duplicate=True,
                result=existing.result,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The synchronization operation could not be recorded safely.",
        )
    except Exception:
        db.rollback()
        raise

    return SynchronizationOperationResult(
        operation_id=operation.operation_id,
        result=result,
    )
