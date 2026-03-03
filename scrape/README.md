# Economic Calendar Scraper 🇺🇸 🇮🇩

Scraper Python untuk **economic calendar** yang mengambil data dari **ForexFactory** dan **Investing.com** — dirancang untuk aplikasi investasi yang mencakup region **United States (USD)** dan **Indonesia (IDR)**.

---

## Daftar Sumber Data

| Sumber | URL | Data | Auth |
|--------|-----|------|------|
| **ForexFactory** | `nfs.faireconomy.media` | USD economic calendar (JSON API resmi) | Tidak perlu |
| **Investing.com** | `investing.com/economic-calendar` | USD + IDR economic calendar | Tidak perlu |

---

## Struktur Project

```
scrape/
├── main.py                          # Orchestrator utama (entry point)
├── config.py                        # Semua konfigurasi & konstanta
├── requirements.txt                 # Dependencies Python
├── .env.example                     # Template environment variables
├── .gitignore
│
├── models/
│   ├── __init__.py
│   └── economic_event.py            # Dataclass EconomicEvent (model data utama)
│
├── scrapers/
│   ├── __init__.py
│   ├── forexfactory_scraper.py      # ForexFactory JSON API → USD events
│   └── investing_scraper.py         # Investing.com AJAX API → USD + IDR events
│
├── utils/
│   ├── __init__.py
│   └── helpers.py                   # Logger, HTTP session, date utils, export
│
└── output/                          # Semua file hasil scraping disimpan di sini
    ├── economic_calendar_combined.json/csv
    ├── economic_calendar_usd.json/csv
    ├── economic_calendar_idr.json/csv
    ├── economic_calendar_high_impact.json/csv
    ├── forexfactory_usd.json/csv
    ├── investing_usd.json/csv
    ├── investing_idr.json/csv
    └── pipeline_summary.json
```

---

## Quick Start

### 1. Clone & Setup Environment

```bash
cd scrape

# Buat virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# atau
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Konfigurasi

```bash
# Salin template .env
cp .env.example .env

# Edit .env sesuai kebutuhan (opsional)
# Semua scraper berjalan tanpa konfigurasi tambahan
nano .env
```

### 3. Jalankan

```bash
# Jalankan semua scraper (ForexFactory + Investing.com)
python main.py

# Hanya ForexFactory
python main.py --source ff

# Hanya Investing.com
python main.py --source inv

# Kedua sumber sekaligus (eksplisit)
python main.py --source ff inv

# Filter High-impact events saja
python main.py --impact High

# Filter currency USD saja
python main.py --currency USD

# Filter currency IDR saja
python main.py --currency IDR

# Lihat 14 hari ke depan
python main.py --days-ahead 14

# Output CSV saja
python main.py --fmt csv

# Tampilkan ke terminal tanpa menyimpan file
python main.py --no-export

# Lihat semua opsi
python main.py --help
```

### 4. Jalankan Scraper Individual

```bash
# ForexFactory saja
python scrapers/forexfactory_scraper.py

