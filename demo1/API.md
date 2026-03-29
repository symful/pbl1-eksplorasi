# PBL Economic & Market Data API v2.1.0

FastAPI-based REST API for scraping economic calendar data and market prices from free sources (no API keys required).

---

## Quick Start

```bash
cd demo1
source scrape/venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

API runs at: http://localhost:8000
Interactive docs: http://localhost:8000/docs

---

## Endpoints

### Health Check
```
GET /health
```
Returns `{"status":"healthy"}`

---

### Economic Calendar

#### Get Combined Calendar
```
GET /calendar/
```
Query parameters:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date_from` | string | auto | Start date (YYYY-MM-DD) |
| `date_to` | string | auto | End date (YYYY-MM-DD) |
| `days_back` | int | 1 | Days before today (0-30) |
| `days_ahead` | int | 7 | Days ahead (0-90) |
| `currencies` | string | all | Comma-separated: USD,IDR |
| `impact` | string | all | Comma-separated: High,Medium,Low |
| `sources` | string | both | Comma-separated: forexfactory,investing |
| `refresh` | bool | false | Bypass cache and force fresh fetch |

Response includes `Cache-Control: private, max-age=120` header.

Example:
```
GET /calendar/?currencies=USD,IDR&impact=High&days_ahead=14
```

#### ForexFactory Only
```
GET /calendar/forexfactory?days_ahead=7
```

#### Investing.com Only
```
GET /calendar/investing?currencies=USD,IDR&days_ahead=14
```

---

### Market Prices

#### Get Quote
```
GET /prices/quote/{symbol}
```
Examples:
- `/prices/quote/IDR=X` — USD/IDR exchange rate
- `/prices/quote/AAPL` — Apple stock
- `/prices/quote/BBCA.JK` — BBCA stock

Query parameters: `ticker`, `proxy`, `refresh` (bypass cache)

Response: `Cache-Control: private, max-age=30`

#### Get Price History
```
GET /prices/history/{symbol}?interval=1d&period=3mo
```
Query parameters: `interval`, `period`, `start`, `end`, `proxy`, `refresh`

Response: `Cache-Control: private, max-age=300`

#### Get Market Overview
```
GET /prices/market/{country}
```
Countries: `US`, `ID`

Response: `Cache-Control: private, max-age=60`

#### List Default Tickers
```
GET /prices/default-tickers
```

#### List Supported Countries
```
GET /prices/supported-countries
```

---

### Cache Management

#### Cache Status
```
GET /cache/status
```
Returns current cache entry count and rate limit states per source.

```json
{
  "cache_entries": 2,
  "rate_limits": {
    "forexfactory": {"blocked": false, "retry_after": 0, "consecutive_errors": 0},
    "investing": {"blocked": false, "retry_after": 0, "consecutive_errors": 0},
    "yfinance": {"blocked": false, "retry_after": 0, "consecutive_errors": 0}
  }
}
```

#### Clear Cache
```
POST /cache/clear
```
Clears all cached responses.

#### Unblock Rate-Limited Source
```
POST /rate-limit/unblock/{source}
```
Manually unblocks a rate-limited source (forexfactory, investing, yfinance).

---

## Caching

| Endpoint Group | TTL | Notes |
|---------------|-----|-------|
| Calendar | 120s | Deduplicated, multi-source merge |
| Quotes | 30s | Per symbol |
| Price History | 300s | Per symbol+interval+period |
| Market Overview | 60s | Per country |

Use `?refresh=true` on any endpoint to bypass cache.

---

## Rate Limiting & Retry

| Source | Retry Mechanism |
|--------|----------------|
| ForexFactory | Tenacity: 3 attempts, exponential backoff 2-10s |
| Investing.com | Tenacity: 3 attempts, 2-10s backoff + 2s between pages |
| Yahoo Finance | 120s cooldown on 429, auto-resume |

When a source is rate-limited, subsequent requests skip that source and return partial data with an `errors` field listing which sources failed.

---

## Data Sources

| Source | Data Type | Auth Required |
|--------|-----------|---------------|
| ForexFactory | Economic Calendar (USD) | No |
| Investing.com | Economic Calendar (USD, IDR) | No |
| Yahoo Finance | Stock/FX/Crypto Prices | No |

---

## Response Models

### EconomicCalendarResponse
```json
{
  "events": [...],
  "total_count": 129,
  "usd_count": 122,
  "idr_count": 7,
  "high_impact_count": 3,
  "sources": ["forexfactory", "investing"],
  "fetched_at": "2026-03-29T01:52:18",
  "date_from": "2026-03-28",
  "date_to": "2026-04-01",
  "errors": null
}
```

### QuoteResponse
```json
{
  "quote": {
    "ticker": "IDR=X",
    "symbol": "IDR=X",
    "fetched_at_utc": "2026-03-29T01:26:04Z",
    "currency": "IDR",
    "last_price": 16925.0,
    "change": 27.0,
    "change_percent": 0.16
  },
  "fetched_at": "2026-03-29T01:26:06"
}
```

---

## Running the Server

```bash
cd demo1
source scrape/venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

For production:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```
