from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.security import create_access_token, hash_password
from backend.app.database.connection import engine, get_db
from backend.app.database.models.organization import Organization
from backend.app.database.models.identity import (
    User,
    Role,
    Permission,
    RolePermission,
    UserRoleAssignment,
)
from backend.app.database.models.asset import AssetCategory


@pytest.fixture
def category_api_context():
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")

    suffix = uuid4().hex[:10]

    organization = Organization(
        name="Category Test Organization",
        code=f"CAT_TEST_ORG_{suffix}",
    )

    user = User(
        email=f"category-test-{suffix}@example.com",
        display_name="Category API Test User",
        password_hash=hash_password("CategoryTestPassword123!"),
        is_active=True,
    )

    role = Role(
        code=f"CAT_TEST_ROLE_{suffix}",
        name="Category API Test Role",
        is_active=True,
    )

    create_permission = Permission(
        code="assets.categories.create",
        name="Create Asset Categories",
        module="asset_management",
        action="create",
    )

    view_permission = Permission(
        code="assets.categories.view",
        name="View Asset Categories",
        module="asset_management",
        action="view",
    )

    update_permission = Permission(
        code="assets.categories.update",
        name="Update Asset Categories",
        module="asset_management",
        action="update",
    )

    deactivate_permission = Permission(
        code="assets.categories.deactivate",
        name="Deactivate Asset Categories",
        module="asset_management",
        action="deactivate",
    )

    reactivate_permission = Permission(
        code="assets.categories.reactivate",
        name="Reactivate Asset Categories",
        module="asset_management",
        action="reactivate",
    )

    db.add_all([
        organization,
        user,
        role,
        create_permission,
        view_permission,
        update_permission,
        deactivate_permission,
        reactivate_permission,
    ])
    db.flush()

    create_role_permission = RolePermission(
        role_id=role.id,
        permission_id=create_permission.id,
    )

    view_role_permission = RolePermission(
        role_id=role.id,
        permission_id=view_permission.id,
    )

    update_role_permission = RolePermission(
        role_id=role.id,
        permission_id=update_permission.id,
    )

    deactivate_role_permission = RolePermission(
        role_id=role.id,
        permission_id=deactivate_permission.id,
    )

    reactivate_role_permission = RolePermission(
        role_id=role.id,
        permission_id=reactivate_permission.id,
    )

    role_assignment = UserRoleAssignment(
        user_id=user.id,
        role_id=role.id,
        organization_id=organization.id,
    )

    db.add_all([
        create_role_permission,
        view_role_permission,
        update_role_permission,
        deactivate_role_permission,
        reactivate_role_permission,
        role_assignment,
    ])
    db.flush()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(subject=str(user.id))

    context = {
        "db": db,
        "organization": organization,
        "user": user,
        "role": role,
        "create_role_permission": create_role_permission,
        "view_role_permission": view_role_permission,
        "update_role_permission": update_role_permission,
        "deactivate_role_permission": deactivate_role_permission,
        "reactivate_role_permission": reactivate_role_permission,
        "token": token,
        "suffix": suffix,
        "client": None,
    }

    try:
        with TestClient(app) as client:
            context["client"] = client
            yield context
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        transaction.rollback()
        connection.close()


def category_payload(context, name="Electrical Equipment", code=None):
    return {
        "organization_id": str(context["organization"].id),
        "name": name,
        "code": code or f"ELEC_{context['suffix']}",
        "description": "Electrical assets and equipment",
    }


def category_headers(context):
    return {
        "Authorization": f"Bearer {context['token']}"
    }


def create_category_request(context, payload=None, organization_id=None):
    selected_org = organization_id or context["organization"].id

    return context["client"].post(
        "/api/v1/asset-categories",
        params={"organization_id": str(selected_org)},
        json=payload or category_payload(context),
        headers=category_headers(context),
    )


def list_categories_request(context, **params):
    query = {
        "organization_id": str(context["organization"].id),
        **params,
    }

    return context["client"].get(
        "/api/v1/asset-categories",
        params=query,
        headers=category_headers(context),
    )


def create_db_category(context, name, code):
    category = AssetCategory(
        organization_id=context["organization"].id,
        name=name,
        code=code,
        description=f"{name} description",
        is_active=True,
    )
    context["db"].add(category)
    context["db"].flush()
    return category


def test_authorized_user_can_create_asset_category(category_api_context):
    context = category_api_context

    response = create_category_request(context)

    assert response.status_code == 201, response.text
    result = response.json()

    assert result["name"] == "Electrical Equipment"
    assert result["code"] == f"ELEC_{context['suffix']}"
    assert result["organization_id"] == str(context["organization"].id)
    assert result["is_active"] is True


