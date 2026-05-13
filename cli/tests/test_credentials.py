"""Tests for credentials store: save/load/permissions."""

from __future__ import annotations

import os
import stat
from datetime import UTC, datetime, timedelta

import pytest

from ipv2.credentials import Credentials, CredentialsNotFound, delete, load, save


@pytest.fixture(autouse=True)
def isolated_config_dir(tmp_path, monkeypatch):
    """Redirect ~/.ipv2 to a temp dir for every test."""
    monkeypatch.setenv("IPV2_CONFIG_DIR", str(tmp_path))
    return tmp_path


def _make_creds(email: str = "test@example.com") -> Credentials:
    return Credentials(
        access_token="acc_token_123",
        refresh_token="ref_token_456",
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        email=email,
    )


def test_save_and_load_roundtrip():
    creds = _make_creds()
    save(creds)
    loaded = load()
    assert loaded.access_token == "acc_token_123"
    assert loaded.refresh_token == "ref_token_456"
    assert loaded.email == "test@example.com"
    assert loaded.expires_at == datetime(2030, 1, 1, tzinfo=UTC)


def test_file_has_0600_permissions(tmp_path):
    save(_make_creds())
    creds_path = tmp_path / "credentials"
    mode = stat.S_IMODE(os.stat(creds_path).st_mode)
    assert mode == 0o600, f"Expected 0600, got {oct(mode)}"


def test_load_raises_when_missing():
    with pytest.raises(CredentialsNotFound):
        load()


def test_delete_removes_file():
    save(_make_creds())
    delete()
    with pytest.raises(CredentialsNotFound):
        load()


def test_delete_is_idempotent():
    delete()  # no error even if file doesn't exist


def test_is_expired_false_for_future():
    creds = _make_creds()
    assert not creds.is_expired()


def test_is_expired_true_for_past():
    creds = Credentials(
        access_token="a",
        refresh_token="r",
        expires_at=datetime(2000, 1, 1, tzinfo=UTC),
        email="x@y.com",
    )
    assert creds.is_expired()


def test_needs_refresh_false_for_far_future():
    creds = _make_creds()
    assert not creds.needs_refresh()


def test_needs_refresh_true_near_expiry():
    creds = Credentials(
        access_token="a",
        refresh_token="r",
        expires_at=datetime.now(tz=UTC) + timedelta(seconds=30),
        email="x@y.com",
    )
    assert creds.needs_refresh()
