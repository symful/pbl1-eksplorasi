# PBL Web Scraper APIs

This document outlines the background data scrapers used by the PBL Desktop Application, including how to call them, their rate limits, and what they do.

---

## 1. Yahoo Finance Price Scraper (`yfinance`)

**Description**: Fetches current snapshot quotes and historical OHLCV (Open, High, Low, Close, Volume) data for stocks, currencies, and indices.

**Usage**:
```python
from scrape.scrapers.yfinance_price_scraper import YahooFinancePriceScraper
scraper = YahooFinancePriceScraper()

# Snapshot
quote = scraper.fetch_quote("AAPL", ticker_label="Apple")

# History
bars = scraper.fetch_history("AAPL", "Apple", interval="1d", period="3mo")
```

**Underlying API**: Uses the unofficial `yfinance` Python library which interacts with `query2.finance.yahoo.com`.

**Rate Limits & Throttle Behavior**:
- **Strict IP Limits**: Yahoo Finance frequently rate limits (HTTP 429) requests. 
- **Mitigation (UI)**: The `MarketOverviewTab` includes a `Proxies` button allowing you to supply rotating proxy servers. When a 429 rate limit is hit, the UI goes into an automatic 3-minute cooldown before fetching again.
- **Mitigation (Backend)**: The `CountryMarketScraper` wrapper includes a randomized sleep (`random.uniform(0.1, 1.5)`) to introduce **jitter** between concurrent worker threads, preventing massive simultaneous request spikes.

---

## 2. Country Market Scraper (Wrapper)

**Description**: Higher-level concurrent wrapper around Yahoo Finance to fetch pre-defined templates of international markets (1 benchmark index + Top 5 largest stocks).

**Usage**:
```python
from scrape.scrapers.country_market_scraper import CountryMarketScraper
scraper = CountryMarketScraper(proxies=["http://myproxy:80"])

# Fetches 6 concurrent quotes
quotes_dict = scraper.fetch_all_quotes(country_code="US") 

# Fetches 6 concurrent histories
histories_dict = scraper.fetch_all_histories(country_code="US")
```

**Concurrency details**: Uses a `ThreadPoolExecutor` of up to 6 workers.

---

## 3. Economic Calendar Scrapers

**Description**: Scrapes financial calendar events (decisions, GDP, API inventories) from financial news portals.
**Supported Sources**: 
- `Investing.com` (Source key: `"inv"`)
- `ForexFactory` (Source key: `"ff"`)

**Usage**:
```python
from scrape.main import run_pipeline

# Scrape combined calendar events
result = run_pipeline(
    sources=["inv", "ff"],
    impact_filter=["High", "Medium"],
    currency_filter=["USD", "IDR"],
    days_back=1,
    days_ahead=0,
    export_fmt="json"
)
print(result.events)
```

**Rate Limits & Throttle Behavior**:
- **Investing.com**: Employs Cloudflare browser checks. The scraper uses standard `requests` with randomized User-Agent headers natively. Since the Economic Calendar updates roughly precisely on schedules (not second-by-second), it is fetched manually in the UI rather than via a looping background timer.
- **ForexFactory**: Very lenient rate limits for the calendar, but highly dependent on the `User-Agent`. 
