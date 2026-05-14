from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.report import Report
from app.repositories.report import ReportRepository
from app.schemas.report import ReportCreate, ReportOut, ReportPatch


class ReportNotFoundError(Exception):
    pass


class ReportService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.repo = ReportRepository(session)
        self.audit = audit

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def create(self, user_id: uuid.UUID, payload: ReportCreate) -> Report:
        now = datetime.now(UTC)
        report = Report(
            id=uuid.uuid4(),
            user_id=user_id,
            report_type=payload.report_type,
            period_start=payload.period_start,
            period_end=payload.period_end,
            generated_at=payload.generated_at,
            uploaded_at=now,
            llm_model=payload.llm_model,
            llm_provider=payload.llm_provider,
            news_detail_level=payload.news_detail_level,
            timeline=payload.timeline,
            summary_md=payload.summary_md,
            content_md=payload.content_md,
            metrics=payload.metrics,
            related_instruments=payload.related_instruments,
            related_industries=payload.related_industries,
            status=payload.status,
            version=1,
        )
        self.repo.create(report)
        self.audit.record(
            action="INSERT",
            target_table="reports",
            target_id=report.id,
            after={
                "report_type": report.report_type,
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "status": report.status,
            },
        )
        return report

    def update(
        self,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
        patch: ReportPatch,
    ) -> Report:
        report = self._get_owned(user_id, report_id)
        before: dict[str, Any] = {}
        updates: dict[str, Any] = {}

        if patch.status is not None:
            before["status"] = report.status
            updates["status"] = patch.status
        if patch.content_md is not None:
            before["content_md_len"] = len(report.content_md or "")
            updates["content_md"] = patch.content_md
        if patch.summary_md is not None:
            before["summary_md_len"] = len(report.summary_md or "")
            updates["summary_md"] = patch.summary_md
        if patch.metrics is not None:
            before["metrics"] = report.metrics
            updates["metrics"] = patch.metrics
        if patch.timeline is not None:
            before["timeline_len"] = len(report.timeline)
            updates["timeline"] = patch.timeline

        if updates:
            self.repo.update(report, **updates)
            self.audit.record(
                action="UPDATE",
                target_table="reports",
                target_id=report.id,
                before=before,
                after=updates,
            )
        return report

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, user_id: uuid.UUID, report_id: uuid.UUID) -> Report:
        return self._get_owned(user_id, report_id)

    def list(
        self,
        user_id: uuid.UUID,
        *,
        report_type: str | None = None,
        status: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ReportOut], int]:
        items, total = self.repo.list_for_user(
            user_id,
            report_type=report_type,
            status=status,
            from_dt=from_dt,
            to_dt=to_dt,
            limit=limit,
            offset=offset,
        )
        return [ReportOut.model_validate(r) for r in items], total

    def latest(self, user_id: uuid.UUID, report_type: str) -> Report | None:
        return self.repo.get_latest_for_user(user_id, report_type)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_owned(self, user_id: uuid.UUID, report_id: uuid.UUID) -> Report:
        report = self.repo.get_for_user(user_id, report_id)
        if report is None:
            raise ReportNotFoundError(f"Report {report_id} not found")
        return report
