import pytest
from pydantic import ValidationError

from backend.app.config import Settings


def test_production_settings_require_a_non_placeholder_secret():
    with pytest.raises(ValidationError, match="Set SECRET_KEY"):
        Settings(
            _env_file=None,
            DEBUG=False,
            SECRET_KEY="REPLACE_WITH_A_RANDOM_SECRET",
        )


def test_production_settings_accept_a_long_random_secret():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        SECRET_KEY="a-random-production-secret-with-at-least-32-characters",
    )

    assert settings.DEBUG is False
