# PBL Desktop App (Economic Calendar + Prices)

Desktop app berbasis **Tkinter** untuk kebutuhan PBL:
1. **Scraping Economic Calendar** (USD & IDR) dari pipeline yang sudah ada (`scrape/`)
2. **Scraping harga** (USD/IDR, IHSG, BBCA) via **Yahoo Finance** (`yfinance`)
3. **Visualisasi** langsung di UI:
   - Tabel event + detail JSON (economic calendar)
   - Grafik harga (line close) + tabel OHLCV + quote snapshot JSON (prices)
4. Output utama: **JSON**, disimpan dan juga ditampilkan di UI.

> Catatan: Data `yfinance` sifatnya *unofficial* dari Yahoo Finance, kadang bisa rate-limit/berubah field yang tersedia.

---

## Struktur Singkat

- `desktop_app/main.py`  
  Entry point UI desktop (tab Economic Calendar & Prices).

- `scrape/`  
  Engine scraping economic calendar (ForexFactory + Investing.com) + export output.

- `scrape/scrapers/yfinance_price_scraper.py`  
  Scraper harga via `yfinance`.

---

## Requirements

App ini jalan di Python 3.x dan butuh dependency yang ada di:

- `scrape/requirements.txt`

Yang penting untuk desktop app:
- `requests`, `beautifulsoup4`, `lxml`, dll (economic calendar)
- `yfinance`, `pandas` (prices)
- `matplotlib` (visualisasi chart di Tkinter)

Jika `matplotlib` belum terpasang di environment kamu, install juga:
- `matplotlib`

---

## Cara Setup & Run (Linux/macOS)

Dari root project:

1) Masuk ke folder scraper dan install dependency
```bash
cd pbl1-eksplorasi/scrape
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install matplotlib
```

2) Jalankan desktop app
```bash
cd ../desktop_app
python main.py
```

---

## Cara Setup & Run (Windows PowerShell)

Dari root project:

1) Install dependency
```powershell
cd pbl1-eksplorasi\scrape
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install matplotlib
```

2) Jalankan desktop app
```powershell
cd ..\desktop_app
python main.py
```

---

## Fitur UI

### Tab: Economic Calendar
- Filter:
  - Currency: `ALL / USD / IDR`
  - Impact: `High / Medium / Low`
  - Days back & days ahead (window kalender)
- Tombol:
  - **Refresh Calendar**: menjalankan pipeline calendar dan load hasil ke tabel UI
  - **Export JSON…**: simpan event yang sedang tampil di UI ke JSON pilihan kamu
- Saat refresh, pipeline juga menyimpan JSON ke:
  - `scrape/output/` (mis. `economic_calendar_combined.json`, dll)

### Tab: Prices
- Instrument:
  - `USDIDR` → `IDR=X`
  - `IHSG` → `^JKSE`
  - `BBCA` → `BBCA.JK`
- Interval & period (mis. `1d`, `3mo`)
- Start/End date optional (format `YYYY-MM-DD`)
- Tombol:
  - **Refresh Prices**: ambil quote + history, tampilkan
  - **Export JSON…**: export gabungan quote+history dari UI ke file JSON

---

## Output JSON (yang dihasilkan)

### Economic Calendar (via pipeline)
Disimpan otomatis oleh pipeline ke `scrape/output/`:
- `economic_calendar_combined.json`
- `economic_calendar_usd.json`
- `economic_calendar_idr.json`
- `economic_calendar_high_impact.json`
- `forexfactory_usd.json`
- `investing_usd.json`
- `investing_idr.json`
- `pipeline_summary.json`

### Prices (dari UI export)
File export dari UI akan berisi:
- `quote` (snapshot)
- `history` (list OHLCV)

---

## Troubleshooting

### 1) UI tidak muncul / error Tkinter
- Pastikan Python kamu include Tk/Tcl.
  - Linux: kadang perlu install paket OS `python3-tk`
  - Windows/macOS biasanya sudah include

### 2) `yfinance` error / kosong
- Coba ganti `interval`/`period` (mis. `1d` + `6mo`)
- Coba ulang beberapa menit (Yahoo kadang rate-limit)
- Pastikan koneksi internet OK

### 3) Economic calendar Investing/FF error
- Investing.com bisa throttle (HTTP 429). Pipeline sudah ada retry/backoff, tapi tetap bisa gagal kalau terlalu sering refresh.

---

## Catatan untuk Laporan PBL (biar gampang nulis)
- Data event diambil dari:
  - ForexFactory (feed JSON resmi) untuk USD
  - Investing.com (AJAX endpoint) untuk USD dan IDR
- Data harga diambil dari:
  - Yahoo Finance via `yfinance`:
    - `IDR=X`, `^JKSE`, `BBCA.JK`
- Visualisasi:
  - Harga: plot line harga `close`
  - Event: tabel + detail JSON (klik row)

---