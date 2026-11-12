import json
import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.modules.ai_insights.schemas.insights import (
    GeneratedInsightsResponse,
    OperationalInsights,
)
from backend.app.modules.reports.services.reports_service import (
    build_reports_snapshot,
)
from backend.app.modules.user_management.services.authorization_service import (
    has_site_access,
)


logger = logging.getLogger(__name__)
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
INSIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "assets",
                            "service_requests",
                            "safety",
                            "maintenance",
                        ],
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["info", "attention", "urgent"],
                    },
                    "evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "recommendation": {"type": "string"},
                },
                "required": [
                    "title",
                    "category",
                    "severity",
                    "evidence",
                    "recommendation",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["insights"],
    "additionalProperties": False,
}
SYSTEM_PROMPT = (
    "You are OxMaint's operational analyst. Use only the aggregated numeric "
    "metrics supplied by the user. Do not infer causes, claim improvement or "
    "decline without comparing supplied dates, or invent missing information. "
    "Return up to five concise, evidence-backed observations and practical "
    "recommendations. Prioritize urgent safety, critical incidents, out-of-"
    "service assets, and aging operational backlogs when supported by the "
    "counts. If the data has no meaningful signal, return an empty insights "
    "array. Do not request or reveal personal or record-level information."
)


def _metrics_for_prompt(snapshot: dict) -> dict:
    return {
        "period": {
            "start_date": snapshot["start_date"].isoformat(),
            "end_date": snapshot["end_date"].isoformat(),
        },
        "summary": snapshot["summary"],
        "asset_status": snapshot["asset_status"],
        "request_status": snapshot["request_status"],
        "incident_severity": snapshot["incident_severity"],
        "work_order_status": snapshot["work_order_status"],
        "daily_trend": [
            {
                **item,
                "date": item["date"].isoformat(),
            }
            for item in snapshot["daily_trend"]
        ],
    }


def _output_text(payload: dict) -> str:
    if payload.get("status") == "incomplete":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned an incomplete response. Try a shorter date range.",
        )

    text_parts: list[str] = []
    output_items = payload.get("output")
    if not isinstance(output_items, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned an invalid response.",
        )
    for output in output_items:
        if not isinstance(output, dict):
            continue
        if output.get("type") != "message":
            continue
        content_items = output.get("content")
        if not isinstance(content_items, list):
            continue
        for content in content_items:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="OpenAI declined to generate insights for this request.",
                )
            if content.get("type") == "output_text":
                text_parts.append(content.get("text", ""))
    if not text_parts:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned no insight content.",
        )
    return "".join(text_parts)


def _request_openai_insights(metrics: dict) -> OperationalInsights:
    if settings.OPENAI_API_KEY is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Insights is not configured. Set OPENAI_API_KEY on the backend.",
        )

    request_payload = {
        "model": settings.OPENAI_MODEL,
        "store": False,
        "max_output_tokens": 1200,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(metrics, separators=(",", ":")),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "operational_insights",
                "strict": True,
                "schema": INSIGHT_SCHEMA,
            }
        },
    }

    try:
        with httpx.Client(
            timeout=httpx.Timeout(25.0, connect=5.0)
        ) as client:
            response = client.post(
                OPENAI_RESPONSES_URL,
                headers={
                    "Authorization": (
                        f"Bearer {settings.OPENAI_API_KEY.get_secret_value()}"
                    ),
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
    except httpx.TimeoutException as error:
        logger.warning("OpenAI insights request timed out.")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="OpenAI did not respond in time. Try again.",
        ) from error
    except httpx.RequestError as error:
        logger.warning("Could not reach OpenAI for insights.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach OpenAI. Try again later.",
        ) from error

    if not response.is_success:
        logger.warning(
            "OpenAI insights request failed with status %s.",
            response.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "OpenAI could not generate insights "
                f"(provider status {response.status_code})."
            ),
        )

    try:
        provider_payload = response.json()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned an invalid response.",
        ) from error
    if not isinstance(provider_payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned an invalid response.",
        )
    output = _output_text(provider_payload)

    try:
        return OperationalInsights.model_validate_json(output)
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned insights that did not match the required format.",
        ) from error


def generate_insights(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    start_date: date,
    end_date: date,
    site_id: UUID | None,
) -> GeneratedInsightsResponse:
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The insight start date must be on or before its end date.",
        )
    if (end_date - start_date).days > 365:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Insights can cover at most 366 days at a time.",
        )
    if site_id is not None and not has_site_access(
        db, user_id, site_id, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Site access denied.",
        )
    if settings.OPENAI_API_KEY is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Insights is not configured. Set OPENAI_API_KEY on the backend.",
        )

    snapshot = build_reports_snapshot(
        db,
        user_id,
        organization_id,
        start_date,
        end_date,
        site_id,
    )
    insights = _request_openai_insights(_metrics_for_prompt(snapshot))
    return GeneratedInsightsResponse(
        generated_at=datetime.now(timezone.utc),
        start_date=start_date,
        end_date=end_date,
        site_id=site_id,
        model=settings.OPENAI_MODEL,
        insights=insights.insights,
    )