def test_category_creation_requires_permission(category_api_context):
    context = category_api_context

    context["db"].delete(context["create_role_permission"])
    context["db"].flush()

    response = create_category_request(context)

    assert response.status_code == 403


def test_category_creation_rejects_organization_mismatch(
    category_api_context,
):
    context = category_api_context
    payload = category_payload(context)
    payload["organization_id"] = str(uuid4())

    response = create_category_request(context, payload=payload)

    assert response.status_code == 403


def test_category_creation_rejects_duplicate_code(category_api_context):
    context = category_api_context
    payload = category_payload(context)

    first = create_category_request(context, payload=payload)
    assert first.status_code == 201, first.text

    second = create_category_request(context, payload=payload)

    assert second.status_code == 409
    assert second.json()["detail"] == (
        "This asset category code already exists in the organization."
    )


def test_category_listing_returns_organization_categories(
    category_api_context,
):
    context = category_api_context

    create_db_category(context, "Mechanical Equipment", "MECH")
    create_db_category(context, "Electrical Equipment", "ELEC")

    other_organization = Organization(
        name="Other Category Organization",
        code=f"OTHER_CAT_{context['suffix']}",
    )
    context["db"].add(other_organization)
    context["db"].flush()

    context["db"].add(
        AssetCategory(
            organization_id=other_organization.id,
            name="Private Category",
            code="PRIVATE",
            is_active=True,
        )
    )
    context["db"].flush()

    response = list_categories_request(context)

    assert response.status_code == 200, response.text
    result = response.json()

    assert result["total"] == 2
    assert {item["name"] for item in result["items"]} == {
        "Mechanical Equipment",
        "Electrical Equipment",
    }


def test_category_listing_requires_view_permission(category_api_context):
    context = category_api_context

    context["db"].delete(context["view_role_permission"])
    context["db"].flush()

    response = list_categories_request(context)

    assert response.status_code == 403


def test_category_listing_searches_name_and_code(category_api_context):
    context = category_api_context

    create_db_category(context, "Hydraulic Systems", "HYDRAULIC")
    create_db_category(context, "Electrical Equipment", "ELECTRICAL")

    name_response = list_categories_request(context, search="Hydraulic")
    assert name_response.status_code == 200
    assert name_response.json()["total"] == 1
    assert name_response.json()["items"][0]["name"] == "Hydraulic Systems"

    code_response = list_categories_request(context, search="ELECTRICAL")
    assert code_response.status_code == 200
    assert code_response.json()["total"] == 1
    assert code_response.json()["items"][0]["code"] == "ELECTRICAL"


def test_category_listing_supports_pagination(category_api_context):
    context = category_api_context

    create_db_category(context, "Alpha Equipment", "ALPHA")
    create_db_category(context, "Bravo Equipment", "BRAVO")
    create_db_category(context, "Charlie Equipment", "CHARLIE")

    first = list_categories_request(context, offset=0, limit=2)
    assert first.status_code == 200, first.text

    first_result = first.json()
    assert first_result["total"] == 3
    assert first_result["page"] == 1
    assert first_result["total_pages"] == 2
    assert first_result["has_more"] is True
    assert len(first_result["items"]) == 2

    second = list_categories_request(context, offset=2, limit=2)
    assert second.status_code == 200, second.text

    second_result = second.json()
    assert second_result["page"] == 2
    assert second_result["has_more"] is False
    assert len(second_result["items"]) == 1
    assert second_result["items"][0]["name"] == "Charlie Equipment"


