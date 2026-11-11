from datetime import timedelta

import pytest

from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


def test_password_hashing():
    password = "OxMaint-Test-Password-2026!"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("Incorrect-Password", hashed)


def test_empty_password_rejected():
    with pytest.raises(ValueError):
        hash_password("")


def test_access_token_creation_and_validation():
    token = create_access_token("test-user-123")

    claims = decode_access_token(token)

    assert claims is not None
    assert claims["sub"] == "test-user-123"
    assert claims["type"] == "access"


def test_expired_token_rejected():
    token = create_access_token(
        "test-user-123",
        expires_delta=timedelta(seconds=-1),
    )

    assert decode_access_token(token) is None


def test_invalid_token_rejected():
    assert decode_access_token("not-a-valid-token") is None


def test_reserved_claims_cannot_be_overridden():
    with pytest.raises(ValueError):
        create_access_token(
            "test-user-123",
            additional_claims={"sub": "another-user"},
        )
