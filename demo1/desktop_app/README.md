# PBL Desktop App (PyQt5)

Desktop app berbasis **PyQt5** + **pyqtgraph** untuk kebutuhan PBL:

1. **Kalender Ekonomi** — USD & IDR events dari ForexFactory & Investing.com
2. **Harga Instrumen** — USD/IDR, IHSG, saham via Yahoo Finance
3. **Market Overview** — US (S&P500 + 5 saham) & ID (IHSG + 5 saham)

---

## Requirements

Semua dependency ada di `scrape/requirements.txt`:
- PyQt5, pyqtgraph, pyqtdarktheme
- yfinance, requests, beautifulsoup4

---

## Cara Setup & Run

```bash
cd demo1/desktop_app
python main.py
```

Atau dari root project:
```bash
cd demo1
python desktop_app/main.py
```

---

## Tab Aplikasi

### Tab: Economic Calendar
- Filter: currency (USD/IDR/ALL), impact (High/Medium/Low), date range
- Sumber: ForexFactory, Investing.com (dual source)
- Refresh: fetch + deduplicate + display
- Export: simpan JSON

### Tab: Prices
- Instruments: USDIDR, IHSG, BBCA, TLKM, ASII
- Interval & period (1d, 3mo, dll)
- Chart: pyqtgraph line plot
- OHLCV table + quote JSON
- Export: JSON

### Tab: Market Overview
- Negara: US, ID
- Index + 5 saham per negara
- Fetch Quotes → chart + table
- Auto-refresh (30s / 1m / 2m / 5m)
- Rate limit cooldown (120s) jika Yahoo throttle

---

## Arsitektur UI

```
main.py
└── MainWindow
    ├── CalendarTab      # Economic calendar (dual-source)
    ├── PricesTab        # Single instrument prices
    └── MarketTab        # Multi-instrument market overview
```

---

## Troubleshooting

### Yahoo Finance rate limit
- Jika 429: 120s cooldown otomatis
- Matikan auto-refresh sementara

### Qt platform plugin not found
```bash
export QT_QPA_PLATFORM=offscreen  # untuk headless
```

### Economic calendar kosong
- ForexFactory/Investing.com mungkin throttle
- Coba beberapa menit kemudian
