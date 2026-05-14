import pytest
from fastapi import HTTPException
from starlette.responses import RedirectResponse

from app.dependencies import _html_auth_or_redirect


def test_no_creds_returns_redirect_response():
    # No Authorization header, no session cookie
    resp = _html_auth_or_redirect(authorization=None, session=None, path="/pin0513/")
    assert isinstance(resp, RedirectResponse)
    assert resp.status_code == 303
    assert "/auth/login" in resp.headers["location"]
    assert "next=/pin0513/" in resp.headers["location"]


def test_bad_token_returns_redirect():
    resp = _html_auth_or_redirect(authorization="Bearer garbage", session=None, path="/pin0513/")
    assert isinstance(resp, RedirectResponse)
    assert "/auth/login" in resp.headers["location"]
