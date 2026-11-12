from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.security import create_access_token, hash_password
from backend.app.database.base import Base
from backend.app.database.connection import get_db
import backend.app.database.models
from backend.app.database.models.identity import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRoleAssignment,
)
from backend.app.database.models.organization import Organization
from backend.app.main import app


@pytest.fixture
def settings_api_context():
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
        name="Settings Test Organization",
        code=f"SETTINGS_{uuid4().hex[:8].upper()}",
        description="Original organization description",
    )
    other_organization = Organization(
        name="Other Settings Organization",
        code=f"OTHER_{uuid4().hex[:8].upper()}",
    )
    manager = User(
        email=f"settings-manager-{uuid4().hex[:8]}@example.com",
        display_name="Settings Manager",
        password_hash=hash_password("SettingsManagerPassword123!"),
        is_active=True,
    )
    member = User(
        email=f"settings-member-{uuid4().hex[:8]}@example.com",
        display_name="Settings Member",
        password_hash=hash_password("SettingsMemberPassword123!"),
        is_active=True,
    )
    manager_role = Role(
        code=f"SETTINGS_MANAGER_{uuid4().hex[:8].upper()}",
        name="Settings Manager",
        is_active=True,
    )
    member_role = Role(
        code=f"SETTINGS_MEMBER_{uuid4().hex[:8].upper()}",
        name="Settings Member",
        is_active=True,
    )
    update_permission = Permission(
        code="organizations.update",
        name="Update Organization Settings",
        module="system_settings",
        action="update",
    )
    db.add_all(
        [
            organization,
            other_organization,
            manager,
            member,
            manager_role,
            member_role,
            update_permission,
        ]
    )
    db.flush()
    db.add_all(
        [
            RolePermission(
                role_id=manager_role.id,
                permission_id=update_permission.id,
            ),
            UserRoleAssignment(
                user_id=manager.id,
                role_id=manager_role.id,
                organization_id=organization.id,
            ),
            UserRoleAssignment(
                user_id=member.id,
                role_id=member_role.id,
                organization_id=organization.id,
            ),
        ]
    )
    db.flush()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield {
                "client": client,
                "db": db,
                "organization": organization,
                "other_organization": other_organization,
                "manager": manager,
                "member": member,
                "manager_token": create_access_token(subject=str(manager.id)),
                "member_token": create_access_token(subject=str(member.id)),
            }
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        transaction.rollback()
        connection.close()
        test_engine.dispose()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_settings_api_updates_profile_and_lists_scoped_permissions(
    settings_api_context,
):
    context = settings_api_context
    client = context["client"]
    profile = client.patch(
        "/api/v1/auth/me",
        headers=_headers(context["manager_token"]),
        json={"display_name": "  Updated Manager  "},
    )

    organizations = client.get(
        "/api/v1/auth/organizations",
        headers=_headers(context["manager_token"]),
    )
    member_organizations = client.get(
        "/api/v1/auth/organizations",
        headers=_headers(context["member_token"]),
    )

    assert profile.status_code == 200
    assert profile.json()["display_name"] == "Updated Manager"
    assert profile.json()["email"] == context["manager"].email
    assert "password_hash" not in profile.json()
    assert organizations.status_code == 200
    assert len(organizations.json()) == 1
    assert organizations.json()[0]["description"] == "Original organization description"
    assert organizations.json()[0]["can_update"] is True
    assert member_organizations.status_code == 200
    assert member_organizations.json()[0]["can_update"] is False


def test_organization_profile_update_requires_permission_and_unique_code(
    settings_api_context,
):
    context = settings_api_context
    client = context["client"]
    organization_id = context["organization"].id
    path = f"/api/v1/organizations?organization_id={organization_id}"
    body = {
        "name": "  Updated OxMaint  ",
        "code": "  oxmaint_ops  ",
        "description": "  Updated organization profile.  ",
    }

    denied = client.put(
        path,
        headers=_headers(context["member_token"]),
        json=body,
    )
    updated = client.put(
        path,
        headers=_headers(context["manager_token"]),
        json=body,
    )
    duplicate = client.put(
        path,
        headers=_headers(context["manager_token"]),
        json={
            **body,
            "code": context["other_organization"].code,
        },
    )

    assert denied.status_code == 403
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated OxMaint"
    assert updated.json()["code"] == "OXMAINT_OPS"
    assert updated.json()["description"] == "Updated organization profile."
    assert updated.json()["can_update"] is True
    assert duplicate.status_code == 409
