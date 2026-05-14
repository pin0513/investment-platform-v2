"""Unit tests for report Pydantic schemas."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.report import ReportCreate, ReportList, ReportOut, ReportPatch


def _now():
    return datetime.now(UTC)


def test_report_create_minimal():
    data = ReportCreate(
        report_type="WEEKLY",
        period_start=_now(),
        period_end=_now(),
    )
    assert data.report_type == "WEEKLY"
    assert data.status == "DRAFT"
    assert data.timeline == []
    assert data.metrics == {}
    assert data.related_instruments == []
    assert data.related_industries == []


def test_report_create_full():
    data = ReportCreate(
        report_type="MONTHLY",
        period_start=datetime(2026, 5, 1, tzinfo=UTC),
        period_end=datetime(2026, 5, 31, tzinfo=UTC),
        generated_at=_now(),
        llm_model="claude-opus-4-5",
        llm_provider="anthropic",
        news_detail_level="SUMMARY",
        summary_md="# Summary\nPortfolio up 3% this month.",
        content_md="## Details\nSomething happened.",
        metrics={"total_return": 0.03},
        related_instruments=["AAPL", "TSMC"],
        status="FINAL",
    )
    assert data.report_type == "MONTHLY"
    assert data.status == "FINAL"
    assert data.llm_model == "claude-opus-4-5"
    assert data.news_detail_level == "SUMMARY"
    assert len(data.related_instruments) == 2


def test_report_create_invalid_type():
    with pytest.raises(ValidationError):
        ReportCreate(
            report_type="BOGUS",
            period_start=_now(),
            period_end=_now(),
        )


def test_report_create_invalid_status():
    with pytest.raises(ValidationError):
        ReportCreate(
            report_type="WEEKLY",
            period_start=_now(),
            period_end=_now(),
            status="INVALID_STATUS",
        )


def test_report_create_invalid_news_detail_level():
    with pytest.raises(ValidationError):
        ReportCreate(
            report_type="WEEKLY",
            period_start=_now(),
            period_end=_now(),
            news_detail_level="FULL_DETAIL",
        )


def test_report_patch_partial():
    p = ReportPatch(status="FINAL")
    assert p.status == "FINAL"
    assert p.content_md is None
    assert p.metrics is None


def test_report_patch_empty():
    p = ReportPatch()
    assert p.status is None
    assert p.content_md is None
    assert p.summary_md is None
    assert p.metrics is None
    assert p.timeline is None


def test_report_patch_invalid_status():
    with pytest.raises(ValidationError):
        ReportPatch(status="INVALID")


def test_report_list_empty():
    lst = ReportList(total=0, items=[])
    assert lst.total == 0
    assert lst.items == []


def test_report_out_from_attributes():
    """Verify model_config from_attributes=True allows ORM-like dict construction."""
    uid = uuid.uuid4()
    now = _now()
    data = {
        "id": uuid.uuid4(),
        "user_id": uid,
        "report_type": "WEEKLY",
        "period_start": now,
        "period_end": now,
        "generated_at": None,
        "uploaded_at": None,
        "llm_model": None,
        "llm_provider": None,
        "news_detail_level": None,
        "timeline": [],
        "summary_md": None,
        "content_md": None,
        "metrics": {},
        "related_instruments": [],
        "related_industries": [],
        "status": "DRAFT",
        "version": 1,
        "prev_version_id": None,
        "created_at": now,
        "updated_at": now,
    }
    # Should not raise
    out = ReportOut.model_validate(data)
    assert out.status == "DRAFT"
    assert out.version == 1