def test_category_detail_returns_category(category_api_context):
    context = category_api_context

    category = create_db_category(
        context,
        "Pneumatic Equipment",
        "PNEUMATIC",
    )

    response = context["client"].get(
        f"/api/v1/asset-categories/{category.id}",
        params={
            "organization_id": str(context["organization"].id)
        },
        headers=category_headers(context),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(category.id)
    assert response.json()["name"] == "Pneumatic Equipment"


def test_category_detail_returns_404_for_other_organization(
    category_api_context,
):
    context = category_api_context

    other_organization = Organization(
        name="Foreign Category Organization",
        code=f"FOREIGN_CAT_{context['suffix']}",
    )
    context["db"].add(other_organization)
    context["db"].flush()

    foreign_category = AssetCategory(
        organization_id=other_organization.id,
        name="Foreign Equipment",
        code="FOREIGN",
        is_active=True,
    )
    context["db"].add(foreign_category)
    context["db"].flush()

    response = context["client"].get(
        f"/api/v1/asset-categories/{foreign_category.id}",
        params={
            "organization_id": str(context["organization"].id)
        },
        headers=category_headers(context),
    )

    assert response.status_code == 404


def test_category_detail_requires_view_permission(category_api_context):
    context = category_api_context

    category = create_db_category(
        context,
        "Protected Category",
        "PROTECTED",
    )

    context["db"].delete(context["view_role_permission"])
    context["db"].flush()

    response = context["client"].get(
        f"/api/v1/asset-categories/{category.id}",
        params={
            "organization_id": str(context["organization"].id)
        },
        headers=category_headers(context),
    )

    assert response.status_code == 403

def test_authorized_user_can_update_asset_category(category_api_context):
    context = category_api_context
    category = create_db_category(context, "Original Name", "UPDATE_TEST")

    response = context["client"].patch(
        f"/api/v1/asset-categories/{category.id}",
        params={"organization_id": str(context["organization"].id)},
        json={"name": "Updated Name", "description": "Updated description"},
        headers=category_headers(context),
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["name"] == "Updated Name"
    assert result["description"] == "Updated description"
    assert result["code"] == "UPDATE_TEST"


def test_category_update_requires_permission(category_api_context):
    context = category_api_context
    category = create_db_category(context, "Protected Name", "UPDATE_DENIED")

    context["db"].delete(context["update_role_permission"])
    context["db"].flush()

    response = context["client"].patch(
        f"/api/v1/asset-categories/{category.id}",
        params={"organization_id": str(context["organization"].id)},
        json={"name": "Unauthorized Change"},
        headers=category_headers(context),
    )

    assert response.status_code == 403


def test_category_update_cannot_access_foreign_organization_category(
    category_api_context,
):
    context = category_api_context
    other_org = Organization(
        name="Foreign Update Organization",
        code=f"FOREIGN_UPDATE_{context['suffix']}",
    )
    context["db"].add(other_org)
    context["db"].flush()

    foreign_category = AssetCategory(
        organization_id=other_org.id,
        name="Foreign Category",
        code="FOREIGN_UPDATE",
        is_active=True,
    )
    context["db"].add(foreign_category)
    context["db"].flush()

    response = context["client"].patch(
        f"/api/v1/asset-categories/{foreign_category.id}",
        params={"organization_id": str(context["organization"].id)},
        json={"name": "Attempted Change"},
        headers=category_headers(context),
    )

    assert response.status_code == 404


def test_authorized_user_can_deactivate_category_and_preserve_record(
    category_api_context,
):
    context = category_api_context
    category = create_db_category(context, "Retained Category", "DEACTIVATE_TEST")
    category_id = category.id

    response = context["client"].post(
        f"/api/v1/asset-categories/{category_id}/deactivate",
        params={"organization_id": str(context["organization"].id)},
        headers=category_headers(context),
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False

    retained = context["db"].get(AssetCategory, category_id)
    assert retained is not None
    assert retained.name == "Retained Category"
    assert retained.code == "DEACTIVATE_TEST"
    assert retained.is_active is False


def test_category_deactivation_requires_permission(category_api_context):
    context = category_api_context
    category = create_db_category(context, "Protected Category", "DEACTIVATE_DENIED")

    context["db"].delete(context["deactivate_role_permission"])
    context["db"].flush()

    response = context["client"].post(
        f"/api/v1/asset-categories/{category.id}/deactivate",
        params={"organization_id": str(context["organization"].id)},
        headers=category_headers(context),
    )

    assert response.status_code == 403
    assert category.is_active is True


def test_authorized_user_can_reactivate_category(category_api_context):
    context = category_api_context
    category = create_db_category(context, "Inactive Category", "REACTIVATE_TEST")
    category.is_active = False
    context["db"].flush()

    response = context["client"].post(
        f"/api/v1/asset-categories/{category.id}/reactivate",
        params={"organization_id": str(context["organization"].id)},
        headers=category_headers(context),
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is True
    assert category.is_active is True


def test_category_reactivation_requires_permission(category_api_context):
    context = category_api_context
    category = create_db_category(context, "Protected Inactive", "REACTIVATE_DENIED")
    category.is_active = False
    context["db"].flush()

    context["db"].delete(context["reactivate_role_permission"])
    context["db"].flush()

    response = context["client"].post(
        f"/api/v1/asset-categories/{category.id}/reactivate",
        params={"organization_id": str(context["organization"].id)},
        headers=category_headers(context),
    )

    assert response.status_code == 403
    assert category.is_active is False


def test_inactive_category_is_hidden_from_listing_and_detail(
    category_api_context,
):
    context = category_api_context
    category = create_db_category(context, "Hidden Category", "HIDDEN_TEST")
    category.is_active = False
    context["db"].flush()

    listing = list_categories_request(context)
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 0

    detail = context["client"].get(
        f"/api/v1/asset-categories/{category.id}",
        params={"organization_id": str(context["organization"].id)},
        headers=category_headers(context),
    )
    assert detail.status_code == 404

