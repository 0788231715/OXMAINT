from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.security import create_access_token, hash_password
from backend.app.config import settings
from backend.app.database.base import Base
from backend.app.database.connection import get_db
import backend.app.database.models
from backend.app.database.models.asset import Asset, AssetCategory
from backend.app.database.models.identity import (
    Permission,
    Role,
    RolePermission,
    User,
    UserDepartmentAccess,
    UserRoleAssignment,
    UserSiteAccess,
)
from backend.app.database.models.incident import Incident
from backend.app.database.models.maintenance_work_order import MaintenanceWorkOrder
from backend.app.database.models.organization import Department, Organization, Site
from backend.app.database.models.service_request import ServiceRequest
from backend.app.main import app


@pytest.fixture
def incident_api_context():
    test_engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    connection = test_engine.connect()
    transaction = connection.begin()
    db = Session(connection, join_transaction_mode="create_savepoint")
    organization = Organization(
        name="Incident API Test Organization",
        code=f"INCIDENT_TEST_{uuid4().hex[:8].upper()}",
    )
    db.add(organization)
    db.flush()

    site = Site(
        organization_id=organization.id,
        name="Incident API Test Site",
        code=f"INCIDENT_SITE_{uuid4().hex[:8].upper()}",
    )
    department = Department(
        organization_id=organization.id,
        name="Incident API Test Department",
        code=f"INCIDENT_DEPT_{uuid4().hex[:8].upper()}",
    )
    user = User(
        email=f"incident-api-{uuid4().hex[:8]}@example.com",
        display_name="Incident API Test User",
        password_hash=hash_password("IncidentApiPassword123!"),
        is_active=True,
    )
    role = Role(
        code=f"INCIDENT_TEST_ROLE_{uuid4().hex[:8].upper()}",
        name="Incident API Test Role",
        is_active=True,
    )
    permissions = [
        Permission(
            code=code,
            name=name,
            module=module,
            action=action,
        )
        for code, name, module, action in (
            ("incidents.create", "Report Incidents", "incident_management", "create"),
            ("incidents.view", "View Incidents", "incident_management", "view"),
            ("incidents.update", "Update Incidents", "incident_management", "update"),
            ("reports.view", "View Operations Reports", "reports", "view"),
            ("ai_insights.generate", "Generate AI Insights", "ai_insights", "generate"),
            ("operations_map.view", "View Operations Map", "operations_map", "view"),
            ("service_requests.create", "Create Service Requests", "service_requests", "create"),
            ("service_requests.transition", "Transition Service Requests", "service_requests", "transition"),
            ("maintenance.create", "Create Work Orders", "maintenance_calendar", "create"),
            ("maintenance.transition", "Transition Work Orders", "maintenance_calendar", "transition"),
        )
    ]
    db.add_all([site, department, user, role, *permissions])
    db.flush()
    db.add_all(
        [
            RolePermission(role_id=role.id, permission_id=permission.id)
            for permission in permissions
        ]
        + [
            UserRoleAssignment(
                user_id=user.id,
                role_id=role.id,
                organization_id=organization.id,
            ),
            UserSiteAccess(user_id=user.id, site_id=site.id),
            UserDepartmentAccess(
                user_id=user.id,
                department_id=department.id,
            ),
        ]
    )
    db.flush()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    token = create_access_token(subject=str(user.id))
    try:
        with TestClient(app) as client:
            yield {
                "client": client,
                "db": db,
                "organization": organization,
                "site": site,
                "department": department,
                "user": user,
                "token": token,
            }
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        transaction.rollback()
        connection.close()
        test_engine.dispose()


def _headers(context):
    return {"Authorization": f"Bearer {context['token']}"}


def _payload(context):
    return {
        "organization_id": str(context["organization"].id),
        "site_id": str(context["site"].id),
        "department_id": str(context["department"].id),
        "title": "Water leak near the pump",
        "description": "Water was found leaking near the north pump.",
        "category": "equipment_damage",
        "severity": "high",
        "occurred_at": "2026-10-01T10:00:00Z",
    }


