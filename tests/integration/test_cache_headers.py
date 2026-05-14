"""Regression tests for the no-store cache-control middleware.

Bug: after login the browser showed a stale pre-auth state (white screen at
`/`) until a hard refresh, because dynamic responses came back cacheable
(`cache-control: private`, no freshness directive). The middleware now forces
`no-store` on every non-static response.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


def test_dynamic_page_is_no_store(client):
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-store"


def test_root_redirect_is_no_store(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert r.headers.get("cache-control") == "no-store"


def test_static_assets_not_forced_no_store(client):
    r = client.get("/static/js/app.js")
    if r.status_code == 200:
        assert r.headers.get("cache-control") != "no-store"
