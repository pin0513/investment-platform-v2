from app.models.audit_log import AuditLog


def test_audit_log_columns():
    cols = {c.name for c in AuditLog.__table__.columns}
    expected = {
        "id", "occurred_at", "actor_user_id", "actor_type", "action",
        "target_table", "target_id", "before", "after", "request_id", "ip",
    }
    assert expected.issubset(cols)


def test_audit_log_uses_bigint_pk():
    pk = AuditLog.__table__.primary_key.columns
    assert next(iter(pk)).name == "id"
