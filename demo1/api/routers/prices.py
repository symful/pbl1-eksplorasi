from typing import Optional

from fastapi import APIRouter, Query, Path, Response

from api.services.price_service import (
    get_quote,
    get_price_history,
    get_market_overview,
    DEFAULT_TICKERS,
    COUNTRY_MARKETS,
)
from api.models.schemas import QuoteResponse, PriceHistoryResponse, MarketOverviewResponse


router = APIRouter(prefix="/prices", tags=["Prices"])


@router.get("/quote/{symbol}", response_model=QuoteResponse)
async def get_quote_endpoint(
    response: Response,
    symbol: str = Path(..., description="Ticker symbol"),
    ticker: Optional[str] = Query(None, description="Display label"),
    proxy: Optional[str] = Query(None, description="HTTP proxy"),
    refresh: bool = Query(False, description="Bypass cache"),
):
    result = get_quote(symbol=symbol, ticker=ticker, proxy=proxy, refresh=refresh)
    response.headers["Cache-Control"] = f"private, max-age={30 if not refresh else 0}"
    return result


@router.get("/history/{symbol}", response_model=PriceHistoryResponse)
async def get_history_endpoint(
    response: Response,
    symbol: str = Path(..., description="Ticker symbol"),
    interval: str = Query("1d", description="1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo"),
    period: str = Query("3mo", description="1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max"),
    start: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    proxy: Optional[str] = Query(None, description="HTTP proxy"),
    refresh: bool = Query(False, description="Bypass cache"),
):
    result = get_price_history(
        symbol=symbol,
        interval=interval,
        period=period,
        start=start,
        end=end,
        proxy=proxy,
        refresh=refresh,
    )
    response.headers["Cache-Control"] = f"private, max-age={300 if not refresh else 0}"
    return result


@router.get("/market/{country}", response_model=MarketOverviewResponse)
async def get_market_endpoint(
    response: Response,
    country: str = Path(..., description="Country code: US, ID"),
    proxy: Optional[str] = Query(None, description="HTTP proxy"),
    refresh: bool = Query(False, description="Bypass cache"),
):
    result = get_market_overview(country=country, proxy=proxy, refresh=refresh)
    response.headers["Cache-Control"] = f"private, max-age={60 if not refresh else 0}"
    return result


@router.get("/default-tickers")
async def get_default_tickers():
    return {"tickers": DEFAULT_TICKERS}


@router.get("/supported-countries")
async def get_supported_countries():
    return {"countries": list(COUNTRY_MARKETS.keys())}
