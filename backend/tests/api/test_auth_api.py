import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import MagicMock
from types import SimpleNamespace
from uuid import uuid4

from backend.app.main import app
from backend.app.database.connection import engine, get_db
from backend.app.database.models.identity import User
from backend.app.core.security import hash_password
from backend.app.core.dependencies import get_current_user
from backend.app.core import authorization
from backend.app.modules.user_management.api import users as users_api


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


def test_login_route_is_registered():
    paths = app.openapi()["paths"]

    assert "/api/v1/auth/login" in paths
    assert "post" in paths["/api/v1/auth/login"]


def test_login_request_uses_oauth2_form():
    operation = app.openapi()["paths"]["/api/v1/auth/login"]["post"]

    assert "requestBody" in operation
    assert operation["responses"]["200"]


def test_complete_login_and_protected_access(db):
    user = User(
        email="api-auth-test@example.com",
        display_name="API Authentication Test",
        password_hash=hash_password("CorrectPassword123!"),
        is_active=True,
        failed_login_attempts=0,
    )

    db.add(user)
    db.flush()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            # Authenticate.
            login_response = client.post(
                "/api/v1/auth/login",
                data={
                    "username": user.email,
                    "password": "CorrectPassword123!",
                },
            )

            assert login_response.status_code == 200

            token_data = login_response.json()

            assert token_data["token_type"] == "bearer"
            assert token_data["access_token"]
            assert token_data["expires_in"] > 0

            print("PASS: Login returns an access token")

            # Access protected endpoint.
            profile_response = client.get(
                "/api/v1/auth/me",
                headers={
                    "Authorization": (
                        f"Bearer {token_data['access_token']}"
                    )
                },
            )

            assert profile_response.status_code == 200

            profile = profile_response.json()

            assert profile["email"] == user.email
            assert profile["display_name"] == user.display_name
            assert profile["is_active"] is True

            print("PASS: JWT grants access to protected profile")

            # Confirm invalid credentials are rejected.
            invalid_response = client.post(
                "/api/v1/auth/login",
                data={
                    "username": user.email,
                    "password": "WrongPassword!",
                },
            )

            assert invalid_response.status_code == 401

            print("PASS: Incorrect login credentials are rejected")

    finally:
        app.dependency_overrides.pop(get_db, None)


def test_user_registration_requires_authentication():
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/users?organization_id={uuid4()}",
            json={
                "email": "new-tech@example.com",
                "display_name": "New Technician",
                "initial_password": "LongInitialPassword123!",
                "site_ids": [str(uuid4())],
                "department_ids": [],
            },
        )

    assert response.status_code == 401


def test_user_registration_requires_users_create_permission(monkeypatch):
    current_user = User(
        id=uuid4(),
        email="technician@example.com",
        display_name="Maintenance Technician",
        password_hash="not-used-in-this-test",
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: MagicMock()
    monkeypatch.setattr(authorization, "has_permission", lambda *args, **kwargs: False)

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/users?organization_id={uuid4()}",
                json={
                    "email": "new-tech@example.com",
                    "display_name": "New Technician",
                    "initial_password": "LongInitialPassword123!",
                    "site_ids": [str(uuid4())],
                    "department_ids": [],
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403


def test_manager_registration_creates_fixed_technician_role(monkeypatch):
    registering_user = User(
        id=uuid4(),
        email="manager@example.com",
        display_name="Maintenance Manager",
        password_hash="not-used-in-this-test",
    )
    registered_user = User(
        id=uuid4(),
        email="new-tech@example.com",
        display_name="New Technician",
        password_hash="must-not-be-returned",
    )
    db = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: registering_user
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(authorization, "has_permission", lambda *args, **kwargs: True)
    monkeypatch.setattr(users_api, "register_technician", lambda **kwargs: registered_user)

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/users?organization_id={uuid4()}",
                json={
                    "email": "new-tech@example.com",
                    "display_name": "New Technician",
                    "initial_password": "LongInitialPassword123!",
                    "site_ids": [str(uuid4())],
                    "department_ids": [],
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    assert response.json()["role_code"] == "maintenance_technician"
    assert "password_hash" not in response.json()


def test_system_admin_can_list_all_active_organizations():
    system_admin = User(
        id=uuid4(),
        email="abel@example.com",
        display_name="Abel",
        password_hash="not-used-in-this-test",
        is_system_admin=True,
    )
    organization = SimpleNamespace(
        id=uuid4(),
        name="Operations",
        code="OPS",
    )
    db = MagicMock()
    db.execute.return_value.all.return_value = [organization]
    app.dependency_overrides[get_current_user] = lambda: system_admin
    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/organizations")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == [{
        "id": str(organization.id),
        "name": organization.name,
        "code": organization.code,
        "can_register_users": True,
    }]
