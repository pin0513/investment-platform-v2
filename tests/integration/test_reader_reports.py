"""Integration tests for the reader reports UI routes (P2.6)."""

import os
import uuid
from datetime import UTC, datetime

import pytest

from app.db import session_scope
from app.models.report import Report
from app.models.user import User
from app.security import create_access_token, hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)

_PERIOD_START = datetime(2026, 5, 5, tzinfo=UTC)
_PERIOD_END = datetime(2026, 5, 11, 23, 59, 59, tzinfo=UTC)


@pytest.fixture
def auth_user():
    user_id = uuid.uuid4()
    slug = f"rdrep{uuid.uuid4().hex[:6]}"
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=f"{slug}@x.z",
                slug=slug,
                role="USER",
                password_hash=hash_password("pw"),
                is_active=True,
                base_currency="TWD",
            )
        )
    yield user_id, slug
    with session_scope() as s:
        from app.models.refresh_token import RefreshToken

        s.query(Report).filter(Report.user_id == user_id).delete()
        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _h(user_id):
    t = create_access_token(subject=str(user_id), email="x@y.z", role="USER", scope="user")
    return {"Authorization": f"Bearer {t}"}


def _create_report(user_id, slug, client, headers, **kwargs):
    payload = {
        "report_type": "WEEKLY",
        "period_start": _PERIOD_START.isoformat(),
        "period_end": _PERIOD_END.isoformat(),
        "summary_md": "## 摘要\n- 本週正常",
        "content_md": "## 詳細\n### 美股\nAAPL OK.",
        "status": "DRAFT",
    }
    payload.update(kwargs)
    r = client.post("/api/v1/reports", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------
# List page
# ------------------------------------------------------------------


def test_reports_list_authenticated_returns_html(client, auth_user):
    user_id, slug = auth_user
    r = client.get(f"/{slug}/reports", headers=_h(user_id))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "投資報告" in r.text


def test_reports_list_unauthenticated_redirects(client, auth_user):
    _, slug = auth_user
    r = client.get(f"/{slug}/reports", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert "/auth/login" in r.headers["location"]


def test_reports_list_empty_state(client, auth_user):
    user_id, slug = auth_user
    r = client.get(f"/{slug}/reports", headers=_h(user_id))
    assert r.status_code == 200
    assert "尚無報告" in r.text


def test_reports_list_shows_created_report(client, auth_user):
    user_id, slug = auth_user
    headers = _h(user_id)
    _create_report(user_id, slug, client, headers)

    r = client.get(f"/{slug}/reports", headers=headers)
    assert r.status_code == 200
    assert "2026-05-05" in r.text
    assert "DRAFT" in r.text


def test_reports_list_filter_by_type(client, auth_user):
    user_id, slug = auth_user
    headers = _h(user_id)
    _create_report(user_id, slug, client, headers)

    r = client.get(f"/{slug}/reports?report_type=WEEKLY", headers=headers)
    assert r.status_code == 200
    assert "週報" in r.text


def test_reports_list_nav_link_present(client, auth_user):
    user_id, slug = auth_user
    r = client.get(f"/{slug}/reports", headers=_h(user_id))
    assert r.status_code == 200
    # nav should include a link to reports
    assert "週報" in r.text


# ------------------------------------------------------------------
# Detail page
# ------------------------------------------------------------------


def test_report_detail_renders(client, auth_user):
    user_id, slug = auth_user
    headers = _h(user_id)
    created = _create_report(user_id, slug, client, headers)
    report_id = created["id"]

    r = client.get(f"/{slug}/reports/{report_id}", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "2026-05-05" in r.text


def test_report_detail_renders_markdown(client, auth_user):
    user_id, slug = auth_user
    headers = _h(user_id)
    created = _create_report(
        user_id,
        slug,
        client,
        headers,
        content_md="## 詳細\n### 美股\nAAPL **上漲**。",
    )
    report_id = created["id"]

    r = client.get(f"/{slug}/reports/{report_id}", headers=headers)
    assert r.status_code == 200
    # markdown should be rendered to HTML
    assert "<h2" in r.text or "<h3" in r.text or "<strong>" in r.text


def test_report_detail_shows_status_badge(client, auth_user):
    user_id, slug = auth_user
    headers = _h(user_id)
    created = _create_report(user_id, slug, client, headers, status="FINAL")
    report_id = created["id"]

    r = client.get(f"/{slug}/reports/{report_id}", headers=headers)
    assert r.status_code == 200
    assert "FINAL" in r.text


def test_report_detail_not_found(client, auth_user):
    user_id, slug = auth_user
    r = client.get(f"/{slug}/reports/{uuid.uuid4()}", headers=_h(user_id))
    assert r.status_code == 404


def test_report_detail_wrong_slug(client, auth_user):
    user_id, _ = auth_user
    r = client.get(f"/wrong-slug/reports/{uuid.uuid4()}", headers=_h(user_id))
    assert r.status_code == 404


# ------------------------------------------------------------------
# Dashboard widget
# ------------------------------------------------------------------


def test_dashboard_weekly_widget_empty_state(client, auth_user):
    user_id, slug = auth_user
    r = client.get(f"/{slug}/", headers=_h(user_id))
    assert r.status_code == 200
    assert "尚無週報" in r.text


def test_dashboard_weekly_widget_shows_report(client, auth_user):
    user_id, slug = auth_user
    headers = _h(user_id)
    _create_report(user_id, slug, client, headers)

    r = client.get(f"/{slug}/", headers=headers)
    assert r.status_code == 200
    assert "近期週報" in r.text
    assert "2026-05-05" in r.text


# ------------------------------------------------------------------
# Markdown filter unit test (via API round-trip)
# ------------------------------------------------------------------


def test_md_to_html_filter():
    """Test the md_to_html filter directly."""
    from app.templating import md_to_html

    result = md_to_html("# Hello\n\n**bold** text")
    assert "<h1>" in result
    assert "<strong>" in result


def test_md_to_html_filter_none():
    from app.templating import md_to_html

    assert md_to_html(None) == ""


def test_md_to_html_filter_empty():
    from app.templating import md_to_html

    assert md_to_html("") == ""
