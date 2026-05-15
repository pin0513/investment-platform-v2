from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user
from app.models.user import User
from app.services.market_data import (
    fetch_public_subscriptions,
    fetch_twd_fx_rates,
    fetch_usd_twd_rate,
)

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/usd-twd")
def usd_twd(user: Annotated[User, Depends(get_current_user)]):
    try:
        return fetch_usd_twd_rate().to_dict()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"USD/TWD unavailable: {e}") from e


@router.get("/fx-rates")
def fx_rates(user: Annotated[User, Depends(get_current_user)]):
    try:
        rates = fetch_twd_fx_rates()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"FX rates unavailable: {e}") from e
    return {
        "quote": "TWD",
        "rates": [rate.to_dict() for rate in rates],
    }


@router.get("/public-subscriptions")
def public_subscriptions(user: Annotated[User, Depends(get_current_user)]):
    try:
        items = fetch_public_subscriptions()
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Public subscription list unavailable: {e}"
        ) from e
    return {
        "source": "HiStock",
        "source_url": "https://histock.tw/stock/public.aspx",
        "items": [item.to_dict() for item in items],
    }
