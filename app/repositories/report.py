from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.report import Report


class ReportRepository:
    def __init__(self, session: Session):
        self.s = session

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def create(self, report: Report) -> Report:
        self.s.add(report)
        self.s.flush()
        return report

    def get_by_id(self, report_id: uuid.UUID) -> Report | None:
        return self.s.get(Report, report_id)

    def update(self, report: Report, **kwargs: Any) -> Report:
        for k, v in kwargs.items():
            setattr(report, k, v)
        self.s.flush()
        return report

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_for_user(self, user_id: uuid.UUID, report_id: uuid.UUID) -> Report | None:
        stmt = select(Report).where(
            and_(
                Report.id == report_id,
                Report.user_id == user_id,
                Report.deleted_at.is_(None),
            )
        )
        return self.s.execute(stmt).scalar_one_or_none()

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        report_type: str | None = None,
        status: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Report], int]:
        cond = and_(
            Report.user_id == user_id,
            Report.deleted_at.is_(None),
        )
        if report_type:
            cond = and_(cond, Report.report_type == report_type)
        if status:
            cond = and_(cond, Report.status == status)
        if from_dt:
            cond = and_(cond, Report.period_start >= from_dt)
        if to_dt:
            cond = and_(cond, Report.period_end <= to_dt)

        count_stmt = select(func.count()).select_from(Report).where(cond)
        total: int = self.s.execute(count_stmt).scalar_one()

        stmt = (
            select(Report)
            .where(cond)
            .order_by(Report.period_start.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list(self.s.execute(stmt).scalars())
        return items, total

    def get_latest_for_user(
        self,
        user_id: uuid.UUID,
        report_type: str,
    ) -> Report | None:
        """Return the most recent non-deleted report of the given type for the user."""
        stmt = (
            select(Report)
            .where(
                and_(
                    Report.user_id == user_id,
                    Report.report_type == report_type,
                    Report.deleted_at.is_(None),
                )
            )
            .order_by(Report.period_start.desc())
            .limit(1)
        )
        return self.s.execute(stmt).scalar_one_or_none()
