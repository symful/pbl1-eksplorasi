import logging
from datetime import datetime
from typing import Optional

from api.scrapers.yfinance import fetch_quote, fetch_history
from api.models.schemas import (
    QuoteSnapshot,
    QuoteResponse,
    PriceBar,
    PriceHistoryResponse,
    MarketOverviewItem,
    MarketOverviewResponse,
)
from api.services.ratelimit import RequestCache, RateLimitTracker

logger = logging.getLogger("api.services.price")

QUOTE_TTL_SECONDS = 30.0
HISTORY_TTL_SECONDS = 300.0
MARKET_TTL_SECONDS = 60.0


DEFAULT_TICKERS = {
    "USDIDR": "IDR=X",
    "IHSG": "^JKSE",
    "BBCA": "BBCA.JK",
    "TLKM": "TLKM.JK",
    "ASII": "ASII.JK",
}

COUNTRY_MARKETS = {
    "US": {
        "name": "United States",
        "index": "^GSPC",
        "stocks": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
    },
    "ID": {
        "name": "Indonesia",
        "index": "^JKSE",
        "stocks": ["BBCA.JK", "TLKM.JK", "ASII.JK", "UNVR.JK", "HRUM.JK"],
    },
}


def get_quote(
    symbol: str,
    ticker: Optional[str] = None,
    proxy: Optional[str] = None,
    refresh: bool = False,
) -> QuoteResponse:
    label = ticker or symbol
    cache = RequestCache.get_instance()

    if not refresh:
        try:
            cached = cache.get("quote", symbol=symbol, label=label)
            if cached is not None:
                logger.debug(f"Quote cache hit: {symbol}")
                return cached
        except Exception as e:
            logger.warning(f"Quote cache read error: {e}")

    try:
        quote = fetch_quote(symbol, label, proxy=proxy)
        resp = QuoteResponse(quote=quote, fetched_at=datetime.now())
    except Exception as e:
        logger.error(f"Quote fetch failed for {symbol}: {e}")
        raise

    try:
        cache.set("quote", resp, ttl=QUOTE_TTL_SECONDS, symbol=symbol, label=label)
    except Exception as e:
        logger.warning(f"Quote cache write error: {e}")

    return resp


def get_price_history(
    symbol: str,
    ticker: Optional[str] = None,
    interval: str = "1d",
    period: str = "3mo",
    start: Optional[str] = None,
    end: Optional[str] = None,
    proxy: Optional[str] = None,
    refresh: bool = False,
) -> PriceHistoryResponse:
    label = ticker or symbol
    cache = RequestCache.get_instance()

    if not refresh:
        try:
            cached = cache.get(
                "history",
                symbol=symbol, label=label,
                interval=interval, period=period,
                start=start or "", end=end or "",
            )
            if cached is not None:
                logger.debug(f"History cache hit: {symbol}")
                return cached
        except Exception as e:
            logger.warning(f"History cache read error: {e}")

    try:
        bars = fetch_history(
            symbol=symbol,
            ticker_label=label,
            interval=interval,
            period=period,
            start=start,
            end=end,
            proxy=proxy,
        )
        resp = PriceHistoryResponse(
            symbol=symbol,
            ticker=label,
            interval=interval,
            period=period,
            bars=bars,
            bar_count=len(bars),
            fetched_at=datetime.now(),
        )
    except Exception as e:
        logger.error(f"History fetch failed for {symbol}: {e}")
        raise

    try:
        cache.set(
            "history", resp, ttl=HISTORY_TTL_SECONDS,
            symbol=symbol, label=label,
            interval=interval, period=period,
            start=start or "", end=end or "",
        )
    except Exception as e:
        logger.warning(f"History cache write error: {e}")

    return resp


def get_market_overview(
    country: str = "US",
    proxy: Optional[str] = None,
    refresh: bool = False,
) -> MarketOverviewResponse:
    cache = RequestCache.get_instance()
    tracker = RateLimitTracker()

    if not refresh:
        try:
            cached = cache.get("market", country=country)
            if cached is not None:
                logger.debug(f"Market cache hit: {country}")
                return cached
        except Exception as e:
            logger.warning(f"Market cache read error: {e}")

    market = COUNTRY_MARKETS.get(country, COUNTRY_MARKETS["US"])
    all_items = []
    errors = []

    index_item = MarketOverviewItem(
        ticker=market["name"],
        symbol=market["index"],
        name=market["name"],
        country=country,
    )
    try:
        quote = fetch_quote(market["index"], market["name"], proxy=proxy)
        index_item.last_price = quote.last_price
        index_item.change = quote.change
        index_item.change_percent = quote.change_percent
        index_item.previous_close = quote.previous_close
        index_item.day_high = quote.day_high
        index_item.day_low = quote.day_low
    except Exception as e:
        logger.warning(f"Market index quote failed for {market['index']}: {e}")
        if "429" in str(e) or "rate" in str(e).lower():
            tracker.block("yfinance", 120.0, str(e))
        errors.append(f"{market['index']}: {e}")
        index_item.error = str(e)
    all_items.append(index_item)

    for sym in market["stocks"]:
        item = MarketOverviewItem(
            ticker=sym,
            symbol=sym,
            name=sym,
            country=country,
        )
        try:
            quote = fetch_quote(sym, sym, proxy=proxy)
            item.last_price = quote.last_price
            item.change = quote.change
            item.change_percent = quote.change_percent
            item.previous_close = quote.previous_close
            item.day_high = quote.day_high
            item.day_low = quote.day_low
        except Exception as e:
            logger.warning(f"Market quote failed for {sym}: {e}")
            if "429" in str(e) or "rate" in str(e).lower():
                tracker.block("yfinance", 120.0, str(e))
            errors.append(f"{sym}: {e}")
            item.error = str(e)
        all_items.append(item)

    resp = MarketOverviewResponse(
        country=country,
        items=all_items,
        fetched_at=datetime.now(),
        errors=errors if errors else None,
    )

    try:
        cache.set("market", resp, ttl=MARKET_TTL_SECONDS, country=country)
    except Exception as e:
        logger.warning(f"Market cache write error: {e}")

    return resp
