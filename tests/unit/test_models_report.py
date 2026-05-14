"""Unit tests for the Report model."""

from app.models.report import Report


def test_report_table_name():
    assert Report.__tablename__ == "reports"


def test_report_columns():
    cols = {c.name for c in Report.__table__.columns}
    expected = {
        "id",
        "user_id",
        "report_type",
        "period_start",
        "period_end",
        "generated_at",
        "uploaded_at",
        "llm_model",
        "llm_provider",
        "news_detail_level",
        "timeline",
        "summary_md",
        "content_md",
        "metrics",
        "related_instruments",
        "related_industries",
        "status",
        "version",
        "prev_version_id",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert expected.issubset(cols)


def test_report_fks():
    fk_targets = {fk.column.table.name for c in Report.__table__.columns for fk in c.foreign_keys}
    assert "users" in fk_targets
    assert "reports" in fk_targets  # self-referential prev_version_id


def test_report_indexes():
    index_names = {idx.name for idx in Report.__table__.indexes}
    assert "ix_reports_user_id" in index_names
    assert "ix_reports_report_type" in index_names
    assert "ix_reports_status" in index_names
    assert "ix_reports_user_type_period" in index_names
