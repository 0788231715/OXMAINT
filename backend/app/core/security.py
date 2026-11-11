from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.app.config import settings


# Password hashing configuration.
password_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__rounds=600000,
)

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Return a secure hash of a user's password."""
    if not password:
        raise ValueError("Password cannot be empty.")

    return password_context.hash(password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    """Verify a password against its stored hash."""
    return password_context.verify(plain_password, password_hash)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    expiry = expires_delta or timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    claims = {
        "sub": subject,
        "iat": now,
        "exp": now + expiry,
        "type": "access",
    }

    if additional_claims:
        reserved_claims = {"sub", "iat", "exp", "type"}
        if reserved_claims.intersection(additional_claims):
            raise ValueError("Additional claims cannot override reserved claims.")

        claims.update(additional_claims)

    return jwt.encode(
        claims,
        settings.SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode a valid access token or return None."""
    try:
        claims = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )

        if claims.get("type") != "access":
            return None

        if not claims.get("sub"):
            return None

        return claims

    except JWTError:
        return None