def test_incident_create_filter_and_status_workflow(incident_api_context):
    context = incident_api_context
    created = context["client"].post(
        f"/api/v1/incidents?organization_id={context['organization'].id}",
        headers=_headers(context),
        json=_payload(context),
    )

    assert created.status_code == 201
    incident = created.json()
    assert incident["status"] == "reported"
    assert incident["reported_by"] == str(context["user"].id)

    listing = context["client"].get(
        f"/api/v1/incidents?organization_id={context['organization'].id}"
        "&status=reported&severity=high&search=pump",
        headers=_headers(context),
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == incident["id"]

    investigating = context["client"].patch(
        f"/api/v1/incidents/{incident['id']}?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={"status": "investigating"},
    )
    assert investigating.status_code == 200
    assert investigating.json()["status"] == "investigating"

    invalid_transition = context["client"].patch(
        f"/api/v1/incidents/{incident['id']}?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={"status": "closed"},
    )
    assert invalid_transition.status_code == 409

    missing_resolution = context["client"].patch(
        f"/api/v1/incidents/{incident['id']}?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={"status": "resolved"},
    )
    assert missing_resolution.status_code == 422

    resolved = context["client"].patch(
        f"/api/v1/incidents/{incident['id']}?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={"status": "resolved", "resolution": "Pump isolated and leak repaired."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    closed = context["client"].patch(
        f"/api/v1/incidents/{incident['id']}?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={"status": "closed"},
    )
    assert closed.status_code == 200


def test_incident_create_requires_access_to_site(incident_api_context):
    context = incident_api_context
    inaccessible_site = Site(
        organization_id=context["organization"].id,
        name="Unassigned Incident Test Site",
        code=f"NO_ACCESS_{uuid4().hex[:8].upper()}",
    )
    context["db"].add(inaccessible_site)
    context["db"].flush()
    payload = _payload(context)
    payload["site_id"] = str(inaccessible_site.id)

    response = context["client"].post(
        f"/api/v1/incidents?organization_id={context['organization'].id}",
        headers=_headers(context),
        json=payload,
    )

    assert response.status_code == 403


def test_reports_aggregate_period_data_with_site_and_department_scope(
    incident_api_context,
):
    context = incident_api_context
    db = context["db"]
    organization = context["organization"]
    site = context["site"]
    department = context["department"]
    category = AssetCategory(
        organization_id=organization.id,
        name="Report Test Category",
        code=f"REPORT_CATEGORY_{uuid4().hex[:8].upper()}",
        is_active=True,
    )
    db.add(category)
    db.flush()
    asset = Asset(
        organization_id=organization.id,
        category_id=category.id,
        site_id=site.id,
        department_id=department.id,
        asset_tag=f"REPORT_ASSET_{uuid4().hex[:8].upper()}",
        name="Report Test Pump",
        status="in_service",
        criticality="high",
        is_active=True,
    )
    inaccessible_department = Department(
        organization_id=organization.id,
        name="Unassigned Report Department",
        code=f"REPORT_DEPT_{uuid4().hex[:8].upper()}",
    )
    db.add_all([asset, inaccessible_department])
    db.flush()
    period_time = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)
    db.add_all(
        [
            Incident(
                organization_id=organization.id,
                site_id=site.id,
                department_id=department.id,
                reported_by=context["user"].id,
                incident_number=f"INC-REPORT-{uuid4().hex[:8]}",
                title="In-period incident",
                description="Incident included in the report period.",
                category="safety",
                severity="high",
                status="reported",
                occurred_at=period_time,
            ),
            Incident(
                organization_id=organization.id,
                site_id=site.id,
                department_id=department.id,
                reported_by=context["user"].id,
                incident_number=f"INC-OLD-{uuid4().hex[:8]}",
                title="Out-of-period incident",
                description="Incident outside the report period.",
                category="safety",
                severity="critical",
                status="reported",
                occurred_at=datetime(2026, 9, 5, 10, tzinfo=timezone.utc),
            ),
            Incident(
                organization_id=organization.id,
                site_id=site.id,
                department_id=inaccessible_department.id,
                reported_by=context["user"].id,
                incident_number=f"INC-SCOPE-{uuid4().hex[:8]}",
                title="Out-of-scope incident",
                description="Incident in a department without access.",
                category="safety",
                severity="critical",
                status="reported",
                occurred_at=period_time,
            ),
            ServiceRequest(
                organization_id=organization.id,
                site_id=site.id,
                department_id=department.id,
                asset_id=asset.id,
                requester_id=context["user"].id,
                request_number=f"REQ-REPORT-{uuid4().hex[:8]}",
                title="In-period service request",
                description="Request included in report.",
                category="maintenance",
                priority="high",
                status="submitted",
                submitted_at=period_time,
            ),
            MaintenanceWorkOrder(
                organization_id=organization.id,
                asset_id=asset.id,
                site_id=site.id,
                department_id=department.id,
                created_by=context["user"].id,
                work_order_number=f"WO-REPORT-{uuid4().hex[:8]}",
                title="In-period work order",
                description="Work order included in report.",
                work_order_type="preventive",
                priority="normal",
                status="completed",
                scheduled_at=period_time,
                completed_at=period_time,
            ),
        ]
    )
    db.flush()

    response = context["client"].get(
        f"/api/v1/reports?organization_id={organization.id}"
        "&start_date=2026-10-01&end_date=2026-10-31",
        headers=_headers(context),
    )

    assert response.status_code == 200
    report = response.json()
    assert report["summary"] == {
        "assets": 1,
        "requests": 1,
        "open_requests": 1,
        "incidents": 1,
        "open_incidents": 1,
        "work_orders": 1,
        "completed_work_orders": 1,
    }
    assert {item["label"]: item["count"] for item in report["incident_severity"]}[
        "high"
    ] == 1
    trend = next(item for item in report["daily_trend"] if item["date"] == "2026-10-05")
    assert trend == {
        "date": "2026-10-05",
        "requests": 1,
        "incidents": 1,
        "work_orders": 1,
    }


