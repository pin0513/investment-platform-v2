from unittest.mock import patch

import pytest

from app.services.auth import GoogleIdTokenVerifier, GoogleVerifyError


def test_verify_returns_payload_on_success(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client.apps.googleusercontent.com")
    fake_payload = {
        "sub": "1234567890",
        "email": "x@y.z",
        "email_verified": True,
        "name": "X Y",
        "aud": "client.apps.googleusercontent.com",
    }
    with patch("app.services.auth.id_token.verify_oauth2_token", return_value=fake_payload):
        v = GoogleIdTokenVerifier()
        out = v.verify("fake.id.token")
        assert out["email"] == "x@y.z"
        assert out["sub"] == "1234567890"


def test_verify_rejects_unverified_email(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client.apps.googleusercontent.com")
    fake_payload = {
        "sub": "1234567890",
        "email": "x@y.z",
        "email_verified": False,
        "aud": "client.apps.googleusercontent.com",
    }
    with patch("app.services.auth.id_token.verify_oauth2_token", return_value=fake_payload):
        v = GoogleIdTokenVerifier()
        with pytest.raises(GoogleVerifyError):
            v.verify("fake.id.token")
