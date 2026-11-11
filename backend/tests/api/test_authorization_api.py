from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.authorization import require_permission
from backend.app.core.dependencies import get_current_user
from backend.app.database.connection import get_db
from backend.app.database.models.identity import User


def build_test_app(permission_result, authenticated=True):
    app = FastAPI()

    user = User(
        id=uuid4(),
        email="authorization-api@example.com",
        display_name="Authorization API Test",
        password_hash="test-hash",
        is_active=True,
    )

    def override_user():
        if not authenticated:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        return user

    def override_db():
        yield object()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    @app.get("/protected")
    def protected_route(
        current_user: User = Depends(
            require_permission("assets.read")
        ),
    ):
        return {"user_id": str(current_user.id)}

    return app


def test_user_with_permission_is_allowed(monkeypatch):
    monkeypatch.setattr(
        "backend.app.core.authorization.has_permission",
        lambda **kwargs: True,
    )

    app = build_test_app(permission_result=True)

    with TestClient(app) as client:
        response = client.get(
            "/protected",
            params={"organization_id": str(uuid4())},
        )

    assert response.status_code == 200
    assert "user_id" in response.json()


def test_user_without_permission_is_forbidden(monkeypatch):
    monkeypatch.setattr(
        "backend.app.core.authorization.has_permission",
        lambda **kwargs: False,
    )

    app = build_test_app(permission_result=False)

    with TestClient(app) as client:
        response = client.get(
            "/protected",
            params={"organization_id": str(uuid4())},
        )

    assert response.status_code == 403


def test_unauthenticated_user_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "backend.app.core.authorization.has_permission",
        lambda **kwargs: True,
    )

    app = build_test_app(
        permission_result=True,
        authenticated=False,
    )

    with TestClient(app) as client:
        response = client.get(
            "/protected",
            params={"organization_id": str(uuid4())},
        )

    assert response.status_code == 401
