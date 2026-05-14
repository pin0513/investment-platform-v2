"""Integration tests for the reports REST API (P2.6)."""

import os
import uuid
from datetime import UTC, datetime

import pytest

from app.db import session_scope
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)

_NOW = datetime.now(UTC)
_PERIOD_START = "2026-05-05T00:00:00+00:00"
_PERIOD_END = "2026-05-11T23:59:59+00:00"


@pytest.fixture
def auth(client):
    """Create a test user and return (headers, user_id, slug)."""
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"rep-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"rep{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("test-password-123"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        email, slug = u.email, u.slug

    token = client.post(
        "/auth/login", json={"email": email, "password": "test-password-123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, slug


def _weekly_payload(**overrides):
    data = {
        "report_type": "WEEKLY",
        "period_start": _PERIOD_START,
        "period_end": _PERIOD_END,
        "summary_md": "## 週報摘要\n- 本週持倉表現良好",
        "content_md": "## 詳細內容\n### 美股\nAAPL 上漲 2%。",
        "llm_model": "claude-opus-4-5",
        "llm_provider": "anthropic",
        "news_detail_level": "SUMMARY",
        "status": "DRAFT",
        "metrics": {"total_return": 0.02},
        "related_instruments": ["AAPL", "TSMC"],
        "timeline": [{"ts": "2026-05-10", "label": "AAPL 上漲"}],
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------
# POST
# ------------------------------------------------------------------


def test_create_report(client, auth):
    headers, _ = auth
    r = client.post("/api/v1/reports", json=_weekly_payload(), headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["report_type"] == "WEEKLY"
    assert body["status"] == "DRAFT"
    assert body["llm_model"] == "claude-opus-4-5"
    assert body["uploaded_at"] is not None
    assert "id" in body


def test_create_report_invalid_type(client, auth):
    headers, _ = auth
    r = client.post(
        "/api/v1/reports",
        json={**_weekly_payload(), "report_type": "BOGUS"},
        headers=headers,
    )
    assert r.status_code == 422


def test_create_report_invalid_status(client, auth):
    headers, _ = auth
    r = client.post(
        "/api/v1/reports",
        json={**_weekly_payload(), "status": "INVALID"},
        headers=headers,
    )
    assert r.status_code == 422


def test_create_report_unauthenticated(client):
    r = client.post("/api/v1/reports", json=_weekly_payload())
    assert r.status_code == 401


# ------------------------------------------------------------------
# GET list
# ------------------------------------------------------------------


def test_list_reports_empty(client, auth):
    headers, _ = auth
    r = client.get("/api/v1/reports", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "items" in body
    assert isinstance(body["items"], list)


def test_list_reports_after_create(client, auth):
    headers, _ = auth
    client.post("/api/v1/reports", json=_weekly_payload(), headers=headers)
    r = client.get("/api/v1/reports", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1


def test_list_reports_filter_by_type(client, auth):
    headers, _ = auth
    # Create a WEEKLY and a MONTHLY
    client.post("/api/v1/reports", json=_weekly_payload(), headers=headers)
    client.post(
        "/api/v1/reports",
        json={**_weekly_payload(), "report_type": "MONTHLY"},
        headers=headers,
    )
    r = client.get("/api/v1/reports?report_type=WEEKLY", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["report_type"] == "WEEKLY" for i in items)


def test_list_reports_filter_by_status(client, auth):
    headers, _ = auth
    client.post("/api/v1/reports", json={**_weekly_payload(), "status": "FINAL"}, headers=headers)
    r = client.get("/api/v1/reports?status=FINAL", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["status"] == "FINAL" for i in items)


def test_list_reports_unauthenticated(client):
    r = client.get("/api/v1/reports")
    assert r.status_code == 401


# ------------------------------------------------------------------
# GET latest
# ------------------------------------------------------------------


def test_get_latest_report(client, auth):
    headers, _ = auth
    client.post("/api/v1/reports", json=_weekly_payload(), headers=headers)
    r = client.get("/api/v1/reports/latest?type=WEEKLY", headers=headers)
    assert r.status_code == 200
    assert r.json()["report_type"] == "WEEKLY"


def test_get_latest_report_not_found(client, auth):
    headers, _ = auth
    r = client.get("/api/v1/reports/latest?type=DAILY", headers=headers)
    assert r.status_code == 404


# ------------------------------------------------------------------
# GET detail
# ------------------------------------------------------------------


def test_get_report_by_id(client, auth):
    headers, _ = auth
    create_r = client.post("/api/v1/reports", json=_weekly_payload(), headers=headers)
    report_id = create_r.json()["id"]

    r = client.get(f"/api/v1/reports/{report_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == report_id


def test_get_report_not_found(client, auth):
    headers, _ = auth
    fake_id = uuid.uuid4()
    r = client.get(f"/api/v1/reports/{fake_id}", headers=headers)
    assert r.status_code == 404


def test_get_report_wrong_user_returns_404(client, auth):
    headers, _ = auth
    create_r = client.post("/api/v1/reports", json=_weekly_payload(), headers=headers)
    report_id = create_r.json()["id"]

    # Create a second user
    with session_scope() as s:
        u2 = User(
            id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"other{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("test-password-123"),
            is_active=True,
        )
        s.add(u2)
        s.commit()
        email2 = u2.email

    token2 = client.post(
        "/auth/login", json={"email": email2, "password": "test-password-123"}
    ).json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    r = client.get(f"/api/v1/reports/{report_id}", headers=headers2)
    assert r.status_code == 404


# ------------------------------------------------------------------
# PATCH
# ------------------------------------------------------------------


def test_patch_report_status(client, auth):
    headers, _ = auth
    create_r = client.post("/api/v1/reports", json=_weekly_payload(), headers=headers)
    report_id = create_r.json()["id"]

    r = client.patch(f"/api/v1/reports/{report_id}", json={"status": "FINAL"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "FINAL"


def test_patch_report_content(client, auth):
    headers, _ = auth
    create_r = client.post("/api/v1/reports", json=_weekly_payload(), headers=headers)
    report_id = create_r.json()["id"]

    new_content = "## Updated Content\nNew insights added."
    r = client.patch(
        f"/api/v1/reports/{report_id}",
        json={"content_md": new_content},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["content_md"] == new_content


def test_patch_report_not_found(client, auth):
    headers, _ = auth
    r = client.patch(f"/api/v1/reports/{uuid.uuid4()}", json={"status": "FINAL"}, headers=headers)
    assert r.status_code == 404


def test_patch_report_invalid_status(client, auth):
    headers, _ = auth
    create_r = client.post("/api/v1/reports", json=_weekly_payload(), headers=headers)
    report_id = create_r.json()["id"]
    r = client.patch(
        f"/api/v1/reports/{report_id}",
        json={"status": "INVALID"},
        headers=headers,
    )
    assert r.status_code == 422


def test_patch_report_metrics(client, auth):
    headers, _ = auth
    create_r = client.post("/api/v1/reports", json=_weekly_payload(), headers=headers)
    report_id = create_r.json()["id"]

    r = client.patch(
        f"/api/v1/reports/{report_id}",
        json={"metrics": {"total_return": 0.05, "sharpe": 1.2}},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["metrics"]["sharpe"] == 1.2
