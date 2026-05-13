"""httpx-based API client with Bearer token injection and auto-refresh."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from ipv2.config import resolve_base_url
from ipv2.credentials import Credentials, CredentialsNotFound
from ipv2.credentials import load as load_creds
from ipv2.credentials import save as save_creds


class AuthRequired(Exception):
    """Operation requires authentication but no credentials found."""


class APIError(Exception):
    """Non-2xx response from the API."""

    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body
        if isinstance(body, dict):
            msg = body.get("detail") or body.get("message") or str(body)
        else:
            msg = str(body)
        super().__init__(f"HTTP {status_code}: {msg}")


class IPV2Client:
    """Thin httpx wrapper.

    Usage:
        with IPV2Client(base_url) as client:
            data = client.get("/api/v1/portfolio/summary")
    """

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self._base_url = (base_url or resolve_base_url()).rstrip("/")
        self._override_token = token
        self._http: httpx.Client | None = None

    def __enter__(self) -> IPV2Client:
        self._http = httpx.Client(base_url=self._base_url, timeout=30.0)
        return self

    def __exit__(self, *_: Any) -> None:
        if self._http:
            self._http.close()

    def _get_token(self) -> str | None:
        if self._override_token:
            return self._override_token
        env_token = os.environ.get("IPV2_TOKEN")
        if env_token:
            return env_token
        try:
            creds = load_creds()
            if creds.needs_refresh():
                creds = self._do_refresh(creds)
            return creds.access_token
        except CredentialsNotFound:
            return None

    def _do_refresh(self, creds: Credentials) -> Credentials:
        """Call /auth/refresh and rotate credentials."""
        assert self._http is not None
        resp = self._http.post(
            "/auth/refresh",
            json={"refresh_token": creds.refresh_token},
        )
        if resp.status_code != 200:
            body = resp.json() if resp.content else {}
            raise APIError(resp.status_code, body)
        data = resp.json()
        new_creds = Credentials(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.now(tz=UTC) + timedelta(seconds=data["expires_in"]),
            email=creds.email,
        )
        save_creds(new_creds)
        return new_creds

    def _headers(self) -> dict[str, str]:
        token = self._get_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    def get(self, path: str, **kwargs: Any) -> Any:
        assert self._http is not None
        resp = self._http.get(path, headers=self._headers(), **kwargs)
        return self._raise_for_status(resp)

    def post(self, path: str, **kwargs: Any) -> Any:
        assert self._http is not None
        resp = self._http.post(path, headers=self._headers(), **kwargs)
        return self._raise_for_status(resp)

    def patch(self, path: str, **kwargs: Any) -> Any:
        assert self._http is not None
        resp = self._http.patch(path, headers=self._headers(), **kwargs)
        return self._raise_for_status(resp)

    def put(self, path: str, **kwargs: Any) -> Any:
        assert self._http is not None
        resp = self._http.put(path, headers=self._headers(), **kwargs)
        return self._raise_for_status(resp)

    def delete(self, path: str, **kwargs: Any) -> Any:
        assert self._http is not None
        resp = self._http.delete(path, headers=self._headers(), **kwargs)
        return self._raise_for_status(resp)

    def _raise_for_status(self, resp: httpx.Response) -> Any:
        if resp.status_code == 204:
            return None
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        if not resp.is_success:
            raise APIError(resp.status_code, body)
        return body
