import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import calendar, prices

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("api")

app = FastAPI(
    title="PBL Economic & Market Data API",
    description="API for scraping economic calendar and market price data from ForexFactory, Investing.com, and Yahoo Finance",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(calendar.router)
app.include_router(prices.router)


@app.get("/")
async def root():
    return {
        "name": "PBL Economic & Market Data API",
        "version": "2.1.0",
        "endpoints": {
            "calendar": "/calendar",
            "prices": "/prices",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/cache/status")
async def cache_status():
    from api.services.ratelimit import RequestCache, RateLimitTracker
    cache = RequestCache.get_instance()
    tracker = RateLimitTracker()

    with cache._lock:
        cache_entries = len(cache._cache)

    states = {}
    for src in ("forexfactory", "investing", "yfinance"):
        st = tracker.get_state(src)
        if st:
            states[src] = {
                "blocked": st.blocked_until > 0,
                "blocked_until": st.blocked_until,
                "retry_after": st.retry_after,
                "consecutive_errors": st.consecutive_errors,
                "last_error": st.last_error,
            }

    return {
        "cache_entries": cache_entries,
        "rate_limits": states,
    }


@app.post("/cache/clear")
async def cache_clear():
    from api.services.ratelimit import RequestCache
    cache = RequestCache.get_instance()
    cache.clear()
    logger.info("Cache cleared")
    return {"status": "cleared"}


@app.post("/rate-limit/unblock/{source}")
async def unblock_source(source: str):
    from api.services.ratelimit import RateLimitTracker
    tracker = RateLimitTracker()
    tracker.unblock(source)
    logger.info(f"Rate limit unblocked for: {source}")
    return {"status": "unblocked", "source": source}
