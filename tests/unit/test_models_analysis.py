"""Unit tests for the Analysis model."""

from app.models.analysis import Analysis


def test_analysis_table_name():
    assert Analysis.__tablename__ == "analyses"


def test_analysis_columns():
    cols = {c.name for c in Analysis.__table__.columns}
    expected = {
        "id",
        "user_id",
        "instrument_id",
        "analysis_type",
        "angle",
        "as_of_date",
        "generated_at",
        "title",
        "summary_md",
        "content_md",
        "metrics",
        "sources",
        "llm_model",
        "confidence",
        "is_superseded",
        "metadata",  # mapped as metadata_json
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert expected.issubset(cols)


def test_analysis_fks():
    fk_targets = {fk.column.table.name for c in Analysis.__table__.columns for fk in c.foreign_keys}
    assert "users" in fk_targets
    assert "instruments" in fk_targets


def test_analysis_indexes():
    index_names = {idx.name for idx in Analysis.__table__.indexes}
    assert "ix_analyses_user_id" in index_names
    assert "ix_analyses_instrument_id" in index_names
    assert "ix_analyses_analysis_type" in index_names
    assert "ix_analyses_instrument_date" in index_names