def test_reports_validate_date_range_and_site_access(incident_api_context):
    context = incident_api_context
    organization = context["organization"]
    inaccessible_site = Site(
        organization_id=organization.id,
        name="Unassigned Report Site",
        code=f"REPORT_NO_ACCESS_{uuid4().hex[:8].upper()}",
    )
    context["db"].add(inaccessible_site)
    context["db"].flush()

    reversed_dates = context["client"].get(
        f"/api/v1/reports?organization_id={organization.id}"
        "&start_date=2026-10-31&end_date=2026-10-01",
        headers=_headers(context),
    )
    assert reversed_dates.status_code == 422

    inaccessible_filter = context["client"].get(
        f"/api/v1/reports?organization_id={organization.id}"
        f"&site_id={inaccessible_site.id}",
        headers=_headers(context),
    )
    assert inaccessible_filter.status_code == 403


def test_operations_map_aggregates_only_accessible_site_and_department_data(
    incident_api_context,
):
    context = incident_api_context
    db = context["db"]
    organization = context["organization"]
    site = context["site"]
    department = context["department"]
    inaccessible_department = Department(
        organization_id=organization.id,
        name="Unassigned Operations Department",
        code=f"OPS_DEPT_{uuid4().hex[:8].upper()}",
    )
    inaccessible_site = Site(
        organization_id=organization.id,
        name="Unassigned Operations Site",
        code=f"OPS_SITE_{uuid4().hex[:8].upper()}",
    )
    category = AssetCategory(
        organization_id=organization.id,
        name="Operations Map Category",
        code=f"OPS_CATEGORY_{uuid4().hex[:8].upper()}",
        is_active=True,
    )
    db.add_all([inaccessible_department, inaccessible_site, category])
    db.flush()
    accessible_asset = Asset(
        organization_id=organization.id,
        category_id=category.id,
        site_id=site.id,
        department_id=department.id,
        asset_tag=f"OPS_ASSET_{uuid4().hex[:8].upper()}",
        name="Accessible operations asset",
        status="in_service",
        criticality="high",
        is_active=True,
    )
    inaccessible_asset = Asset(
        organization_id=organization.id,
        category_id=category.id,
        site_id=site.id,
        department_id=inaccessible_department.id,
        asset_tag=f"OPS_HIDDEN_ASSET_{uuid4().hex[:8].upper()}",
        name="Out-of-scope operations asset",
        status="out_of_service",
        criticality="high",
        is_active=True,
    )
    db.add_all([accessible_asset, inaccessible_asset])
    db.flush()

    now = datetime.now(timezone.utc)
    db.add_all(
        [
            Incident(
                organization_id=organization.id,
                site_id=site.id,
                department_id=department.id,
                reported_by=context["user"].id,
                incident_number=f"INC-OPS-{uuid4().hex[:8]}",
                title="Accessible high-severity incident",
                description="Open incident in accessible scope.",
                category="safety",
                severity="high",
                status="reported",
                occurred_at=now,
            ),
            Incident(
                organization_id=organization.id,
                site_id=site.id,
                department_id=inaccessible_department.id,
                reported_by=context["user"].id,
                incident_number=f"INC-OPS-HIDDEN-{uuid4().hex[:8]}",
                title="Out-of-scope incident",
                description="Incident in a department without access.",
                category="safety",
                severity="critical",
                status="reported",
                occurred_at=now,
            ),
            ServiceRequest(
                organization_id=organization.id,
                site_id=site.id,
                department_id=department.id,
                asset_id=accessible_asset.id,
                requester_id=context["user"].id,
                request_number=f"REQ-OPS-{uuid4().hex[:8]}",
                title="Accessible open request",
                description="Request in accessible scope.",
                category="maintenance",
                priority="high",
                status="submitted",
            ),
            ServiceRequest(
                organization_id=organization.id,
                site_id=site.id,
                department_id=inaccessible_department.id,
                asset_id=inaccessible_asset.id,
                requester_id=context["user"].id,
                request_number=f"REQ-OPS-HIDDEN-{uuid4().hex[:8]}",
                title="Out-of-scope request",
                description="Request in a department without access.",
                category="maintenance",
                priority="high",
                status="submitted",
            ),
            MaintenanceWorkOrder(
                organization_id=organization.id,
                asset_id=accessible_asset.id,
                site_id=site.id,
                department_id=department.id,
                created_by=context["user"].id,
                work_order_number=f"WO-OPS-{uuid4().hex[:8]}",
                title="Accessible overdue work",
                description="Overdue work in accessible scope.",
                work_order_type="preventive",
                priority="normal",
                status="scheduled",
                scheduled_at=now - timedelta(days=1),
            ),
            MaintenanceWorkOrder(
                organization_id=organization.id,
                asset_id=inaccessible_asset.id,
                site_id=site.id,
                department_id=inaccessible_department.id,
                created_by=context["user"].id,
                work_order_number=f"WO-OPS-HIDDEN-{uuid4().hex[:8]}",
                title="Out-of-scope work",
                description="Work order in a department without access.",
                work_order_type="preventive",
                priority="normal",
                status="scheduled",
                scheduled_at=now - timedelta(days=1),
            ),
        ]
    )
    db.flush()

    response = context["client"].get(
        f"/api/v1/operations-map?organization_id={organization.id}",
        headers=_headers(context),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == {
        "sites": 1,
        "assets": 1,
        "open_requests": 1,
        "open_incidents": 1,
        "overdue_work_orders": 1,
    }
    assert len(data["sites"]) == 1
    assert data["sites"][0]["site_id"] == str(site.id)
    assert data["sites"][0]["asset_status"]["in_service"] == 1
    assert data["sites"][0]["high_severity_incidents"] == 1
    assert data["sites"][0]["open_work_orders"] == 1


def test_synchronization_receipt_makes_offline_incident_create_idempotent(
    incident_api_context,
):
    context = incident_api_context
    organization = context["organization"]
    operation_id = uuid4()
    operation = {
        "operation_id": str(operation_id),
        "organization_id": str(organization.id),
        "operation_type": "incident.create",
        "record_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": _payload(context),
    }
    endpoint = (
        f"/api/v1/synchronization/operations?organization_id={organization.id}"
    )

    created = context["client"].post(
        endpoint,
        headers=_headers(context),
        json=operation,
    )
    duplicate = context["client"].post(
        endpoint,
        headers=_headers(context),
        json=operation,
    )

    assert created.status_code == 200
    assert duplicate.status_code == 200
    assert created.json()["result"]["record_id"] == duplicate.json()["result"]["record_id"]
    assert duplicate.json()["duplicate"] is True

    changed_payload = {
        **operation,
        "payload": {**operation["payload"], "title": "Changed after queueing"},
    }
    conflicting_reuse = context["client"].post(
        endpoint,
        headers=_headers(context),
        json=changed_payload,
    )
    assert conflicting_reuse.status_code == 409


def test_synchronization_keeps_incident_transition_guards(
    incident_api_context,
):
    context = incident_api_context
    organization = context["organization"]
    endpoint = (
        f"/api/v1/synchronization/operations?organization_id={organization.id}"
    )
    created = context["client"].post(
        endpoint,
        headers=_headers(context),
        json={
            "operation_id": str(uuid4()),
            "organization_id": str(organization.id),
            "operation_type": "incident.create",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": _payload(context),
        },
    )
    assert created.status_code == 200

    invalid_transition = context["client"].post(
        endpoint,
        headers=_headers(context),
        json={
            "operation_id": str(uuid4()),
            "organization_id": str(organization.id),
            "operation_type": "incident.update",
            "record_id": created.json()["result"]["record_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"status": "closed"},
        },
    )
    assert invalid_transition.status_code == 409


def test_synchronization_rejects_offline_operations_outside_site_scope(
    incident_api_context,
):
    context = incident_api_context
    organization = context["organization"]
    inaccessible_site = Site(
        organization_id=organization.id,
        name="Unassigned Offline Sync Site",
        code=f"SYNC_NO_ACCESS_{uuid4().hex[:8].upper()}",
    )
    context["db"].add(inaccessible_site)
    context["db"].flush()
    payload = _payload(context)
    payload["site_id"] = str(inaccessible_site.id)

    response = context["client"].post(
        f"/api/v1/synchronization/operations?organization_id={organization.id}",
        headers=_headers(context),
        json={
            "operation_id": str(uuid4()),
            "organization_id": str(organization.id),
            "operation_type": "incident.create",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        },
    )

    assert response.status_code == 403


def test_synchronization_accepts_offline_request_and_work_order_creates(
    incident_api_context,
):
    context = incident_api_context
    organization = context["organization"]
    site = context["site"]
    department = context["department"]
    db = context["db"]
    category = AssetCategory(
        organization_id=organization.id,
        name="Offline sync asset category",
        code=f"SYNC_CATEGORY_{uuid4().hex[:8].upper()}",
        is_active=True,
    )
    db.add(category)
    db.flush()
    asset = Asset(
        organization_id=organization.id,
        category_id=category.id,
        site_id=site.id,
        department_id=department.id,
        asset_tag=f"SYNC_ASSET_{uuid4().hex[:8].upper()}",
        name="Offline sync pump",
        status="in_service",
        criticality="medium",
        is_active=True,
    )
    db.add(asset)
    db.flush()

    endpoint = (
        f"/api/v1/synchronization/operations?organization_id={organization.id}"
    )
    created_request = context["client"].post(
        endpoint,
        headers=_headers(context),
        json={
            "operation_id": str(uuid4()),
            "organization_id": str(organization.id),
            "operation_type": "service_request.create",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "organization_id": str(organization.id),
                "site_id": str(site.id),
                "department_id": str(department.id),
                "asset_id": str(asset.id),
                "title": "Offline request",
                "description": "A request queued while disconnected.",
                "category": "maintenance",
                "priority": "normal",
                "safety_critical": False,
            },
        },
    )
    created_work_order = context["client"].post(
        endpoint,
        headers=_headers(context),
        json={
            "operation_id": str(uuid4()),
            "organization_id": str(organization.id),
            "operation_type": "maintenance_work_order.create",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "organization_id": str(organization.id),
                "asset_id": str(asset.id),
                "title": "Offline work order",
                "description": "A work order queued while disconnected.",
                "work_order_type": "preventive",
                "priority": "normal",
                "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            },
        },
    )

    assert created_request.status_code == 200
    assert created_request.json()["result"]["record_id"]
    assert created_work_order.status_code == 200
    assert created_work_order.json()["result"]["record_id"]


def test_ai_insights_sends_aggregates_only_after_consent(
    incident_api_context, monkeypatch
):
    context = incident_api_context
    db = context["db"]
    period_time = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)
    db.add(
        Incident(
            organization_id=context["organization"].id,
            site_id=context["site"].id,
            department_id=context["department"].id,
            reported_by=context["user"].id,
            incident_number=f"INC-AI-{uuid4().hex[:8]}",
            title="Confidential incident title",
            description="Confidential incident record description.",
            category="safety",
            severity="critical",
            status="reported",
            occurred_at=period_time,
        )
    )
    db.flush()

    captured_request = {}
    provider_body = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "insights": [
                                    {
                                        "title": "Review critical incident follow-up",
                                        "category": "safety",
                                        "severity": "urgent",
                                        "evidence": [
                                            "1 critical incident was reported in this period."
                                        ],
                                        "recommendation": (
                                            "Review its status and ensure the "
                                            "appropriate follow-up is recorded."
                                        ),
                                    }
                                ]
                            }
                        ),
                    }
                ],
            }
        ],
    }

    def handle_openai(request):
        captured_request["authorization"] = request.headers["Authorization"]
        captured_request["body"] = json.loads(request.content)
        return httpx.Response(200, json=provider_body)

    mocked_client = httpx.Client(
        transport=httpx.MockTransport(handle_openai)
    )
    from backend.app.modules.ai_insights.services import openai_service

    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr("test-api-key"))
    monkeypatch.setattr(
        openai_service.httpx,
        "Client",
        lambda **kwargs: mocked_client,
    )

    response = context["client"].post(
        f"/api/v1/ai-insights/generate?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
            "confirm_external_processing": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["insights"][0]["severity"] == "urgent"
    assert captured_request["authorization"] == "Bearer test-api-key"
    assert captured_request["body"]["store"] is False
    prompt_metrics = json.loads(captured_request["body"]["input"][1]["content"])
    assert prompt_metrics["summary"]["incidents"] == 1
    serialized_metrics = json.dumps(prompt_metrics)
    assert "Confidential incident title" not in serialized_metrics
    assert "Confidential incident record description" not in serialized_metrics
    assert str(context["user"].id) not in serialized_metrics
    mocked_client.close()


def test_ai_insights_require_consent_and_backend_configuration(
    incident_api_context, monkeypatch
):
    context = incident_api_context
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    url = (
        f"/api/v1/ai-insights/generate"
        f"?organization_id={context['organization'].id}"
    )

    missing_consent = context["client"].post(
        url,
        headers=_headers(context),
        json={"start_date": "2026-10-01", "end_date": "2026-10-31"},
    )
    assert missing_consent.status_code == 422

    missing_configuration = context["client"].post(
        url,
        headers=_headers(context),
        json={
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
            "confirm_external_processing": True,
        },
    )
    assert missing_configuration.status_code == 503
