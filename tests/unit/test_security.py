import uuid

import pytest
from jose import JWTError

from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip():
    plain = "super-secret-pw"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_roundtrip():
    user_id = uuid.uuid4()
    token = create_access_token(subject=str(user_id), email="x@y.z", role="USER", scope="user")
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["email"] == "x@y.z"
    assert claims["role"] == "USER"
    assert claims["scope"] == "user"
    assert "jti" in claims


def test_access_token_expiry_rejected():
    token = create_access_token(
        subject="x", email="x@y.z", role="USER", scope="user", expires_in_minutes=-1
    )
    with pytest.raises(JWTError):
        decode_access_token(token)


def test_refresh_token_format():
    raw = new_refresh_token()
    assert len(raw) >= 32

    h = hash_refresh_token(raw)
    assert h != raw
    assert hash_refresh_token(raw) == h  # deterministic
