from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from backend.app.database.connection import engine
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
from backend.app.modules.user_management.services.authorization_service import (
    has_permission,
    has_department_access,
    has_site_access,
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


def test_organization_role_and_resource_access(db):
    org_a = Organization(name="Auth Organization A", code="AUTH_ORG_A")
    org_b = Organization(name="Auth Organization B", code="AUTH_ORG_B")

    db.add_all([org_a, org_b])
    db.flush()

    user = User(
        email="authorization-test@example.com",
        display_name="Authorization Test",
        password_hash="test-password-hash",
    )

    role = Role(
        code="AUTH_TEST_MANAGER",
        name="Authorization Test Manager",
        is_active=True,
    )

    permission = Permission(
        code="assets.view",
        name="View Assets",
        module="asset_management",
        action="view",
    )

    department_a = Department(
        organization_id=org_a.id,
        name="Department A",
        code="AUTH_DEPT_A",
    )

    department_b = Department(
        organization_id=org_b.id,
        name="Department B",
        code="AUTH_DEPT_B",
    )

    site_a = Site(
        organization_id=org_a.id,
        name="Site A",
        code="AUTH_SITE_A",
    )

    site_b = Site(
        organization_id=org_b.id,
        name="Site B",
        code="AUTH_SITE_B",
    )

    db.add_all([
        user,
        role,
        permission,
        department_a,
        department_b,
        site_a,
        site_b,
    ])
    db.flush()

    db.add_all([
        RolePermission(
            role_id=role.id,
            permission_id=permission.id,
        ),
        UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            organization_id=org_a.id,
        ),
        UserDepartmentAccess(
            user_id=user.id,
            department_id=department_a.id,
        ),
        UserSiteAccess(
            user_id=user.id,
            site_id=site_a.id,
        ),
    ])
    db.flush()

    assert has_permission(
        db, user.id, org_a.id, "assets.view"
    ) is True

    assert has_permission(
        db, user.id, org_b.id, "assets.view"
    ) is False

    assert has_department_access(
        db, user.id, department_a.id, org_a.id
    ) is True

    assert has_department_access(
        db, user.id, department_b.id, org_b.id
    ) is False

    assert has_site_access(
        db, user.id, site_a.id, org_a.id
    ) is True

    assert has_site_access(
        db, user.id, site_b.id, org_b.id
    ) is False

    print("PASS: Organization-scoped permission checks")
    print("PASS: Department access checks")
    print("PASS: Site access checks")


def test_expired_authorization_assignments_are_rejected(db):
    org = Organization(
        name="Expired Authorization Organization",
        code="EXPIRED_AUTH_ORG",
    )
    db.add(org)
    db.flush()

    department = Department(
        organization_id=org.id,
        name="Temporary Department",
        code="EXPIRED_AUTH_DEPT",
    )

    site = Site(
        organization_id=org.id,
        name="Temporary Site",
        code="EXPIRED_AUTH_SITE",
    )

    user = User(
        email="expired-auth-test@example.com",
        display_name="Expired Authorization Test",
        password_hash="test-password-hash",
    )

    role = Role(
        code="EXPIRED_AUTH_ROLE",
        name="Expired Authorization Role",
        is_active=True,
    )

    permission = Permission(
        code="reports.view",
        name="View Reports",
        module="reports",
        action="view",
    )

    db.add_all([department, site, user, role, permission])
    db.flush()

    expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    db.add_all([
        RolePermission(
            role_id=role.id,
            permission_id=permission.id,
        ),
        UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            organization_id=org.id,
            expires_at=expired_at,
        ),
        UserDepartmentAccess(
            user_id=user.id,
            department_id=department.id,
            expires_at=expired_at,
        ),
        UserSiteAccess(
            user_id=user.id,
            site_id=site.id,
            expires_at=expired_at,
        ),
    ])
    db.flush()

    assert has_permission(
        db, user.id, org.id, "reports.view"
    ) is False

    assert has_department_access(
        db, user.id, department.id, org.id
    ) is False

    assert has_site_access(
        db, user.id, site.id, org.id
    ) is False

def test_inactive_organization_department_and_site_are_rejected(db):
    org = Organization(
        name="Inactive Authorization Organization",
        code="INACTIVE_AUTH_ORG",
        is_active=True,
    )

    db.add(org)
    db.flush()

    department = Department(
        organization_id=org.id,
        name="Inactive Test Department",
        code="INACTIVE_AUTH_DEPT",
        is_active=True,
    )

    site = Site(
        organization_id=org.id,
        name="Inactive Test Site",
        code="INACTIVE_AUTH_SITE",
        is_active=True,
    )

    user = User(
        email="inactive-auth-test@example.com",
        display_name="Inactive Authorization Test",
        password_hash="test-password-hash",
    )

    role = Role(
        code="INACTIVE_AUTH_ROLE",
        name="Inactive Authorization Role",
        is_active=True,
    )

    permission = Permission(
        code="assets.view",
        name="View Assets",
        module="asset_management",
        action="view",
    )

    db.add_all([department, site, user, role, permission])
    db.flush()

    db.add_all([
        RolePermission(
            role_id=role.id,
            permission_id=permission.id,
        ),
        UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            organization_id=org.id,
        ),
        UserDepartmentAccess(
            user_id=user.id,
            department_id=department.id,
        ),
        UserSiteAccess(
            user_id=user.id,
            site_id=site.id,
        ),
    ])
    db.flush()

    # An inactive organization must deny all three access checks.
    org.is_active = False
    db.flush()

    assert has_permission(
        db, user.id, org.id, "assets.view"
    ) is False

    assert has_department_access(
        db, user.id, department.id, org.id
    ) is False

    assert has_site_access(
        db, user.id, site.id, org.id
    ) is False

    # Reactivate the organization and deactivate the department.
    org.is_active = True
    department.is_active = False
    db.flush()

    assert has_department_access(
        db, user.id, department.id, org.id
    ) is False

    # Reactivate the department and deactivate the site.
    department.is_active = True
    site.is_active = False
    db.flush()

    assert has_site_access(
        db, user.id, site.id, org.id
    ) is False

    print("PASS: Inactive organization access rejected")
    print("PASS: Inactive department access rejected")
    print("PASS: Inactive site access rejected")
       