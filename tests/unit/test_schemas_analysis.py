"""Unit tests for analysis Pydantic schemas."""
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisCreate, AnalysisList, AnalysisPatch


def test_analysis_create_valid():
    data = AnalysisCreate(
        analysis_type="NEWS",
        as_of_date=date(2026, 5, 1),
        content_md="# News\nSome content",
    )
    assert data.analysis_type == "NEWS"
    assert data.metrics == {}
    assert data.sources == []


def test_analysis_create_with_sources():
    data = AnalysisCreate(
        analysis_type="VALUATION",
        as_of_date=date(2026, 5, 1),
        content_md="DCF analysis",
        sources=[{"url": "https://example.com", "title": "Example"}],
    )
    assert len(data.sources) == 1
    assert data.sources[0].url == "https://example.com"


def test_analysis_create_invalid_type():
    with pytest.raises(ValidationError):
        AnalysisCreate(
            analysis_type="INVALID_TYPE",
            as_of_date=date(2026, 5, 1),
            content_md="x",
        )


def test_analysis_create_empty_content_md_fails():
    with pytest.raises(ValidationError):
        AnalysisCreate(
            analysis_type="NEWS",
            as_of_date=date(2026, 5, 1),
            content_md="",
        )


def test_analysis_patch_partial():
    p = AnalysisPatch(is_superseded=True)
    assert p.is_superseded is True
    assert p.metadata is None


def test_analysis_patch_empty():
    p = AnalysisPatch()
    assert p.is_superseded is None
    assert p.metadata is None


def test_analysis_list_structure():
    lst = AnalysisList(total=0, items=[])
    assert lst.total == 0
    assert lst.items == []
    assert lst.filters == {}
