from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.analysis import Analysis


class AnalysisRepository:
    def __init__(self, session: Session):
        self.s = session

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def create(self, analysis: Analysis) -> Analysis:
        self.s.add(analysis)
        self.s.flush()
        return analysis

    def get_by_id(self, analysis_id: uuid.UUID) -> Analysis | None:
        return self.s.get(Analysis, analysis_id)

    def update(self, analysis: Analysis, **kwargs: Any) -> Analysis:
        for k, v in kwargs.items():
            setattr(analysis, k, v)
        self.s.flush()
        return analysis

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_for_instrument(
        self,
        user_id: uuid.UUID,
        instrument_id: uuid.UUID,
        *,
        analysis_type: str | None = None,
        include_superseded: bool = False,
        limit: int = 20,
    ) -> list[Analysis]:
        stmt = (
            select(Analysis)
            .where(
                and_(
                    Analysis.user_id == user_id,
                    Analysis.instrument_id == instrument_id,
                    Analysis.deleted_at.is_(None),
                )
            )
            .order_by(Analysis.as_of_date.desc(), Analysis.generated_at.desc())
            .limit(limit)
        )
        if analysis_type:
            stmt = stmt.where(Analysis.analysis_type == analysis_type)
        if not include_superseded:
            stmt = stmt.where(Analysis.is_superseded.is_(False))
        return list(self.s.execute(stmt).scalars())

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        analysis_type: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        include_superseded: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Analysis], int]:
        base_cond = and_(
            Analysis.user_id == user_id,
            Analysis.deleted_at.is_(None),
        )
        if analysis_type:
            base_cond = and_(base_cond, Analysis.analysis_type == analysis_type)
        if from_date:
            base_cond = and_(base_cond, Analysis.as_of_date >= from_date)
        if to_date:
            base_cond = and_(base_cond, Analysis.as_of_date <= to_date)
        if not include_superseded:
            base_cond = and_(base_cond, Analysis.is_superseded.is_(False))

        count_stmt = select(func.count()).select_from(Analysis).where(base_cond)
        total: int = self.s.execute(count_stmt).scalar_one()

        stmt = (
            select(Analysis)
            .where(base_cond)
            .order_by(Analysis.as_of_date.desc(), Analysis.generated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list(self.s.execute(stmt).scalars())
        return items, total

    def get_latest_per_type(
        self,
        user_id: uuid.UUID,
        instrument_id: uuid.UUID,
    ) -> dict[str, uuid.UUID]:
        """Return mapping of analysis_type -> latest (non-superseded) id."""
        stmt = (
            select(Analysis.analysis_type, Analysis.id, Analysis.generated_at)
            .where(
                and_(
                    Analysis.user_id == user_id,
                    Analysis.instrument_id == instrument_id,
                    Analysis.is_superseded.is_(False),
                    Analysis.deleted_at.is_(None),
                )
            )
            .order_by(Analysis.analysis_type, Analysis.generated_at.desc())
        )
        rows = self.s.execute(stmt).all()
        seen: dict[str, uuid.UUID] = {}
        for analysis_type, analysis_id, _ in rows:
            if analysis_type not in seen:
                seen[analysis_type] = analysis_id
        return seen
