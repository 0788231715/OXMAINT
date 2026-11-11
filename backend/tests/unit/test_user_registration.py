from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from backend.app.database.models.identity import User
from backend.app.modules.asset_management.services.asset_service import (
    _build_accessible_assets_query,
)
from backend.app.modules.user_management.schemas.users import UserRegistrationInput
from backend.app.modules.user_management.services import user_service
from backend.app.modules.user_management.services.authorization_service import (
    has_department_access,
    has_permission,
    has_site_access,
)
from backend.app.modules.service_requests.services.service_request_service import (
    list_accessible_service_requests,
)


def registration_input():
    return UserRegistrationInput(
        email="New.Technician@example.com",
        display_name=" New Technician ",
        initial_password="LongInitialPassword123!",
        site_ids=[uuid4()],
        department_ids=[],
    )


def test_register_technician_hashes_password_and_assigns_fixed_role(monkeypatch):
    organization_id = uuid4()
    manager_id = uuid4()
    site_id = uuid4()
    data = registration_input().model_copy(update={"site_ids": [site_id]})
    organization = SimpleNamespace(is_active=True)
    role = SimpleNamespace(id=uuid4(), code="maintenance_technician")
    manager = SimpleNamespace(id=manager_id)
    db = MagicMock()
    db.get.return_value = organization
    db.scalar.side_effect = [None, role]
    monkeypatch.setattr(user_service, "has_site_access", lambda *args: True)
    monkeypatch.setattr(user_service, "has_department_access", lambda *args: True)
    monkeypatch.setattr(user_service, "hash_password", lambda value: f"hashed:{value}")

    user = user_service.register_technician(
        db=db,
        organization_id=organization_id,
        registering_user=manager,
        data=data,
    )

    created_user = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], User)
    )
    role_assignment = next(
        call.args[0]
        for call in db.add.call_args_list
        if hasattr(call.args[0], "role_id")
    )
    site_assignments = db.add_all.call_args_list[0].args[0]

    assert user is created_user
    assert created_user.email == "new.technician@example.com"
    assert created_user.password_hash == "hashed:LongInitialPassword123!"
    assert role_assignment.role_id == role.id
    assert role_assignment.organization_id == organization_id
    assert role_assignment.granted_by == manager_id
    assert len(site_assignments) == 1
    assert site_assignments[0].site_id == site_id


def test_register_technician_rejects_site_outside_manager_scope(monkeypatch):
    organization_id = uuid4()
    manager = SimpleNamespace(id=uuid4())
    role = SimpleNamespace(id=uuid4(), code="maintenance_technician")
    db = MagicMock()
    db.get.return_value = SimpleNamespace(is_active=True)
    db.scalar.side_effect = [None, role]
    monkeypatch.setattr(user_service, "has_site_access", lambda *args: False)

    with pytest.raises(HTTPException) as error:
        user_service.register_technician(
            db=db,
            organization_id=organization_id,
            registering_user=manager,
            data=registration_input(),
        )

    assert error.value.status_code == 403
    db.add.assert_not_called()
    db.add_all.assert_not_called()


def test_system_admin_has_scoped_permission_and_location_access():
    user_id = uuid4()
    organization_id = uuid4()
    site_id = uuid4()
    department_id = uuid4()
    db = MagicMock()
    db.scalar.side_effect = [True, organization_id, True, site_id, True, department_id]

    assert has_permission(db, user_id, organization_id, "users.create") is True
    assert has_site_access(db, user_id, site_id, organization_id) is True
    assert has_department_access(db, user_id, department_id, organization_id) is True


def test_system_admin_still_cannot_access_inactive_resources():
    user_id = uuid4()
    organization_id = uuid4()
    site_id = uuid4()
    db = MagicMock()
    db.scalar.side_effect = [True, None, True, None, True, None]

    assert has_permission(db, user_id, organization_id, "users.create") is False
    assert has_site_access(db, user_id, site_id, organization_id) is False
    assert has_department_access(db, user_id, uuid4(), organization_id) is False


def test_system_admin_is_included_in_asset_and_request_list_queries():
    user_id = uuid4()
    organization_id = uuid4()
    asset_query = _build_accessible_assets_query(user_id, organization_id)
    asset_sql = str(asset_query.compile(dialect=postgresql.dialect()))

    db = MagicMock()
    db.scalar.return_value = 0
    db.scalars.return_value.all.return_value = []
    list_accessible_service_requests(db, user_id, organization_id)
    request_queries = [
        call.args[0]
        for call in [*db.scalar.call_args_list, *db.scalars.call_args_list]
    ]
    request_sql = " ".join(
        str(statement.compile(dialect=postgresql.dialect()))
        for statement in request_queries
    )

    assert "is_system_admin" in asset_sql
    assert "is_system_admin" in request_sql
