"""Integration tests for STRATEGY_MONTHLY report type + dashboard strategy widget."""

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

_PERIOD_START = datetime(2026, 4, 14, tzinfo=UTC)
_PERIOD_END = datetime(2026, 5, 14, 23, 59, 59, tzinfo=UTC)


@pytest.fixture
def auth_user():
    user_id = uuid.uuid4()
    slug = f"strw{uuid.uuid4().hex[:6]}"
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


def _create_strategy(client, headers, **kwargs):
    payload = {
        "report_type": "STRATEGY_MONTHLY",
        "period_start": _PERIOD_START.isoformat(),
        "period_end": _PERIOD_END.isoformat(),
        "summary_md": "TW 半導體週期上行. 金融受利差收斂壓力. 建議加碼 2330.",
        "content_md": "## 整體判斷\n半導體上行.\n\n## Actions\n- ADD 2330",
        "status": "FINAL",
        "metrics": {
            "score": {"overall": 78},
            "actions": [
                {
                    "direction": "ADD",
                    "symbol": "2330",
                    "target_pct_change": 5.0,
                    "confidence": "HIGH",
                    "rationale_short": "半導體 AI 動能延續",
                    "time_horizon": "3M",
                },
                {
                    "direction": "TRIM",
                    "symbol": "2887",
                    "target_pct_change": -2.0,
                    "confidence": "MEDIUM",
                    "rationale_short": "利差收斂風險",
                    "time_horizon": "1M",
                },
                {
                    "direction": "HOLD",
                    "symbol": "VOO",
                    "target_pct_change": None,
                    "confidence": "HIGH",
                    "rationale_short": "核心配置不動",
                },
            ],
            "themes": ["半導體上行", "金融利差收斂"],
            "tuning_round": 1,
        },
    }
    payload.update(kwargs)
    r = client.post("/api/v1/reports", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------
# API accepts new type
# ------------------------------------------------------------------


def test_strategy_monthly_type_accepted(client, auth_user):
    user_id, _ = auth_user
    created = _create_strategy(client, _h(user_id))
    assert created["report_type"] == "STRATEGY_MONTHLY"
    assert created["metrics"]["score"]["overall"] == 78
    assert len(created["metrics"]["actions"]) == 3


def test_strategy_patch_increments_tuning(client, auth_user):
    user_id, _ = auth_user
    headers = _h(user_id)
    created = _create_strategy(client, headers)
    report_id = created["id"]

    new_metrics = dict(created["metrics"])
    new_metrics["tuning_round"] = 2
    new_metrics["prev_overall_score"] = 78
    new_metrics["score"] = {"overall": 82}

    r = client.patch(
        f"/api/v1/reports/{report_id}",
        json={"metrics": new_metrics, "summary_md": "Tuning round 2 — 修正配置建議"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["metrics"]["tuning_round"] == 2
    assert body["metrics"]["score"]["overall"] == 82


def test_unknown_strategy_type_rejected(client, auth_user):
    user_id, _ = auth_user
    r = client.post(
        "/api/v1/reports",
        json={
            "report_type": "STRATEGY_QUARTERLY",  # not yet enabled
            "period_start": _PERIOD_START.isoformat(),
            "period_end": _PERIOD_END.isoformat(),
        },
        headers=_h(user_id),
    )
    assert r.status_code == 422


# ------------------------------------------------------------------
# Dashboard widget renders
# ------------------------------------------------------------------


def test_dashboard_strategy_widget_empty_state(client, auth_user):
    user_id, slug = auth_user
    r = client.get(f"/{slug}/", headers=_h(user_id))
    assert r.status_code == 200
    assert "月度戰略" in r.text
    assert "尚無戰略報告" in r.text


def test_dashboard_strategy_widget_renders_score(client, auth_user):
    user_id, slug = auth_user
    headers = _h(user_id)
    _create_strategy(client, headers)

    r = client.get(f"/{slug}/", headers=headers)
    assert r.status_code == 200
    assert "月度戰略" in r.text
    assert "78" in r.text  # score
    assert "/ 100" in r.text


def test_dashboard_strategy_widget_renders_actions(client, auth_user):
    user_id, slug = auth_user
    headers = _h(user_id)
    _create_strategy(client, headers)

    r = client.get(f"/{slug}/", headers=headers)
    assert r.status_code == 200
    # action symbols
    assert "2330" in r.text
    assert "2887" in r.text
    assert "VOO" in r.text
    # action direction labels (emoji + text)
    assert "ADD" in r.text
    assert "TRIM" in r.text
    assert "HOLD" in r.text
    # rationale_short text
    assert "半導體 AI 動能延續" in r.text


def test_dashboard_strategy_widget_shows_tuning_badge(client, auth_user):
    user_id, slug = auth_user
    headers = _h(user_id)
    created = _create_strategy(client, headers)

    # Patch to tuning round 3
    new_metrics = dict(created["metrics"])
    new_metrics["tuning_round"] = 3
    new_metrics["prev_overall_score"] = 78
    new_metrics["score"] = {"overall": 81}
    r = client.patch(
        f"/api/v1/reports/{created['id']}",
        json={"metrics": new_metrics},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    r = client.get(f"/{slug}/", headers=headers)
    assert r.status_code == 200
    assert "tuning #3" in r.text
    # delta indicator (81 - 78 = +3)
    assert "+3" in r.text


def test_dashboard_strategy_widget_link_to_detail(client, auth_user):
    user_id, slug = auth_user
    headers = _h(user_id)
    created = _create_strategy(client, headers)

    r = client.get(f"/{slug}/", headers=headers)
    assert r.status_code == 200
    assert f"/{slug}/reports/{created['id']}" in r.text
    assert "看完整" in r.text
