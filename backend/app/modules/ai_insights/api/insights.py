from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User
from backend.app.modules.ai_insights.schemas.insights import (
    GenerateInsightsRequest,
    GeneratedInsightsResponse,
)
from backend.app.modules.ai_insights.services.openai_service import (
    generate_insights,
)


router = APIRouter(prefix="/ai-insights", tags=["AI Insights"])


@router.post("/generate", response_model=GeneratedInsightsResponse)
def create_insights(
    data: GenerateInsightsRequest,
    organization_id: UUID = Query(...),
    current_user: User = Depends(
        require_permission("ai_insights.generate")
    ),
    db: Session = Depends(get_db),
):
    return generate_insights(
        db=db,
        user_id=current_user.id,
        organization_id=organization_id,
        start_date=data.start_date,
        end_date=data.end_date,
        site_id=data.site_id,
    )
