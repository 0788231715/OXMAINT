import pytest

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.database.connection import engine
from backend.app.database.models.organization import (
    Organization,
    Site,
    Department,
)
from backend.app.database.models.asset import Asset, AssetCategory
from backend.app.modules.asset_management.schemas.asset import AssetCreate
from backend.app.modules.asset_management.services.asset_service import (
    create_asset,
)


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def test_asset_creation_and_organization_validation(db):
    org_a = Organization(name="Test Organization A", code="TEST_ORG_A")
    org_b = Organization(name="Test Organization B", code="TEST_ORG_B")

    db.add_all([org_a, org_b])
    db.flush()

    site_a = Site(
        organization_id=org_a.id,
        name="Test Site A",
        code="TEST_SITE_A",
    )

    site_b = Site(
        organization_id=org_b.id,
        name="Test Site B",
        code="TEST_SITE_B",
    )

    department_a = Department(
        organization_id=org_a.id,
        name="Test Department A",
        code="TEST_DEPT_A",
    )

    category_a = AssetCategory(
        organization_id=org_a.id,
        name="Test Equipment",
        code="TEST_EQUIPMENT",
    )

    db.add_all([site_a, site_b, department_a, category_a])
    db.flush()

    valid_data = AssetCreate(
        organization_id=org_a.id,
        category_id=category_a.id,
        site_id=site_a.id,
        department_id=department_a.id,
        asset_tag="TEST-ASSET-001",
        name="Test Generator",
    )

    asset = create_asset(db, valid_data)

    assert asset.id is not None
    assert asset.organization_id == org_a.id
    print("PASS: Valid asset creation")

    duplicate_data = valid_data.model_copy(
        update={"name": "Duplicate Generator"}
    )

    with pytest.raises(HTTPException) as duplicate_error:
        create_asset(db, duplicate_data)

    assert duplicate_error.value.status_code == 409
    print("PASS: Duplicate asset tag rejected")

    invalid_site_data = valid_data.model_copy(
        update={
            "asset_tag": "TEST-ASSET-002",
            "site_id": site_b.id,
        }
    )

    with pytest.raises(HTTPException) as site_error:
        create_asset(db, invalid_site_data)

    assert site_error.value.status_code == 422
    print("PASS: Cross-organization site rejected")

    print("All asset service integration checks passed.")
from backend.app.modules.asset_management.schemas.asset import AssetUpdate
from backend.app.modules.asset_management.services.asset_service import update_asset


def test_asset_updates_and_hierarchy_validation(db):
    organization = Organization(
        name="Hierarchy Test Organization",
        code="HIERARCHY_TEST_ORG",
    )
    db.add(organization)
    db.flush()

    site = Site(
        organization_id=organization.id,
        name="Hierarchy Test Site",
        code="HIERARCHY_TEST_SITE",
    )

    category = AssetCategory(
        organization_id=organization.id,
        name="Hierarchy Test Equipment",
        code="HIERARCHY_TEST_EQUIPMENT",
    )

    db.add_all([site, category])
    db.flush()

    parent_data = AssetCreate(
        organization_id=organization.id,
        category_id=category.id,
        site_id=site.id,
        asset_tag="HIERARCHY-PARENT",
        name="Main Generator",
    )

    parent = create_asset(db, parent_data)

    # Verify a normal update.
    updated = update_asset(
        db,
        parent,
        AssetUpdate(name="Updated Main Generator"),
    )

    assert updated.name == "Updated Main Generator"
    print("PASS: Asset update")

    # Explicitly clearing the required name must be rejected.
    with pytest.raises(HTTPException) as name_error:
        update_asset(db, parent, AssetUpdate(name=None))

    assert name_error.value.status_code == 422
    print("PASS: Empty asset name rejected")

    # An asset cannot be its own parent.
    with pytest.raises(HTTPException) as self_parent_error:
        update_asset(
            db,
            parent,
            AssetUpdate(parent_asset_id=parent.id),
        )

    assert self_parent_error.value.status_code == 422
    print("PASS: Self-parent assignment rejected")

    # Create a child asset belonging to the parent.
    child = create_asset(
        db,
        AssetCreate(
            organization_id=organization.id,
            category_id=category.id,
            site_id=site.id,
            parent_asset_id=parent.id,
            asset_tag="HIERARCHY-CHILD",
            name="Generator Control Unit",
        ),
    )

    assert child.parent_asset_id == parent.id
    print("PASS: Parent-child asset relationship")

    # Attempt to make the parent a child of its own child.
    with pytest.raises(HTTPException) as cycle_error:
        update_asset(
            db,
            parent,
            AssetUpdate(parent_asset_id=child.id),
        )

    assert cycle_error.value.status_code == 422
    print("PASS: Circular asset hierarchy rejected")

    print("All asset update and hierarchy checks passed.")
