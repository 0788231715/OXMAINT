from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.security import (
    create_access_token,
    verify_password,
)
from backend.app.database.models.identity import User


MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User:
    """Authenticate a user and manage failed-login attempts."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    normalized_email = email.strip().lower()

    user = db.scalar(
        select(User).where(User.email == normalized_email)
    )

    if user is None:
        raise unauthorized

    password_valid = verify_password(
        password,
        user.password_hash,
    )

    now = datetime.now(timezone.utc)

    if user.locked_until is not None:
        locked_until = user.locked_until

        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(
                tzinfo=timezone.utc
            )

        if locked_until > now:
            raise unauthorized

        # The previous lockout has expired.
        user.failed_login_attempts = 0
        user.locked_until = None

    if not user.is_active or not password_valid:
        if user.is_active:
            user.failed_login_attempts += 1

            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = now + timedelta(
                    minutes=LOCKOUT_DURATION_MINUTES
                )

            db.commit()

        raise unauthorized

    # Successful authentication resets the failure counter.
    user.failed_login_attempts = 0
    user.locked_until = None

    db.commit()
    db.refresh(user)

    return user


def generate_user_access_token(user: User) -> str:
    """Generate an access token for an authenticated user."""

    return create_access_token(subject=str(user.id))
