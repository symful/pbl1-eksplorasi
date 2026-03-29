from typing import Optional

from fastapi import APIRouter, Query, Response

from api.services.calendar_service import get_economic_calendar
from api.models.schemas import EconomicCalendarResponse, ImpactLevel, Currency


router = APIRouter(prefix="/calendar", tags=["Economic Calendar"])


@router.get("/", response_model=EconomicCalendarResponse)
async def get_calendar(
    response: Response,
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    days_back: int = Query(1, ge=0, le=30, description="Days before today"),
    days_ahead: int = Query(7, ge=0, le=90, description="Days ahead"),
    currencies: Optional[str] = Query(None, description="Comma-separated: USD,IDR"),
    impact: Optional[str] = Query(None, description="Comma-separated: High,Medium,Low"),
    sources: Optional[str] = Query(None, description="Comma-separated: forexfactory,investing"),
    refresh: bool = Query(False, description="Bypass cache and force fresh fetch"),
):
    currency_list = [c.strip().upper() for c in currencies.split(",")] if currencies else None
    impact_list = [i.strip() for i in impact.split(",")] if impact else None
    source_list = [s.strip() for s in sources.split(",")] if sources else None

    if refresh:
        from api.services.ratelimit import RequestCache
        cache = RequestCache.get_instance()
        cache_key = {
            "date_from": date_from or "",
            "date_to": date_to or "",
            "currencies": ",".join(sorted(currency_list)) if currency_list else "",
            "impact_filter": ",".join(sorted(impact_list)) if impact_list else "",
            "sources": ",".join(sorted(source_list)) if source_list else "",
        }
        cache.invalidate("calendar", **cache_key)

    result = await get_economic_calendar(
        date_from=date_from,
        date_to=date_to,
        days_back=days_back,
        days_ahead=days_ahead,
        currencies=currency_list,
        impact_filter=impact_list,
        sources=source_list,
    )

    response.headers["Cache-Control"] = "private, max-age=120"
    return result


@router.get("/forexfactory", response_model=EconomicCalendarResponse)
async def get_forexfactory_calendar(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    days_ahead: int = 7,
):
    return await get_economic_calendar(
        date_from=date_from,
        date_to=date_to,
        days_ahead=days_ahead,
        sources=["forexfactory"],
    )


@router.get("/investing", response_model=EconomicCalendarResponse)
async def get_investing_calendar(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    currencies: Optional[str] = None,
    days_ahead: int = 7,
):
    currency_list = [c.strip().upper() for c in currencies.split(",")] if currencies else ["USD", "IDR"]
    return await get_economic_calendar(
        date_from=date_from,
        date_to=date_to,
        days_ahead=days_ahead,
        currencies=currency_list,
        sources=["investing"],
    )
