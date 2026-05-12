import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    GoogleLoginRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)


def test_login_request_validates_email():
    LoginRequest(email="x@y.z", password="abc12345")
    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email", password="abc12345")


def test_login_request_min_password_len():
    with pytest.raises(ValidationError):
        LoginRequest(email="x@y.z", password="abc")


def test_token_response_shape():
    t = TokenResponse(access_token="a", refresh_token="b", expires_in=900)
    assert t.token_type == "Bearer"


def test_refresh_request_requires_token():
    with pytest.raises(ValidationError):
        RefreshRequest(refresh_token="")


def test_google_login_request():
    GoogleLoginRequest(id_token="abc")


def test_user_out_fields():
    import uuid

    UserOut(
        id=uuid.uuid4(),
        email="x@y.z",
        slug="x",
        role="USER",
        base_currency="TWD",
        display_name=None,
    )
