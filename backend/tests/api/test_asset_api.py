
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.security import create_access_token, hash_password
from backend.app.database.connection import engine, get_db

from backend.app.database.models.organization import (
    Organization,
    Department,
    Site,
)

from backend.app.database.models.identity import (
    User,
    Role,
    Permission,
    RolePermission,
    UserRoleAssignment,
    UserDepartmentAccess,
    UserSiteAccess,
)

from backend.app.database.models.asset import (
    Asset,
    AssetCategory,
)


@pytest.fixture
def asset_api_context():
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    organization = Organization(
        name="Asset API Test Organization",
        code="ASSET_API_TEST_ORG",
    )

    db.add(organization)
    db.flush()

    department = Department(
        organization_id=organization.id,
        name="Asset API Test Department",
        code="ASSET_API_TEST_DEPT",
    )

    site = Site(
        organization_id=organization.id,
        name="Asset API Test Site",
        code="ASSET_API_TEST_SITE",
    )

    user = User(
        email="asset-api-test@example.com",
        display_name="Asset API Test User",
        password_hash=hash_password("AssetApiPassword123!"),
        is_active=True,
    )

    role = Role(
        code="ASSET_API_TEST_ROLE",
        name="Asset API Test Role",
        is_active=True,
    )

    permission = (
        db.query(Permission)
        .filter_by(code="assets.create")
        .one()
    )
    view_permission = (
        db.query(Permission)
        .filter_by(code="assets.view")
        .one()
    )
    update_permission = (
        db.query(Permission)
        .filter_by(code="assets.update")
        .one()
    )

    category = AssetCategory(
        organization_id=organization.id,
        name="Test Equipment",
        code="ASSET_API_TEST_CATEGORY",
        is_active=True,
    )

    db.add_all([
        department,
        site,
        user,
        role,
        category,
    ])

    db.flush()

    role_permission = RolePermission(
        role_id=role.id,
        permission_id=permission.id,
    )

    view_role_permission = RolePermission(
        role_id=role.id,
        permission_id=view_permission.id,
    )

    update_role_permission = RolePermission(
        role_id=role.id,
        permission_id=update_permission.id,
    )

    role_assignment = UserRoleAssignment(
        user_id=user.id,
        role_id=role.id,
        organization_id=organization.id,
    )

    department_access = UserDepartmentAccess(
        user_id=user.id,
        department_id=department.id,
    )

    site_access = UserSiteAccess(
        user_id=user.id,
        site_id=site.id,
    )

    db.add_all([
        role_permission,
        view_role_permission,
        update_role_permission,
        role_assignment,
        department_access,
        site_access,
    ])

    db.flush()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(subject=str(user.id))

    context = {
        "db": db,
        "client": None,
        "organization": organization,
        "department": department,
        "site": site,
        "user": user,
        "role": role,
        "permission": permission,
        "view_permission": view_permission,
        "update_permission": update_permission,
        "update_role_permission": update_role_permission,
        "category": category,
        "role_permission": role_permission,
        "view_role_permission": view_role_permission,
        "department_access": department_access,
        "site_access": site_access,
        "token": token,
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


def asset_payload(context):
    return {
        "organization_id": str(context["organization"].id),
        "category_id": str(context["category"].id),
        "site_id": str(context["site"].id),
        "department_id": str(context["department"].id),
        "asset_tag": "ASSET-API-001",
        "name": "Test Generator",
        "manufacturer": "Test Manufacturer",
        "status": "in_service",
        "criticality": "high",
    }


def post_asset(context, payload=None, organization_id=None):
    data = payload or asset_payload(context)

    selected_organization = (
        organization_id or context["organization"].id
    )

    return context["client"].post(
        f"/api/v1/assets?organization_id={selected_organization}",
        json=data,
        headers={
            "Authorization": f"Bearer {context['token']}"
        },
    )


# ============================================================
# EXISTING ASSET CREATION TESTS
# ============================================================

def test_authorized_user_can_create_asset(asset_api_context):
    response = post_asset(asset_api_context)

    assert response.status_code == 201, response.text

    result = response.json()

    assert result["name"] == "Test Generator"
    assert result["asset_tag"] == "ASSET-API-001"
    assert result["organization_id"] == str(
        asset_api_context["organization"].id
    )

    print("PASS: Authorized asset creation")


def test_user_without_create_permission_is_forbidden(asset_api_context):
    context = asset_api_context

    context["db"].delete(context["role_permission"])
    context["db"].flush()

    response = post_asset(context)

    assert response.status_code == 403

    print("PASS: Missing asset creation permission rejected")


def test_user_without_site_access_is_forbidden(asset_api_context):
    context = asset_api_context

    context["db"].delete(context["site_access"])
    context["db"].flush()

    response = post_asset(context)

    assert response.status_code == 403

    print("PASS: Unauthorized site access rejected")


def test_user_without_department_access_is_forbidden(asset_api_context):
    context = asset_api_context

    context["db"].delete(context["department_access"])
    context["db"].flush()

    response = post_asset(context)

    assert response.status_code == 403

    print("PASS: Unauthorized department access rejected")


def test_organization_mismatch_is_forbidden(asset_api_context):
    context = asset_api_context
    payload = asset_payload(context)

    payload["organization_id"] = str(uuid4())

    response = post_asset(context, payload=payload)

    assert response.status_code == 403

    print("PASS: Organization mismatch rejected")


def test_invalid_asset_category_is_rejected(asset_api_context):
    context = asset_api_context
    payload = asset_payload(context)

    payload["category_id"] = str(uuid4())

    response = post_asset(context, payload=payload)

    assert response.status_code == 422

    print("PASS: Invalid asset category rejected")


# ============================================================
# NEW ASSET LISTING SECURITY TESTS
# ============================================================

def test_asset_listing_respects_site_and_department_access(
    asset_api_context,
):
    context = asset_api_context
    db = context["db"]

    # Create another site and department without granting access.
    other_site = Site(
        organization_id=context["organization"].id,
        name="Unauthorized Site",
        code="ASSET_API_OTHER_SITE",
    )

    other_department = Department(
        organization_id=context["organization"].id,
        name="Unauthorized Department",
        code="ASSET_API_OTHER_DEPT",
    )

    db.add_all([other_site, other_department])
    db.flush()

    assets = [
        # Authorized site and authorized department.
        Asset(
            organization_id=context["organization"].id,
            category_id=context["category"].id,
            site_id=context["site"].id,
            department_id=context["department"].id,
            asset_tag="LIST-AUTHORIZED-001",
            name="Authorized Generator",
            status="in_service",
            criticality="high",
        ),

        # Unauthorized site.
        Asset(
            organization_id=context["organization"].id,
            category_id=context["category"].id,
            site_id=other_site.id,
            department_id=context["department"].id,
            asset_tag="LIST-OTHER-SITE-001",
            name="Other Site Generator",
            status="in_service",
            criticality="medium",
        ),

        # Authorized site but unauthorized department.
        Asset(
            organization_id=context["organization"].id,
            category_id=context["category"].id,
            site_id=context["site"].id,
            department_id=other_department.id,
            asset_tag="LIST-OTHER-DEPT-001",
            name="Other Department Generator",
            status="in_service",
            criticality="medium",
        ),

        # Authorized site and no department assignment.
        Asset(
            organization_id=context["organization"].id,
            category_id=context["category"].id,
            site_id=context["site"].id,
            department_id=None,
            asset_tag="LIST-NO-DEPT-001",
            name="Shared Site Generator",
            status="in_service",
            criticality="low",
        ),
    ]

    db.add_all(assets)
    db.flush()

    response = context["client"].get(
        f"/api/v1/assets?organization_id={context['organization'].id}",
        headers={
            "Authorization": f"Bearer {context['token']}"
        },
    )

    assert response.status_code == 200, response.text

    result = response.json()

    returned_names = {
        item["name"] for item in result["items"]
    }

    assert result["total"] == 2
    assert result["page"] == 1
    assert result["total_pages"] == 1
    assert result["has_more"] is False

    assert returned_names == {
        "Authorized Generator",
        "Shared Site Generator",
    }

    print("PASS: Unauthorized site assets are hidden")
    print("PASS: Unauthorized department assets are hidden")
    print("PASS: Authorized assets without departments are visible")


def test_asset_listing_requires_view_permission(asset_api_context):
    context = asset_api_context

    # Remove only the view permission.
    # The create permission remains assigned.
    context["db"].delete(context["view_role_permission"])
    context["db"].flush()

    response = context["client"].get(
        f"/api/v1/assets?organization_id={context['organization'].id}",
        headers={
            "Authorization": f"Bearer {context['token']}"
        },
    )

    assert response.status_code == 403

    print("PASS: Asset listing rejects users without view permission")

# ============================================================
# ASSET LISTING: PAGINATION, SEARCH AND FILTER TESTS
# ============================================================

def create_listing_asset(
    context,
    asset_tag,
    name,
    asset_status="in_service",
    criticality="medium",
):
    asset = Asset(
        organization_id=context["organization"].id,
        category_id=context["category"].id,
        site_id=context["site"].id,
        department_id=context["department"].id,
        asset_tag=asset_tag,
        name=name,
        status=asset_status,
        criticality=criticality,
    )

    context["db"].add(asset)
    context["db"].flush()

    return asset


def get_listed_assets(context, **params):
    query_params = {
        "organization_id": str(context["organization"].id),
        **params,
    }

    return context["client"].get(
        "/api/v1/assets",
        params=query_params,
        headers={
            "Authorization": f"Bearer {context['token']}"
        },
    )


def test_asset_listing_pagination(asset_api_context):
    context = asset_api_context

    create_listing_asset(
        context, "PAGE-001", "Alpha Generator"
    )
    create_listing_asset(
        context, "PAGE-002", "Bravo Pump"
    )
    create_listing_asset(
        context, "PAGE-003", "Charlie Compressor"
    )

    first_response = get_listed_assets(
        context, offset=0, limit=2
    )

    assert first_response.status_code == 200

    first_page = first_response.json()

    assert first_page["total"] == 3
    assert first_page["page"] == 1
    assert first_page["total_pages"] == 2
    assert first_page["has_more"] is True
    assert len(first_page["items"]) == 2

    assert [
        item["name"] for item in first_page["items"]
    ] == ["Alpha Generator", "Bravo Pump"]

    second_response = get_listed_assets(
        context, offset=2, limit=2
    )

    assert second_response.status_code == 200

    second_page = second_response.json()

    assert second_page["total"] == 3
    assert second_page["page"] == 2
    assert second_page["total_pages"] == 2
    assert second_page["has_more"] is False
    assert len(second_page["items"]) == 1
    assert second_page["items"][0]["name"] == "Charlie Compressor"


def test_asset_listing_searches_name_and_asset_tag(asset_api_context):
    context = asset_api_context

    create_listing_asset(
        context, "SEARCH-TAG-001", "Backup Generator"
    )
    create_listing_asset(
        context, "SEARCH-TAG-002", "Water Pump"
    )

    name_response = get_listed_assets(
        context, search="Backup"
    )

    assert name_response.status_code == 200

    name_result = name_response.json()

    assert name_result["total"] == 1
    assert name_result["items"][0]["name"] == "Backup Generator"

    tag_response = get_listed_assets(
        context, search="SEARCH-TAG-002"
    )

    assert tag_response.status_code == 200

    tag_result = tag_response.json()

    assert tag_result["total"] == 1
    assert tag_result["items"][0]["asset_tag"] == "SEARCH-TAG-002"


def test_asset_listing_filters_by_status(asset_api_context):
    context = asset_api_context

    create_listing_asset(
        context,
        "STATUS-001",
        "Operating Generator",
        asset_status="in_service",
    )

    create_listing_asset(
        context,
        "STATUS-002",
        "Maintenance Pump",
        asset_status="under_maintenance",
    )

    response = get_listed_assets(
        context, status="under_maintenance"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["total"] == 1
    assert result["items"][0]["asset_tag"] == "STATUS-002"
    assert result["items"][0]["status"] == "under_maintenance"


def test_asset_listing_filters_by_criticality(asset_api_context):
    context = asset_api_context

    create_listing_asset(
        context,
        "CRITICALITY-001",
        "Standard Pump",
        criticality="low",
    )

    create_listing_asset(
        context,
        "CRITICALITY-002",
        "Critical Generator",
        criticality="critical",
    )

    response = get_listed_assets(
        context, criticality="critical"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["total"] == 1
    assert result["items"][0]["asset_tag"] == "CRITICALITY-002"
    assert result["items"][0]["criticality"] == "critical"


def test_asset_listing_rejects_invalid_status_filter(asset_api_context):
    response = get_listed_assets(
        asset_api_context, status="unknown_status"
    )

    assert response.status_code == 422


def test_asset_listing_rejects_invalid_criticality_filter(
    asset_api_context,
):
    response = get_listed_assets(
        asset_api_context, criticality="extreme"
    )

    assert response.status_code == 422

# ============================================================
# ASSET DETAIL AND UPDATE API TESTS
# ============================================================

def get_asset_detail(context, asset_id):
    return context["client"].get(
        f"/api/v1/assets/{asset_id}",
        params={
            "organization_id": str(context["organization"].id)
        },
        headers={
            "Authorization": f"Bearer {context['token']}"
        },
    )


def patch_asset(context, asset_id, payload):
    return context["client"].patch(
        f"/api/v1/assets/{asset_id}",
        params={
            "organization_id": str(context["organization"].id)
        },
        json=payload,
        headers={
            "Authorization": f"Bearer {context['token']}"
        },
    )


def test_get_asset_returns_authorized_asset(asset_api_context):
    context = asset_api_context

    asset = create_listing_asset(
        context,
        "DETAIL-001",
        "Detail Test Generator",
    )

    response = get_asset_detail(context, asset.id)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(asset.id)
    assert response.json()["name"] == "Detail Test Generator"

    print("PASS: Authorized asset detail retrieval")


def test_get_asset_returns_404_for_missing_asset(asset_api_context):
    context = asset_api_context

    response = get_asset_detail(context, uuid4())

    assert response.status_code == 404

    print("PASS: Missing asset returns 404")


def test_get_asset_requires_view_permission(asset_api_context):
    context = asset_api_context

    asset = create_listing_asset(
        context,
        "DETAIL-002",
        "Protected Generator",
    )

    context["db"].delete(context["view_role_permission"])
    context["db"].flush()

    response = get_asset_detail(context, asset.id)

    assert response.status_code == 403

    print("PASS: Asset detail requires view permission")


def test_authorized_user_can_update_asset(asset_api_context):
    context = asset_api_context

    asset = create_listing_asset(
        context,
        "UPDATE-001",
        "Original Generator",
    )

    response = patch_asset(
        context,
        asset.id,
        {"name": "Updated Generator"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Updated Generator"

    context["db"].refresh(asset)
    assert asset.name == "Updated Generator"

    print("PASS: Authorized asset update")


def test_user_without_update_permission_is_forbidden(
    asset_api_context,
):
    context = asset_api_context

    asset = create_listing_asset(
        context,
        "UPDATE-002",
        "Protected Pump",
    )

    context["db"].delete(context["update_role_permission"])
    context["db"].flush()

    response = patch_asset(
        context,
        asset.id,
        {"name": "Unauthorized Change"},
    )

    assert response.status_code == 403

    context["db"].refresh(asset)
    assert asset.name == "Protected Pump"

    print("PASS: Missing update permission rejected")

def test_asset_update_rejects_unauthorized_target_site(
    asset_api_context,
):
    context = asset_api_context

    asset = create_listing_asset(
        context,
        "TRANSFER-SITE-001",
        "Site Transfer Generator",
    )

    other_site = Site(
        organization_id=context["organization"].id,
        name="Unauthorized Target Site",
        code="TRANSFER_UNAUTHORIZED_SITE",
    )
    context["db"].add(other_site)
    context["db"].flush()

    response = patch_asset(
        context,
        asset.id,
        {"site_id": str(other_site.id)},
    )

    assert response.status_code == 403, response.text

    context["db"].refresh(asset)
    assert asset.site_id == context["site"].id

    print("PASS: Unauthorized target site transfer rejected")


def test_asset_update_rejects_unauthorized_target_department(
    asset_api_context,
):
    context = asset_api_context

    asset = create_listing_asset(
        context,
        "TRANSFER-DEPT-001",
        "Department Transfer Generator",
    )

    other_department = Department(
        organization_id=context["organization"].id,
        name="Unauthorized Target Department",
        code="TRANSFER_UNAUTHORIZED_DEPT",
    )
    context["db"].add(other_department)
    context["db"].flush()

    response = patch_asset(
        context,
        asset.id,
        {"department_id": str(other_department.id)},
    )

    assert response.status_code == 403, response.text

    context["db"].refresh(asset)
    assert asset.department_id == context["department"].id

    print("PASS: Unauthorized target department transfer rejected")


# ============================================================
# CATEGORY LIFECYCLE AND HISTORICAL ASSET INTEGRITY TESTS
# ============================================================

def test_inactive_category_cannot_be_assigned_to_new_asset(
    asset_api_context,
):
    context = asset_api_context

    context["category"].is_active = False
    context["db"].flush()

    response = post_asset(
        context,
        payload={
            **asset_payload(context),
            "asset_tag": "INACTIVE-CATEGORY-001",
        },
    )

    assert response.status_code == 422, response.text
    assert "category" in response.text.lower()

    print("PASS: Inactive category assignment rejected")


def test_category_deactivation_preserves_existing_asset_reference(
    asset_api_context,
):
    context = asset_api_context

    response = post_asset(
        context,
        payload={
            **asset_payload(context),
            "asset_tag": "HISTORICAL-CATEGORY-001",
        },
    )

    assert response.status_code == 201, response.text

    asset = (
        context["db"]
        .query(Asset)
        .filter(
            Asset.asset_tag == "HISTORICAL-CATEGORY-001"
        )
        .one()
    )

    original_category_id = context["category"].id

    assert asset.category_id == original_category_id

    # Deactivation must preserve historical asset references.
    context["category"].is_active = False
    context["db"].flush()
    context["db"].refresh(asset)

    assert asset.category_id == original_category_id
    assert asset.category.id == original_category_id
    assert asset.category.is_active is False

    print("PASS: Existing asset retains its deactivated category reference")
