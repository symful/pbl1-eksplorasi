# PBL Desktop App (Economic Calendar & Prices) v2.1.0

Desktop app berbasis **PyQt5** + **FastAPI** untuk memantau:
- **Kalender Ekonomi** dari ForexFactory & Investing.com
- **Harga instrumen** dari Yahoo Finance
- **Market overview** per negara (US, ID)

---

## Running the App

```bash
cd demo1/desktop_app
python main.py
```

Requirements: PyQt5, pyqtgraph (see `scrape/requirements.txt`)

---

## Running the API Server

```bash
cd demo1
source scrape/venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /calendar/` | Combined economic calendar |
| `GET /calendar/forexfactory` | ForexFactory only |
| `GET /calendar/investing` | Investing.com only |
| `GET /prices/quote/{symbol}` | Current quote (e.g. IDR=X, AAPL, BBCA.JK) |
| `GET /prices/history/{symbol}` | Historical OHLCV |
| `GET /prices/market/{country}` | Market overview (US, ID) |

---

## Project Structure

```
demo1/
├── api/                          # FastAPI REST API
│   ├── main.py                   # Entry point
│   ├── requirements.txt
│   ├── models/schemas.py         # Pydantic models
│   ├── routers/
│   │   ├── calendar.py           # /calendar/* endpoints
│   │   └── prices.py             # /prices/* endpoints
│   ├── scrapers/
│   │   ├── forexfactory.py       # Async FF scraper
│   │   ├── investing.py          # Async Investing scraper
│   │   └── yfinance.py           # Yahoo Finance scraper
│   └── services/
│       ├── calendar_service.py
│       └── price_service.py
│
├── desktop_app/                  # PyQt5 Desktop App
│   ├── main.py                   # Entry point
│   └── ui/
│       ├── main_window.py       # MainWindow (tabs)
│       ├── calendar_tab.py       # Economic calendar tab
│       ├── prices_tab.py         # Prices tab
│       ├── market_tab.py         # Market overview tab
│       └── utils.py              # Helper functions
│
└── scrape/                       # Original CLI scrapers
    ├── main.py
    ├── config.py
    ├── models/
    └── scrapers/
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **API Framework** | FastAPI + Uvicorn |
| **Data Models** | Pydantic v2 |
| **HTTP Client** | httpx (async), requests |
| **Web Scraping** | BeautifulSoup4 |
| **Financial Data** | yfinance |
| **Retry Logic** | tenacity |
| **GUI Framework** | PyQt5 + pyqtgraph |

---

## Rate Limiting

| Source | Mechanism |
|--------|-----------|
| ForexFactory | Tenacity: 3 attempts, exponential backoff 2-10s |
| Investing.com | Tenacity: 3 attempts + 2s sleep between pages |
| Yahoo Finance | 120s cooldown on 429; returns empty on failures |

### Cache Management
- `GET /cache/status` — View cache entries and rate limit states
- `POST /cache/clear` — Clear all cached responses
- `POST /rate-limit/unblock/{source}` — Manually unblock a source

Use `?refresh=true` on any endpoint to bypass cache.
