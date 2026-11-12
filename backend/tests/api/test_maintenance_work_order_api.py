from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.security import create_access_token, hash_password
from backend.app.database.base import Base
from backend.app.database.connection import get_db
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
from backend.app.database.models.organization import Department, Organization, Site
from backend.app.database.models.work_order_assignment import WorkOrderAssignment
from backend.app.main import app
import backend.app.database.models


@pytest.fixture
def maintenance_api_context():
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
        name="Maintenance API Test Organization",
        code=f"MAINT_TEST_{uuid4().hex[:8].upper()}",
    )
    db.add(organization)
    db.flush()
    site = Site(
        organization_id=organization.id,
        name="Maintenance API Test Site",
        code=f"MAINT_SITE_{uuid4().hex[:8].upper()}",
    )
    department = Department(
        organization_id=organization.id,
        name="Maintenance API Test Department",
        code=f"MAINT_DEPT_{uuid4().hex[:8].upper()}",
    )
    user = User(
        email=f"maintenance-api-{uuid4().hex[:8]}@example.com",
        display_name="Maintenance API Test User",
        password_hash=hash_password("MaintenanceApiPassword123!"),
        is_active=True,
    )
    role = Role(
        code=f"MAINT_TEST_ROLE_{uuid4().hex[:8].upper()}",
        name="Maintenance API Test Role",
        is_active=True,
    )
    permissions = [
        Permission(
            code=code,
            name=name,
            module="maintenance_calendar",
            action=action,
        )
        for code, name, action in (
            ("maintenance.view", "View Work Orders", "view"),
            ("maintenance.create", "Create Work Orders", "create"),
            ("maintenance.transition", "Transition Work Orders", "transition"),
            ("coordination.view", "View Coordination", "view"),
            ("coordination.assign", "Assign Work Orders", "assign"),
        )
    ]
    technician_role = Role(
        code="maintenance_technician",
        name="Maintenance Technician",
        is_active=True,
    )
    technician = User(
        email=f"maintenance-technician-{uuid4().hex[:8]}@example.com",
        display_name="Maintenance Technician",
        password_hash=hash_password("MaintenanceApiPassword123!"),
        is_active=True,
    )
    category = AssetCategory(
        organization_id=organization.id,
        name="Maintenance Test Category",
        code=f"MAINT_CATEGORY_{uuid4().hex[:8].upper()}",
        is_active=True,
    )
    db.add_all(
        [
            site,
            department,
            user,
            role,
            technician_role,
            technician,
            *permissions,
            category,
        ]
    )
    db.flush()
    asset = Asset(
        organization_id=organization.id,
        category_id=category.id,
        site_id=site.id,
        department_id=department.id,
        asset_tag=f"MAINT_ASSET_{uuid4().hex[:8].upper()}",
        name="Test Pump",
        status="in_service",
        criticality="medium",
        is_active=True,
    )
    db.add(asset)
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
            UserRoleAssignment(
                user_id=technician.id,
                role_id=technician_role.id,
                organization_id=organization.id,
            ),
            UserSiteAccess(user_id=technician.id, site_id=site.id),
            UserDepartmentAccess(
                user_id=technician.id,
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
                "asset": asset,
                "user": user,
                "technician": technician,
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
        "asset_id": str(context["asset"].id),
        "title": "Quarterly pump inspection",
        "description": "Inspect seals and test the pump under normal load.",
        "work_order_type": "preventive",
        "priority": "high",
        "scheduled_at": "2026-12-01T10:00:00Z",
    }


