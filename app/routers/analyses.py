"""REST API for per-instrument persistent analyses (P2.5)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.repositories.instrument import InstrumentRepository
from app.schemas.analysis import AnalysisCreate, AnalysisList, AnalysisOut, AnalysisPatch
from app.services.analysis import AnalysisNotFoundError, AnalysisService

router = APIRouter(tags=["analyses"])


def _audit(request: Request, user: User, db: Session) -> AuditWriter:
    rid = getattr(request.state, "request_id", None)
    return AuditWriter(
        db,
        request_id=uuid.UUID(rid) if rid else None,
        actor_user_id=user.id,
        actor_type="USER",
    )


def _svc(request: Request, user: User, db: Session) -> AnalysisService:
    return AnalysisService(db, _audit(request, user, db))


# ──────────────────────────────────────────────────────────────
#  Instrument-scoped endpoints
# ──────────────────────────────────────────────────────────────


@router.post(
    "/api/v1/instruments/{symbol}/analyses",
    response_model=AnalysisOut,
    status_code=201,
)
def create_analysis(
    symbol: str,
    payload: AnalysisCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    market: Annotated[str | None, Query()] = None,
) -> AnalysisOut:
    inst = InstrumentRepository(db).get_by_symbol_market(symbol, market)
    if inst is None:
        raise HTTPException(404, f"Instrument {symbol!r} not found")

    svc = _svc(request, user, db)
    analysis = svc.create(user.id, inst.id, payload)
    db.commit()

    # Refresh to pick up server defaults (generated_at, created_at)
    db.refresh(analysis)
    items = svc.list_for_instrument(user.id, inst.id, limit=1)
    out = AnalysisOut.model_validate(analysis)
    if len(items) > 0 and items[0].id == analysis.id:
        out.is_latest = items[0].is_latest
    return out


@router.get(
    "/api/v1/instruments/{symbol}/analyses",
    response_model=AnalysisList,
)
def list_analyses_for_instrument(
    symbol: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    market: Annotated[str | None, Query()] = None,
    analysis_type: Annotated[str | None, Query()] = None,
    include_superseded: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(le=100)] = 20,
) -> AnalysisList:
    inst = InstrumentRepository(db).get_by_symbol_market(symbol, market)
    if inst is None:
        raise HTTPException(404, f"Instrument {symbol!r} not found")

    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = AnalysisService(db, audit)
    items = svc.list_for_instrument(
        user.id,
        inst.id,
        analysis_type=analysis_type,
        include_superseded=include_superseded,
        limit=limit,
    )
    return AnalysisList(
        total=len(items),
        items=items,
        filters={
            "symbol": symbol,
            "analysis_type": analysis_type,
            "include_superseded": include_superseded,
        },
    )


# ──────────────────────────────────────────────────────────────
#  Single-analysis endpoints
# ──────────────────────────────────────────────────────────────


@router.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(
    analysis_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisOut:
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = AnalysisService(db, audit)
    try:
        analysis = svc.get(user.id, analysis_id)
    except AnalysisNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return AnalysisOut.model_validate(analysis)


@router.patch("/api/v1/analyses/{analysis_id}", response_model=AnalysisOut)
def patch_analysis(
    analysis_id: uuid.UUID,
    payload: AnalysisPatch,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisOut:
    svc = _svc(request, user, db)
    try:
        analysis = svc.patch(user.id, analysis_id, payload)
    except AnalysisNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    db.refresh(analysis)
    return AnalysisOut.model_validate(analysis)


# ──────────────────────────────────────────────────────────────
#  Cross-instrument search
# ──────────────────────────────────────────────────────────────


@router.get("/api/v1/analyses", response_model=AnalysisList)
def search_analyses(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    analysis_type: Annotated[str | None, Query()] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    include_superseded: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnalysisList:
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = AnalysisService(db, audit)
    items, total = svc.list_for_user(
        user.id,
        analysis_type=analysis_type,
        from_date=from_date,
        to_date=to_date,
        include_superseded=include_superseded,
        limit=limit,
        offset=offset,
    )
    return AnalysisList(
        total=total,
        items=items,
        filters={
            "analysis_type": analysis_type,
            "from": str(from_date) if from_date else None,
            "to": str(to_date) if to_date else None,
            "include_superseded": include_superseded,
        },
    )
