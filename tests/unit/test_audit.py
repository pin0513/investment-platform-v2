import os
import uuid

import pytest
from sqlalchemy import select

from app.audit import AuditWriter
from app.db import session_scope
from app.models.audit_log import AuditLog

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


def test_audit_writer_writes_row(monkeypatch):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    request_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    with session_scope() as s:
        writer = AuditWriter(s, request_id=request_id, actor_user_id=actor_id, ip="1.2.3.4")
        writer.record(
            action="INSERT",
            target_table="accounts",
            target_id=uuid.uuid4(),
            before=None,
            after={"name": "test"},
        )

    with session_scope() as s:
        rows = s.execute(select(AuditLog).where(AuditLog.request_id == request_id)).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.action == "INSERT"
        assert row.target_table == "accounts"
        assert row.after == {"name": "test"}