# Investing.com saja
python scrapers/investing_scraper.py
```

---

## Data yang Di-scrape

### 🇺🇸 United States (USD)

| Indikator | Impact | Sumber |
|-----------|--------|--------|
| FOMC Rate Decision | 🔴 High | ForexFactory, Investing.com |
| Non-Farm Payrolls (NFP) | 🔴 High | ForexFactory, Investing.com |
| CPI / Core CPI | 🔴 High | ForexFactory, Investing.com |
| GDP Growth Rate | 🔴 High | ForexFactory, Investing.com |
| Unemployment Rate | 🔴 High | ForexFactory, Investing.com |
| Retail Sales | 🔴 High | ForexFactory, Investing.com |
| ISM Manufacturing/Services PMI | 🔴 High | ForexFactory, Investing.com |
| ADP Non-Farm Employment Change | 🔴 High | ForexFactory, Investing.com |
| Consumer Confidence | 🟡 Medium | ForexFactory, Investing.com |
| Fed Member Speeches | 🟡 Medium | ForexFactory, Investing.com |

### 🇮🇩 Indonesia (IDR)

| Indikator | Impact | Sumber |
|-----------|--------|--------|
| BI 7-Day Reverse Repo Rate (RDG) | 🔴 High | Investing.com |
| GDP Growth Rate (PDB) | 🔴 High | Investing.com |
| Inflasi (IHK/CPI) | 🔴 High | Investing.com |
| Neraca Perdagangan | 🟡 Medium | Investing.com |
| Ekspor & Impor | 🟡 Medium | Investing.com |
| Tingkat Pengangguran (TPT) | 🔴 High | Investing.com |

---

## Output Format

### `EconomicEvent` (model data utama)

Setiap event disimpan dengan struktur berikut:

```json
{
  "source": "forexfactory",
  "event_id": "",
  "date": "2025-03-06",
  "time": "20:30",
  "datetime_utc": "2025-03-06T13:30:00+00:00",
  "country": "US",
  "currency": "USD",
  "region": "United States",
  "title": "Non-Farm Employment Change",
  "category": "Labour Market",
  "description": "",
  "impact": "High",
  "impact_emoji": "🔴",
  "actual": "59K",
  "forecast": "130K",
  "previous": "143K",
  "revised": "",
  "unit": "K",
  "sentiment": "worse"
}
```

### File Output

| File | Isi |
|------|-----|
| `economic_calendar_combined.json/csv` | Semua event (FF + Investing) setelah merge & deduplikasi |
| `economic_calendar_usd.json/csv` | Events USD saja |
| `economic_calendar_idr.json/csv` | Events IDR saja |
| `economic_calendar_high_impact.json/csv` | Events High-impact saja |
| `forexfactory_usd.json/csv` | Events dari ForexFactory |
| `investing_usd.json/csv` | Events USD dari Investing.com |
| `investing_idr.json/csv` | Events IDR dari Investing.com |
| `pipeline_summary.json` | Metadata run (waktu, jumlah event, error) |

---

## Kategori Event

Setiap event secara otomatis di-tag dengan kategori berdasarkan judul:

| Kategori | Contoh Event |
|----------|-------------|
| `Monetary Policy` | FOMC Decision, BI Rate, Beige Book |
| `Inflation` | CPI, PPI, PCE, IHK |
| `Labour Market` | NFP, ADP, Unemployment Rate, TPT |
| `Growth` | GDP, PDB |
| `Trade` | Trade Balance, Neraca Perdagangan, Ekspor/Impor |
| `Business Activity` | PMI, ISM Manufacturing, ISM Services |
| `Consumer` | Retail Sales, Consumer Confidence |
| `Housing` | Building Permits, New Home Sales |
| `CB Speech` | Fed Member Speaks, BI Governor |
| `FX Reserves` | Cadangan Devisa, DXY, USD/IDR |
| `Fiscal` | Budget, Treasury, Debt |

---

## Konfigurasi Lanjutan

### Environment Variables (`.env`)

| Variable | Default | Keterangan |
|----------|---------|------------|
| `REQUEST_DELAY_SECONDS` | `2` | Jeda antar request (detik) |
| `REQUEST_TIMEOUT_SECONDS` | `30` | Timeout HTTP request |
| `MAX_RETRIES` | `3` | Jumlah retry saat gagal |
| `OUTPUT_DIR` | `output` | Direktori output file |
| `OUTPUT_FORMAT` | `both` | Format: `json`, `csv`, atau `both` |
| `DAYS_AHEAD` | `7` | Berapa hari ke depan yang di-fetch |
| `DAYS_BACK` | `1` | Berapa hari ke belakang yang di-fetch |
| `LOG_LEVEL` | `INFO` | Level log: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_TO_FILE` | `false` | Simpan log ke file |
| `LOG_FILE` | `logs/scraper.log` | Path file log |
| `HTTP_PROXY` | _(kosong)_ | Proxy HTTP (opsional) |
| `HTTPS_PROXY` | _(kosong)_ | Proxy HTTPS (opsional) |
| `USER_AGENT` | Chrome 124 | Custom User-Agent header |

