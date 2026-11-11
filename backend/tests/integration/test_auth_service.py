from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.core.security import hash_password
from backend.app.database.connection import engine
from backend.app.database.models.identity import User
from backend.app.modules.user_management.services.auth_service import (
    authenticate_user,
    generate_user_access_token,
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


def create_test_user(
    db,
    email="auth-test@example.com",
    is_active=True,
    failed_attempts=0,
):
    user = User(
        email=email,
        display_name="Authentication Test User",
        password_hash=hash_password("CorrectPassword123!"),
        is_active=is_active,
        failed_login_attempts=failed_attempts,
    )

    db.add(user)
    db.flush()

    return user


def test_successful_authentication_and_token(db):
    user = create_test_user(db, failed_attempts=2)

    authenticated_user = authenticate_user(
        db,
        user.email,
        "CorrectPassword123!",
    )

    assert authenticated_user.id == user.id
    assert authenticated_user.failed_login_attempts == 0

    token = generate_user_access_token(authenticated_user)

    assert isinstance(token, str)
    assert len(token) > 20

    print("PASS: Successful login and access token generation")


def test_incorrect_password_increments_failed_attempts(db):
    user = create_test_user(db)

    with pytest.raises(HTTPException) as error:
        authenticate_user(
            db,
            user.email,
            "IncorrectPassword!",
        )

    assert error.value.status_code == 401
    assert user.failed_login_attempts == 1

    print("PASS: Incorrect password increments failure counter")


def test_five_failed_attempts_trigger_lockout(db):
    user = create_test_user(db)

    for attempt in range(5):
        with pytest.raises(HTTPException) as error:
            authenticate_user(
                db,
                user.email,
                "IncorrectPassword!",
            )

        assert error.value.status_code == 401

    assert user.failed_login_attempts == 5
    assert user.locked_until is not None

    # Correct credentials must still be rejected during lockout.
    with pytest.raises(HTTPException) as locked_error:
        authenticate_user(
            db,
            user.email,
            "CorrectPassword123!",
        )

    assert locked_error.value.status_code == 401

    print("PASS: Five failed attempts trigger a 15-minute lockout")


def test_expired_lockout_allows_successful_login(db):
    user = create_test_user(db, failed_attempts=5)
    user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.flush()

    authenticated_user = authenticate_user(
        db,
        user.email,
        "CorrectPassword123!",
    )

    assert authenticated_user.id == user.id
    assert authenticated_user.failed_login_attempts == 0
    assert authenticated_user.locked_until is None

    print("PASS: Expired lockout permits successful authentication")


def test_inactive_user_cannot_authenticate(db):
    user = create_test_user(db, is_active=False)

    with pytest.raises(HTTPException) as error:
        authenticate_user(
            db,
            user.email,
            "CorrectPassword123!",
        )

    assert error.value.status_code == 401
    assert user.failed_login_attempts == 0

    print("PASS: Inactive accounts cannot authenticate")
