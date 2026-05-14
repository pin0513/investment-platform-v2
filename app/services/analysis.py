from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.analysis import Analysis
from app.repositories.analysis import AnalysisRepository
from app.schemas.analysis import AnalysisCreate, AnalysisOut, AnalysisPatch


class AnalysisNotFoundError(Exception):
    pass


class AnalysisService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.repo = AnalysisRepository(session)
        self.audit = audit

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def create(
        self,
        user_id: uuid.UUID,
        instrument_id: uuid.UUID,
        payload: AnalysisCreate,
    ) -> Analysis:
        analysis = Analysis(
            id=uuid.uuid4(),
            user_id=user_id,
            instrument_id=instrument_id,
            analysis_type=payload.analysis_type,
            angle=payload.angle,
            as_of_date=payload.as_of_date,
            title=payload.title,
            summary_md=payload.summary_md,
            content_md=payload.content_md,
            metrics=payload.metrics,
            sources=[s.model_dump() for s in payload.sources],
            llm_model=payload.llm_model,
            confidence=payload.confidence,
            is_superseded=False,
            metadata_json=payload.metadata,
        )
        self.repo.create(analysis)
        self.audit.record(
            action="INSERT",
            target_table="analyses",
            target_id=analysis.id,
            after={
                "analysis_type": analysis.analysis_type,
                "instrument_id": str(instrument_id),
                "as_of_date": str(analysis.as_of_date),
            },
        )
        return analysis

    def mark_superseded(
        self,
        user_id: uuid.UUID,
        analysis_id: uuid.UUID,
    ) -> Analysis:
        analysis = self._get_owned(user_id, analysis_id)
        before = {"is_superseded": analysis.is_superseded}
        self.repo.update(analysis, is_superseded=True)
        self.audit.record(
            action="UPDATE",
            target_table="analyses",
            target_id=analysis.id,
            before=before,
            after={"is_superseded": True},
        )
        return analysis

    def patch(
        self,
        user_id: uuid.UUID,
        analysis_id: uuid.UUID,
        payload: AnalysisPatch,
    ) -> Analysis:
        analysis = self._get_owned(user_id, analysis_id)
        before: dict[str, Any] = {}
        updates: dict[str, Any] = {}

        if payload.is_superseded is not None:
            before["is_superseded"] = analysis.is_superseded
            updates["is_superseded"] = payload.is_superseded

        if payload.metadata is not None:
            before["metadata"] = analysis.metadata_json
            updates["metadata_json"] = payload.metadata

        if updates:
            self.repo.update(analysis, **updates)
            self.audit.record(
                action="UPDATE",
                target_table="analyses",
                target_id=analysis.id,
                before=before,
                after=dict(updates.items()),
            )
        return analysis

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, user_id: uuid.UUID, analysis_id: uuid.UUID) -> Analysis:
        return self._get_owned(user_id, analysis_id)

    def list_for_instrument(
        self,
        user_id: uuid.UUID,
        instrument_id: uuid.UUID,
        *,
        analysis_type: str | None = None,
        include_superseded: bool = False,
        limit: int = 20,
    ) -> list[AnalysisOut]:
        items = self.repo.list_for_instrument(
            user_id,
            instrument_id,
            analysis_type=analysis_type,
            include_superseded=include_superseded,
            limit=limit,
        )
        latest_ids = self.repo.get_latest_per_type(user_id, instrument_id)
        return [self._to_out(a, latest_ids) for a in items]

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
    ) -> tuple[list[AnalysisOut], int]:
        items, total = self.repo.list_for_user(
            user_id,
            analysis_type=analysis_type,
            from_date=from_date,
            to_date=to_date,
            include_superseded=include_superseded,
            limit=limit,
            offset=offset,
        )
        # is_latest is instrument-scoped; for cross-instrument listing we skip it
        return [AnalysisOut.model_validate(a) for a in items], total

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_owned(self, user_id: uuid.UUID, analysis_id: uuid.UUID) -> Analysis:
        analysis = self.repo.get_by_id(analysis_id)
        if analysis is None or analysis.deleted_at is not None or analysis.user_id != user_id:
            raise AnalysisNotFoundError(f"Analysis {analysis_id} not found")
        return analysis

    @staticmethod
    def _to_out(analysis: Analysis, latest_ids: dict[str, uuid.UUID]) -> AnalysisOut:
        out = AnalysisOut.model_validate(analysis)
        out.is_latest = latest_ids.get(analysis.analysis_type) == analysis.id
        return out
