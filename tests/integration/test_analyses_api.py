"""Integration tests for the analyses API (P2.5)."""
import os
import uuid

import pytest

from app.db import session_scope
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)

TODAY = "2026-05-14"


@pytest.fixture
def auth(client):
    """Create a user + instrument for each test (function-scoped to match client)."""
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"ana-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"ana{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("test-password-123"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        email = u.email

    token = client.post("/auth/login", json={"email": email, "password": "test-password-123"}).json()[
        "access_token"
    ]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a unique instrument per test
    sym = f"ANA{uuid.uuid4().hex[:6].upper()}"
    r = client.post(
        "/api/v1/instruments",
        json={"symbol": sym, "asset_class": "STOCK", "currency": "TWD"},
        headers=headers,
    )
    assert r.status_code == 201, r.text

    return headers, sym


def test_create_analysis(client, auth):
    headers, sym = auth
    r = client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={
            "analysis_type": "NEWS",
            "as_of_date": TODAY,
            "title": "TSMC 新聞摘要",
            "summary_md": "法說會重點",
            "content_md": "## 重點\n- AI 需求強勁",
            "confidence": "HIGH",
            "angle": "中長期",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["analysis_type"] == "NEWS"
    assert body["title"] == "TSMC 新聞摘要"
    assert body["confidence"] == "HIGH"
    assert body["is_superseded"] is False
    assert "id" in body


def test_create_second_analysis_same_type(client, auth):
    """Append-only: second row for same type is fine."""
    headers, sym = auth
    r = client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={
            "analysis_type": "NEWS",
            "as_of_date": TODAY,
            "content_md": "Second analysis",
        },
        headers=headers,
    )
    assert r.status_code == 201


def test_list_analyses_for_instrument(client, auth):
    headers, sym = auth
    # Create one first
    client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={"analysis_type": "NEWS", "as_of_date": TODAY, "content_md": "Some news"},
        headers=headers,
    )

    r = client.get(f"/api/v1/instruments/{sym}/analyses", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    items = body["items"]
    assert len(items) >= 1
    assert all(i["analysis_type"] is not None for i in items)


def test_list_analyses_filter_by_type(client, auth):
    headers, sym = auth
    # Create a VALUATION analysis
    client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={
            "analysis_type": "VALUATION",
            "as_of_date": TODAY,
            "content_md": "DCF: fair value $800",
        },
        headers=headers,
    )
    # Create a NEWS analysis
    client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={"analysis_type": "NEWS", "as_of_date": TODAY, "content_md": "News content"},
        headers=headers,
    )

    r = client.get(
        f"/api/v1/instruments/{sym}/analyses?analysis_type=VALUATION",
        headers=headers,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(i["analysis_type"] == "VALUATION" for i in items)


def test_get_single_analysis(client, auth):
    headers, sym = auth
    r = client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={
            "analysis_type": "TECHNICAL",
            "as_of_date": TODAY,
            "content_md": "RSI oversold",
        },
        headers=headers,
    )
    analysis_id = r.json()["id"]

    r = client.get(f"/api/v1/analyses/{analysis_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == analysis_id


def test_patch_analysis_superseded(client, auth):
    headers, sym = auth
    r = client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={
            "analysis_type": "MACRO",
            "as_of_date": TODAY,
            "content_md": "Fed hike expected",
        },
        headers=headers,
    )
    analysis_id = r.json()["id"]

    r = client.patch(
        f"/api/v1/analyses/{analysis_id}",
        json={"is_superseded": True},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["is_superseded"] is True


def test_patch_analysis_wrong_user_returns_404(client, auth):
    headers, sym = auth

    # Create a second user
    with session_scope() as s:
        u2 = User(
            id=uuid.uuid4(),
            email=f"evil-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"evil{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("test-password-123"),
            is_active=True,
        )
        s.add(u2)
        s.commit()
        email2 = u2.email

    token2 = client.post("/auth/login", json={"email": email2, "password": "test-password-123"}).json()[
        "access_token"
    ]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # User1 creates an analysis
    r = client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={
            "analysis_type": "GENERAL",
            "as_of_date": TODAY,
            "content_md": "General thoughts",
        },
        headers=headers,
    )
    analysis_id = r.json()["id"]

    # User2 tries to patch it — should be 404
    r = client.patch(
        f"/api/v1/analyses/{analysis_id}",
        json={"is_superseded": True},
        headers=headers2,
    )
    assert r.status_code == 404


def test_search_analyses_across_instruments(client, auth):
    headers, sym = auth
    client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={"analysis_type": "INDUSTRY", "as_of_date": TODAY, "content_md": "Industry trends"},
        headers=headers,
    )

    r = client.get("/api/v1/analyses", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "items" in body
    assert body["total"] >= 1


def test_search_analyses_filter_by_type(client, auth):
    headers, _ = auth
    r = client.get("/api/v1/analyses?type=NEWS", headers=headers)
    assert r.status_code == 200


def test_instrument_not_found_returns_404(client, auth):
    headers, _ = auth
    r = client.get("/api/v1/instruments/NONEXISTENT_ZZZ/analyses", headers=headers)
    assert r.status_code == 404


def test_create_analysis_invalid_type(client, auth):
    headers, sym = auth
    r = client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={
            "analysis_type": "BOGUS_TYPE",
            "as_of_date": TODAY,
            "content_md": "x",
        },
        headers=headers,
    )
    assert r.status_code == 422


def test_analysis_404_for_nonexistent_id(client, auth):
    headers, _ = auth
    fake_id = uuid.uuid4()
    r = client.get(f"/api/v1/analyses/{fake_id}", headers=headers)
    assert r.status_code == 404


def test_unauthenticated_returns_401(client, auth):
    _, sym = auth
    r = client.get(f"/api/v1/instruments/{sym}/analyses")
    assert r.status_code == 401


def test_analysis_with_sources(client, auth):
    headers, sym = auth
    r = client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={
            "analysis_type": "NEWS",
            "as_of_date": TODAY,
            "content_md": "News with sources",
            "sources": [
                {"url": "https://cnyes.com/news/123", "title": "鉅亨網報導"},
            ],
        },
        headers=headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert len(body["sources"]) == 1
    assert body["sources"][0]["url"] == "https://cnyes.com/news/123"


def test_patch_metadata(client, auth):
    headers, sym = auth
    r = client.post(
        f"/api/v1/instruments/{sym}/analyses",
        json={"analysis_type": "CHIP_FLOW", "as_of_date": TODAY, "content_md": "Chip analysis"},
        headers=headers,
    )
    analysis_id = r.json()["id"]

    r = client.patch(
        f"/api/v1/analyses/{analysis_id}",
        json={"metadata": {"reviewed_by": "analyst_A"}},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["metadata"]["reviewed_by"] == "analyst_A"
