# ============================================================
# Economic Calendar Scraper - Configuration
# ============================================================

import os

from dotenv import load_dotenv

load_dotenv()

# ── General ─────────────────────────────────────────────────
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY_SECONDS", 2))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", 30))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "false").lower() == "true"
LOG_FILE = os.getenv("LOG_FILE", "logs/scraper.log")
DAYS_AHEAD = int(os.getenv("DAYS_AHEAD", 7))
DAYS_BACK = int(os.getenv("DAYS_BACK", 1))

# ── Output ───────────────────────────────────────────────────
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "both")  # csv | json | both
APPEND_MODE = os.getenv("APPEND_MODE", "false").lower() == "true"

# ── Proxy ────────────────────────────────────────────────────
PROXIES: dict | None = None
_http = os.getenv("HTTP_PROXY", "").strip()
_https = os.getenv("HTTPS_PROXY", "").strip()
if _http or _https:
    PROXIES = {}
    if _http:
        PROXIES["http"] = _http
    if _https:
        PROXIES["https"] = _https

# ── User-Agent ───────────────────────────────────────────────
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Target Regions ───────────────────────────────────────────
TARGET_CURRENCIES = ["USD", "IDR"]
TARGET_COUNTRIES = ["US", "ID"]  # ISO-2 codes

# ── Importance Filter ────────────────────────────────────────
# Include all impact levels by default; adjust as needed.
IMPACT_LEVELS = ["High", "Medium", "Low"]

# ── ForexFactory ─────────────────────────────────────────────
FF_BASE_URL = "https://nfs.faireconomy.media"
FF_THIS_WEEK = f"{FF_BASE_URL}/ff_calendar_thisweek.json"
FF_NEXT_WEEK = f"{FF_BASE_URL}/ff_calendar_nextweek.json"

# ForexFactory uses these country codes in the JSON feed.
# Note: IDR (Indonesian Rupiah) is not covered by ForexFactory;
# Indonesian events are sourced from Investing.com instead.
FF_TARGET_CURRENCIES = ["USD"]

# ── Investing.com ─────────────────────────────────────────────
# Internal AJAX endpoint used by the Investing.com economic calendar.
INVESTING_CALENDAR_URL = "https://www.investing.com/economic-calendar/"
INVESTING_CALENDAR_API = (
    "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"
)

# Country IDs used by Investing.com's internal API.
INVESTING_COUNTRY_IDS = {
    "USD": 5,  # United States
    "IDR": 48,  # Indonesia
}

# Importance level IDs (1 = High, 2 = Medium, 3 = Low).
INVESTING_IMPORTANCE_IDS = {
    "High": 1,
    "Medium": 2,
    "Low": 3,
}

INVESTING_HEADERS = {
    **DEFAULT_HEADERS,
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": INVESTING_CALENDAR_URL,
    "Origin": "https://www.investing.com",
}


# ── Category Labels ───────────────────────────────────────────
# Maps keyword fragments in event titles to a semantic category.
# Used to enrich scraped events with a standardised category field.
EVENT_CATEGORIES = {
    # Monetary Policy
    "rate decision": "Monetary Policy",
    "interest rate": "Monetary Policy",
    "fomc": "Monetary Policy",
    "fed": "Monetary Policy",
    "rapat dewan": "Monetary Policy",
    "bi rate": "Monetary Policy",
    "repo rate": "Monetary Policy",
    "beige book": "Monetary Policy",
    "monetary": "Monetary Policy",
    # Inflation
    "cpi": "Inflation",
    "pce": "Inflation",
    "inflation": "Inflation",
    "ppi": "Inflation",
    "deflator": "Inflation",
    # Labour Market
    "nonfarm": "Labour Market",
    "non-farm": "Labour Market",
    "payroll": "Labour Market",
    "unemployment": "Labour Market",
    "jobless": "Labour Market",
    "employment": "Labour Market",
    "job": "Labour Market",
    "adp": "Labour Market",
    "tenaga kerja": "Labour Market",
    # Growth / GDP
    "gdp": "Growth",
    "gross domestic": "Growth",
    "pdb": "Growth",
    # Trade
    "trade balance": "Trade",
    "neraca": "Trade",
    "current account": "Trade",
    "export": "Trade",
    "import": "Trade",
    # Business Activity
    "pmi": "Business Activity",
    "ism": "Business Activity",
    "manufacturing": "Business Activity",
    "services": "Business Activity",
    # Consumer
    "retail": "Consumer",
    "consumer confid": "Consumer",
    "consumer credit": "Consumer",
    "penjualan": "Consumer",
    # Housing
    "housing": "Housing",
    "building": "Housing",
    "home": "Housing",
    "construction": "Housing",
    # Central Bank Speech
    "speaks": "CB Speech",
    "testimony": "CB Speech",
    "press": "CB Speech",
    # Reserves & FX
    "reserve": "FX Reserves",
    "devisa": "FX Reserves",
    "foreign": "FX Reserves",
    # Government / Fiscal
    "budget": "Fiscal",
    "treasury": "Fiscal",
    "debt": "Fiscal",
    "deficit": "Fiscal",
}
