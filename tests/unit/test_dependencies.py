import uuid

import pytest
from fastapi import HTTPException

from app.dependencies import _parse_auth_token


def test_parse_bearer_header():
    sub = uuid.uuid4()
    from app.security import create_access_token

    token = create_access_token(subject=str(sub), email="x@y.z", role="USER")
    claims = _parse_auth_token(f"Bearer {token}", cookie=None)
    assert claims["sub"] == str(sub)


def test_parse_cookie_when_no_header():
    sub = uuid.uuid4()
    from app.security import create_access_token

    token = create_access_token(subject=str(sub), email="x@y.z", role="USER")
    claims = _parse_auth_token(None, cookie=token)
    assert claims["sub"] == str(sub)


def test_no_credentials_raises_401():
    with pytest.raises(HTTPException) as ei:
        _parse_auth_token(None, None)
    assert ei.value.status_code == 401


def test_malformed_header_raises_401():
    with pytest.raises(HTTPException) as ei:
        _parse_auth_token("NotBearer xxx", None)
    assert ei.value.status_code == 401
