from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User
from backend.app.modules.reports.schemas.reports import ReportsSnapshot
from backend.app.modules.reports.services.reports_service import (
    build_reports_snapshot,
)
from backend.app.modules.user_management.services.authorization_service import (
    has_site_access,
)


router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get("", response_model=ReportsSnapshot)
def get_reports_snapshot(
    organization_id: UUID = Query(...),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    site_id: UUID | None = Query(None),
    current_user: User = Depends(require_permission("reports.view")),
    db: Session = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()
    effective_end = end_date or today
    effective_start = start_date or effective_end - timedelta(days=29)
    if effective_start > effective_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The report start date must be on or before its end date.",
        )
    if (effective_end - effective_start).days > 365:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Reports can cover at most 366 days at a time.",
        )
    if site_id is not None and not has_site_access(
        db, current_user.id, site_id, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Site access denied.",
        )

    return build_reports_snapshot(
        db,
        current_user.id,
        organization_id,
        effective_start,
        effective_end,
        site_id,
    )
