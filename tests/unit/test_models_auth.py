from app.models.allowlisted_email import AllowlistedEmail
from app.models.refresh_token import RefreshToken
from app.models.user import User


def test_user_table_columns():
    cols = {c.name for c in User.__table__.columns}
    expected = {
        "id", "email", "google_sub", "display_name", "slug", "base_currency",
        "role", "password_hash", "is_active", "timezone", "metadata",
        "created_at", "updated_at", "deleted_at",
    }
    assert expected.issubset(cols)


def test_allowlisted_email_pk_is_email():
    pk_cols = [c.name for c in AllowlistedEmail.__table__.primary_key.columns]
    assert pk_cols == ["email"]


def test_refresh_token_has_user_fk():
    fks = {fk.column.table.name for c in RefreshToken.__table__.columns for fk in c.foreign_keys}
    assert "users" in fks
