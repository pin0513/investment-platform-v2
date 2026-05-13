"""Credentials store: ~/.ipv2/credentials (0600 JSON)."""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

from ipv2.config import config_dir


class CredentialsNotFound(Exception):
    """No credentials file exists."""


class Credentials:
    """In-memory credentials representation."""

    access_token: str
    refresh_token: str
    expires_at: datetime
    email: str

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
        email: str,
    ) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.email = email

    def is_expired(self) -> bool:
        return datetime.now(tz=UTC) >= self.expires_at

    def expires_in_seconds(self) -> float:
        delta = self.expires_at - datetime.now(tz=UTC)
        return delta.total_seconds()

    def needs_refresh(self) -> bool:
        """True when < 60 s remain on the access token."""
        return self.expires_in_seconds() < 60


def _creds_path() -> Path:
    return config_dir() / "credentials"


def save(creds: Credentials) -> None:
    """Persist credentials with 0600 permissions."""
    path = _creds_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    old_umask = os.umask(0o177)  # ensure 0600 on creation
    try:
        path.write_text(
            json.dumps(
                {
                    "access_token": creds.access_token,
                    "refresh_token": creds.refresh_token,
                    "expires_at": creds.expires_at.isoformat(),
                    "email": creds.email,
                }
            )
        )
    finally:
        os.umask(old_umask)
    # Enforce 0600 on existing files (umask only affects creation)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load() -> Credentials:
    """Load credentials from disk. Raises CredentialsNotFound if missing."""
    path = _creds_path()
    if not path.exists():
        raise CredentialsNotFound(f"No credentials at {path}. Run: ipv2 auth login")
    data = json.loads(path.read_text())
    return Credentials(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=datetime.fromisoformat(data["expires_at"]),
        email=data["email"],
    )


def delete() -> None:
    """Remove credentials file (best effort)."""
    path = _creds_path()
    if path.exists():
        path.unlink()