def test_work_order_create_filter_and_completion_workflow(maintenance_api_context):
    context = maintenance_api_context
    created = context["client"].post(
        f"/api/v1/maintenance/work-orders?organization_id={context['organization'].id}",
        headers=_headers(context),
        json=_payload(context),
    )

    assert created.status_code == 201
    work_order = created.json()
    assert work_order["status"] == "scheduled"
    assert work_order["created_by"] == str(context["user"].id)

    listing = context["client"].get(
        f"/api/v1/maintenance/work-orders?organization_id={context['organization'].id}"
        "&status=scheduled&type=preventive&search=pump",
        headers=_headers(context),
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == work_order["id"]

    started = context["client"].post(
        f"/api/v1/maintenance/work-orders/{work_order['id']}/transition"
        f"?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={"status": "in_progress"},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    missing_note = context["client"].post(
        f"/api/v1/maintenance/work-orders/{work_order['id']}/transition"
        f"?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={"status": "completed"},
    )
    assert missing_note.status_code == 422

    completed = context["client"].post(
        f"/api/v1/maintenance/work-orders/{work_order['id']}/transition"
        f"?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={
            "status": "completed",
            "completion_note": "Inspection passed; seals are serviceable.",
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None


def test_work_order_create_requires_access_to_asset_site(maintenance_api_context):
    context = maintenance_api_context
    inaccessible_site = Site(
        organization_id=context["organization"].id,
        name="Unassigned Maintenance Test Site",
        code=f"NO_ACCESS_{uuid4().hex[:8].upper()}",
    )
    context["db"].add(inaccessible_site)
    context["db"].flush()
    inaccessible_asset = Asset(
        organization_id=context["organization"].id,
        category_id=context["asset"].category_id,
        site_id=inaccessible_site.id,
        asset_tag=f"NO_ACCESS_{uuid4().hex[:8].upper()}",
        name="Unassigned Test Pump",
        status="in_service",
        criticality="medium",
        is_active=True,
    )
    context["db"].add(inaccessible_asset)
    context["db"].flush()
    payload = _payload(context)
    payload["asset_id"] = str(inaccessible_asset.id)

    response = context["client"].post(
        f"/api/v1/maintenance/work-orders?organization_id={context['organization'].id}",
        headers=_headers(context),
        json=payload,
    )

    assert response.status_code == 403


def test_coordination_assigns_eligible_technician_and_records_handoff(
    maintenance_api_context,
):
    context = maintenance_api_context
    work_order_response = context["client"].post(
        f"/api/v1/maintenance/work-orders?organization_id={context['organization'].id}",
        headers=_headers(context),
        json=_payload(context),
    )
    assert work_order_response.status_code == 201
    work_order = work_order_response.json()

    assigned = context["client"].post(
        f"/api/v1/coordination/work-orders/{work_order['id']}/assign"
        f"?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={
            "assigned_to": str(context["technician"].id),
            "handoff_note": "Check the seal before startup.",
        },
    )
    assert assigned.status_code == 201
    assert assigned.json()["assignee_name"] == "Maintenance Technician"

    second_technician = User(
        email=f"maintenance-technician-2-{uuid4().hex[:8]}@example.com",
        display_name="Second Maintenance Technician",
        password_hash=hash_password("MaintenanceApiPassword123!"),
        is_active=True,
    )
    technician_role = context["db"].query(Role).filter_by(
        code="maintenance_technician"
    ).one()
    context["db"].add(second_technician)
    context["db"].flush()
    context["db"].add_all(
        [
            UserRoleAssignment(
                user_id=second_technician.id,
                role_id=technician_role.id,
                organization_id=context["organization"].id,
            ),
            UserSiteAccess(
                user_id=second_technician.id,
                site_id=context["site"].id,
            ),
            UserDepartmentAccess(
                user_id=second_technician.id,
                department_id=context["department"].id,
            ),
        ]
    )
    context["db"].flush()
    handoff = context["client"].post(
        f"/api/v1/coordination/work-orders/{work_order['id']}/assign"
        f"?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={
            "assigned_to": str(second_technician.id),
            "handoff_note": "Passing the work to the incoming technician.",
        },
    )
    assert handoff.status_code == 201

    listing = context["client"].get(
        f"/api/v1/coordination/work-orders?organization_id={context['organization'].id}",
        headers=_headers(context),
    )
    assert listing.status_code == 200
    assert listing.json()["items"][0]["current_assignment"]["assigned_to"] == str(
        second_technician.id
    )

    history = context["client"].get(
        f"/api/v1/coordination/work-orders/{work_order['id']}/history"
        f"?organization_id={context['organization'].id}",
        headers=_headers(context),
    )
    assert history.status_code == 200
    assert len(history.json()["items"]) == 2
    assert history.json()["items"][0]["handoff_note"] == (
        "Passing the work to the incoming technician."
    )
    assert history.json()["items"][1]["handoff_note"] == (
        "Check the seal before startup."
    )


def test_coordination_rejects_technician_without_matching_site_access(
    maintenance_api_context,
):
    context = maintenance_api_context
    work_order_response = context["client"].post(
        f"/api/v1/maintenance/work-orders?organization_id={context['organization'].id}",
        headers=_headers(context),
        json=_payload(context),
    )
    work_order = work_order_response.json()
    inaccessible_technician = User(
        email=f"inaccessible-tech-{uuid4().hex[:8]}@example.com",
        display_name="Inaccessible Technician",
        password_hash=hash_password("MaintenanceApiPassword123!"),
        is_active=True,
    )
    technician_role = context["db"].query(Role).filter_by(
        code="maintenance_technician"
    ).one()
    context["db"].add(inaccessible_technician)
    context["db"].flush()
    context["db"].add(
        UserRoleAssignment(
            user_id=inaccessible_technician.id,
            role_id=technician_role.id,
            organization_id=context["organization"].id,
        )
    )
    context["db"].flush()

    response = context["client"].post(
        f"/api/v1/coordination/work-orders/{work_order['id']}/assign"
        f"?organization_id={context['organization'].id}",
        headers=_headers(context),
        json={"assigned_to": str(inaccessible_technician.id)},
    )
    assert response.status_code == 422
    assert context["db"].query(WorkOrderAssignment).count() == 0