### Menambah Target Currency di Investing.com

Edit `config.py`:

```python
INVESTING_COUNTRY_IDS = {
    "USD": 5,    # United States
    "IDR": 48,   # Indonesia
    "SGD": 36,   # Singapore  <- tambahkan di sini
    "MYR": 42,   # Malaysia
}
```

---

## Penggunaan sebagai Library

```python
from scrapers.forexfactory_scraper import ForexFactoryScraper
from scrapers.investing_scraper import InvestingComScraper

# --- ForexFactory: USD events minggu ini ---
ff = ForexFactoryScraper()
usd_events = ff.fetch()
high_impact = ff.fetch_high_impact()

# --- Investing.com: USD + IDR events ---
inv = InvestingComScraper(days_ahead=14)
all_events = inv.fetch()
idr_events = [e for e in all_events if e.currency == "IDR"]

# --- Pipeline lengkap ---
from main import run_pipeline

result = run_pipeline(
    sources=["ff", "inv"],
    impact_filter=["High", "Medium"],
    currency_filter=["USD", "IDR"],
    days_ahead=14,
)
print(f"Total events : {result.total_events}")
print(f"High impact  : {len(result.high_impact_events)}")
print(f"USD events   : {len(result.usd_events)}")
print(f"IDR events   : {len(result.idr_events)}")
```

---

## Catatan Teknis

### Rate Limiting
Semua scraper menggunakan delay default **2 detik** antar request. Ubah `REQUEST_DELAY_SECONDS` di `.env` jika diperlukan.

### Timezone
- Semua event ditampilkan dalam **WIB (UTC+7)**.
- `datetime_utc` disimpan dalam UTC untuk interoperabilitas.
- ForexFactory mengembalikan data dalam ET (UTC-5); konversi ke WIB dilakukan otomatis.

### ForexFactory — Feed Minggu Depan
ForexFactory mempublikasikan feed JSON untuk minggu berjalan (`ff_calendar_thisweek.json`). Feed minggu depan (`ff_calendar_nextweek.json`) **tidak selalu tersedia** dan akan menghasilkan 404 di pertengahan minggu — hal ini normal dan sudah ditangani secara diam-diam oleh scraper (hanya log INFO, bukan error).

### Investing.com Anti-Scraping
Scraper Investing.com secara otomatis:
1. Melakukan GET ke halaman kalender untuk mendapatkan session cookie.
2. Menggunakan header `X-Requested-With: XMLHttpRequest` yang diperlukan.
3. Menerapkan retry dengan exponential backoff saat terkena rate limit (HTTP 429).

---

## Dependencies

| Package | Versi | Kegunaan |
|---------|-------|----------|
| `requests` | 2.31.0 | HTTP client |
| `urllib3` | 2.2.1 | HTTP transport layer |
| `beautifulsoup4` | 4.12.3 | HTML parsing (Investing.com) |
| `lxml` | 5.2.2 | HTML/XML parser backend |
| `python-dateutil` | 2.9.0 | Date parsing |
| `pytz` | 2024.1 | Timezone handling |
| `python-dotenv` | 1.0.1 | Environment variables |
| `colorama` | 0.4.6 | Terminal colors |
| `rich` | 13.7.1 | Rich terminal output |

---

## Legal & Disclaimer

Scraping ini dilakukan untuk tujuan **akademis / tugas PBL** dengan mematuhi:
- Terms of Service masing-masing website
- Rate limiting yang wajar (delay 2 detik antar request)
- Tidak menyimpan data secara komersial
- Tidak menyalahi robots.txt

Data dari ForexFactory dan Investing.com adalah milik masing-masing penyedia. Gunakan data ini sesuai dengan ketentuan yang berlaku.

---

## Kontribusi

Pull request dan issue sangat disambut. Pastikan:
1. Jalankan scraper sebelum submit untuk memverifikasi hasilnya
2. Tambahkan docstring pada fungsi baru
3. Update `README.md` jika menambah sumber data baru