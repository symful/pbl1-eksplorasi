import logging
from datetime import datetime, timedelta
from typing import Optional

from api.scrapers.forexfactory import fetch_forexfactory_events
from api.scrapers.investing import fetch_investing_events
from api.models.schemas import EconomicEvent, EconomicCalendarResponse
from api.services.ratelimit import RequestCache, RateLimitTracker

logger = logging.getLogger("api.services.calendar")

CALENDAR_TTL_SECONDS = 120.0


async def get_economic_calendar(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    days_back: int = 1,
    days_ahead: int = 7,
    currencies: Optional[list[str]] = None,
    impact_filter: Optional[list[str]] = None,
    sources: Optional[list[str]] = None,
) -> EconomicCalendarResponse:
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    if date_to is None:
        date_to = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    cache = RequestCache.get_instance()
    tracker = RateLimitTracker()

    cache_key = {
        "date_from": date_from,
        "date_to": date_to,
        "currencies": ",".join(sorted(currencies)) if currencies else "",
        "impact_filter": ",".join(sorted(impact_filter)) if impact_filter else "",
        "sources": ",".join(sorted(sources)) if sources else "",
    }

    try:
        cached = cache.get("calendar", **cache_key)
        if cached is not None:
            logger.debug(f"Calendar cache hit: {date_from} -> {date_to}")
            return cached
    except Exception as e:
        logger.warning(f"Cache read error: {e}")

    all_events = []
    errors = []

    ff_enabled = sources is None or "forexfactory" in sources or "ff" in sources
    inv_enabled = sources is None or "investing" in sources or "inv" in sources

    if ff_enabled:
        ff_blocked = tracker.is_blocked("forexfactory")
        if ff_blocked:
            logger.warning("ForexFactory is rate-limited, skipping")
            errors.append("forexfactory: rate limited")
        else:
            try:
                ff_events = await fetch_forexfactory_events(
                    currencies=currencies,
                    impact_filter=impact_filter,
                )
                all_events.extend(ff_events)
                logger.info(f"ForexFactory: fetched {len(ff_events)} events")
            except Exception as e:
                err_msg = str(e)
                logger.error(f"ForexFactory fetch failed: {err_msg}")
                errors.append(f"forexfactory: {err_msg}")
                if "429" in err_msg or "rate" in err_msg.lower():
                    tracker.block("forexfactory", 300.0, err_msg)

    if inv_enabled:
        inv_blocked = tracker.is_blocked("investing")
        if inv_blocked:
            logger.warning("Investing.com is rate-limited, skipping")
            errors.append("investing: rate limited")
        else:
            try:
                inv_events = await fetch_investing_events(
                    date_from=date_from,
                    date_to=date_to,
                    currencies=currencies,
                    impact_filter=impact_filter,
                )
                all_events.extend(inv_events)
                logger.info(f"Investing.com: fetched {len(inv_events)} events")
            except Exception as e:
                err_msg = str(e)
                logger.error(f"Investing.com fetch failed: {err_msg}")
                errors.append(f"investing: {err_msg}")
                if "429" in err_msg or "rate" in err_msg.lower():
                    tracker.block("investing", 300.0, err_msg)

    deduped = _deduplicate_events(all_events)
    sorted_events = sorted(deduped, key=lambda e: (e.date, e.time or "00:00"))

    usd_count = len([e for e in sorted_events if str(e.currency) == "USD"])
    idr_count = len([e for e in sorted_events if str(e.currency) == "IDR"])
    high_impact_count = len([e for e in sorted_events if str(e.impact) == "High"])

    response = EconomicCalendarResponse(
        events=sorted_events,
        total_count=len(sorted_events),
        usd_count=usd_count,
        idr_count=idr_count,
        high_impact_count=high_impact_count,
        sources=list(set(str(e.source) for e in sorted_events)),
        fetched_at=datetime.now(),
        date_from=date_from,
        date_to=date_to,
        errors=errors if errors else None,
    )

    try:
        cache.set("calendar", response, ttl=CALENDAR_TTL_SECONDS, **cache_key)
    except Exception as e:
        logger.warning(f"Cache write error: {e}")

    return response


def _deduplicate_events(events: list[EconomicEvent]) -> list[EconomicEvent]:
    seen = set()
    unique = []
    for e in events:
        key = (e.date, e.time, e.currency, e.title.lower())
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique
