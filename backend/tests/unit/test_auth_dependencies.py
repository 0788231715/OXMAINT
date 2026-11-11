from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.app.core.dependencies import get_current_user
from backend.app.core.security import create_access_token


def test_active_user_is_authenticated():
    user_id = uuid4()
    user = SimpleNamespace(id=user_id, is_active=True)

    db = MagicMock()
    db.get.return_value = user

    token = create_access_token(str(user_id))

    result = get_current_user(token=token, db=db)

    assert result is user
    db.get.assert_called_once()


def test_inactive_user_is_rejected():
    user_id = uuid4()
    user = SimpleNamespace(id=user_id, is_active=False)

    db = MagicMock()
    db.get.return_value = user

    token = create_access_token(str(user_id))

    with pytest.raises(HTTPException) as error:
        get_current_user(token=token, db=db)

    assert error.value.status_code == 401


def test_nonexistent_user_is_rejected():
    db = MagicMock()
    db.get.return_value = None

    token = create_access_token(str(uuid4()))

    with pytest.raises(HTTPException) as error:
        get_current_user(token=token, db=db)

    assert error.value.status_code == 401


def test_invalid_token_is_rejected():
    db = MagicMock()

    with pytest.raises(HTTPException) as error:
        get_current_user(token="invalid-token", db=db)

    assert error.value.status_code == 401
    db.get.assert_not_called()


def test_token_with_invalid_user_id_is_rejected():
    db = MagicMock()
    token = create_access_token("not-a-valid-uuid")

    with pytest.raises(HTTPException) as error:
        get_current_user(token=token, db=db)

    assert error.value.status_code == 401
    db.get.assert_not_called()
