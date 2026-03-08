# PBL Desktop App (Economic Calendar & Prices)

Aplikasi desktop berbasis **Python (Tkinter)** yang terintegrasi dengan pipeline data scraping untuk memantau **Kalender Ekonomi** (bersumber dari ForexFactory & Investing.com) serta pergerakan **Harga Instrumen Finansial** (bersumber dari Yahoo Finance). Aplikasi ini mencakup pencatatan data ke dalam format JSON/CSV dan visualisasi data secara langsung melalui antarmuka grafis.

---

## Tampilan Aplikasi

*(Tambahkan screenshot aplikasi di sini jika ada)*
Aplikasi memiliki jendela antarmuka Tkinter (PyQt5) modern berdesain latar gelap (Dark Theme) dengan pembagian tab fungsional:
- **Tab Economic Calendar**: Menampilkan tabel event ekonomi beserta detail JSON saat baris (row) diklik.
- **Tab Prices**: Menampilkan grafik harga (line close chart), tabel historis OHLCV (Open, High, Low, Close, Volume), dan snapshot quote JSON untuk instrumen spesifik.
- **Tab Market Overview**: Memantau banyak instrumen finansial berdasarkan negara (Indeks, Saham, Futures, Forex, Bond) secara *real-time* via Finnhub Websocket atau *Auto-Refresh* berkala dengan API. Menampilkan tabel quote *live* dan grafik historis interaktif dengan kapabilitas *export* yang komprehensif.

---

### Struktur Folder

```text
demo1/
├── desktop_app/
│   ├── main.py                          # Entry point aplikasi GUI (PyQt5)
│   └── ui/                              # Komponen antarmuka grafis
│       ├── main_window.py               # Window utama pengelola Tab
│       ├── calendar_tab.py              # Tab Economic Calendar
│       ├── prices_tab.py                # Tab Single Asset Price
│       ├── market_tab.py                # Tab Market Overview (Advanced)
│       └── utils.py                     # Utilitas konversi tipe & string untuk UI
│
└── scrape/
    ├── main.py                          # Orchestrator utama pemrosesan scraping (`run_pipeline`)
    ├── config.py                        # Konfigurasi konstanta, delay, proxy (.env support), kategori event
    ├── requirements.txt                 # Daftar dependensi Python
    ├── .env.example                     # Template pengaturan environment variables
    │
    ├── models/
    │   └── economic_event.py            # Model `dataclass` untuk data `EconomicEvent` dengan logic sentimen
    │
    ├── scrapers/
    │   ├── forexfactory_scraper.py      # Scraper feed JSON resmi ForexFactory
    │   ├── investing_scraper.py         # Scraper internal AJAX API Investing.com (support Pagination)
    │   ├── yfinance_price_scraper.py    # Wrapper `yfinance` dengan handler Rate Limit & Error khusus intraday
    │   ├── country_market_scraper.py    # `ThreadPoolExecutor` concurrent fetch untuk Top 5 Stocks & Index 10 negara dengan *Proxy Rotation*
    │   └── finnhub_websocket.py         # Subclass `QThread` khusus koneksi websocket `wss://ws.finnhub.io` real-time
    │
    ├── utils/
    │   └── helpers.py                   # Utilitas: custom Logger, safe HTTP Requests dengan *Exponential Backoff* Retry, manajemen zona waktu, dan ekspor data (JSON/CSV)
    │
    └── output/                          # Folder tempat hasil ekstraksi (JSON/CSV) disatukan
```

---

## Tech Stack

| Komponen | Teknologi | Keterangan |
|---|---|---|
| **Bahasa Utama** | Python 3.8+ | Bahasa backend dan frontend integrasi |
| **GUI Framework** | PyQt5, `qdarktheme` | Membangun antarmuka desktop modern berlatar gelap |
| **HTTP Requests & Parsing** | `requests`, `urllib3` (Retry), `bs4` | Ekstraksi sesi, cookie, & parsing DOM HTML API internal Investing |
| **Model Data** | `dataclasses` | Penggunaan model `EconomicEvent` baku & konversi seragam JSON |
| **Financial Data API** | `yfinance` | Menarik quotes *fast_info* dan historis pergerakan OHLCV |
| **Real-time Streaming** | `websocket-client` | Menangkap sinyal raw trade WSS milik Finnhub ke dalam Thread UI |
| **Concurrency / Threading** | `QThread` (PyQt), `ThreadPoolExecutor` | Multi-threading untuk auto-refresh GUI & Paralel Fetching Yahoo Finance |
| **Data Visualization** | `pyqtgraph` | Library graphing performant untuk rendering chart candlestick cepat |

---

## Arsitektur Aplikasi & Desain Threading

Aplikasi ini menggunakan perpaduan **PyQt5** untuk antarmuka pengguna (GUI) dan arsitektur *multithreading* (`QThread` & `ThreadPoolExecutor`) untuk memastikan responsivitas tingkat tinggi (mencegah UI *freeze*).

```text
┌─────────────────────────────────────────────────────┐
│                 desktop_app/main.py                 │
│              PyQt5 GUI (App Desktop)                │
│                 (Main UI Thread)                    │
└──────────────────────┬──────────────────────────────┘
                       │
           ┌───────────┼───────────┐
           │           │           │
 ┌─────────▼─┐   ┌─────▼─────┐   ┌─▼─────────┐
 │ Eco Cal.  │   │  Prices   │   │  Market   │
 │   Tab     │   │   Tab     │   │ Overview  │
 └─────────┬─┘   └─────┬─────┘   └─┬─────────┘
           │           │           │ memanggil QThread
           │ memicu eksekusi       │ (FullFetchWorker, FinnhubWebsocketClient)
 ┌─────────▼───────────▼───────────▼─────────┐
 │                  scrape/                  │
 │       Pipeline Scraping & Processing      │
 └─────────┬───────────┬───────────┬─────────┘
           │           │           │
 ┌─────────▼─┐   ┌─────▼─────┐   ┌─▼─────────┐
 │eco cal API│   │yfinance   │   │Websocket /│
 │(Investing/│   │Top 5      │   │Yahoo API  │
 │ FF)       │   │Concurrent │   │(finnhub)  │
 └─────────┬─┘   └─────┬─────┘   └─┬─────────┘
           │           │           │
           └──►  output/ (JSON)  ◄─┘
```

Setiap operasi I/O jaringan ditangani asinkron. Tab `Economic Calendar` memakai kombinasi orchestrator `run_pipeline`, sedangkan `Market Overview` menggabungkan `CountryMarketScraper` (berbasis `ThreadPoolExecutor`) dengan sistem rotasi proxy internal, ditambah dukungan `FinnhubWebsocketClient`.

---

## Fitur-Fitur Aplikasi Detil

### 1. Tab Economic Calendar (`calendar_tab.py`)
- **Filter Data Terpadu**: Pengguna bisa menyortir event ekonomi berdasarkan **Mata Uang** (`ALL`, `USD`, `IDR`), **Tingkat Dampak / Impact** (`High`, `Medium`, `Low`), serta jendela hari ke belakang (`Days back`).
- **Tabel Responsif & Model Terpusat**: Seluruh event direpresentasikan lewat `EconomicEvent` terstandard, memungkinkan komputasi *sentiment* (baik/buruk) otomatis jika data aktual telah terbit.
- **Inspeksi JSON Langsung**: Panel pratinjau data mentah berformat JSON dari setiap *event* ketika diklik ganda/disorot.
- **Refresh & Eksekusi Asinkron**: Tombol `Refresh Calendar` menjalankan pengambilan data kalender di latar belakang (`CalendarWorker`).
- **Export Mandiri**: Tombol `Export JSON` memungkinkan ekspor status kalender di layar secara format struktur siap baca.

### 2. Tab Prices (`prices_tab.py`)
- **Penanganan Aset Tunggal**: Menggunakan `yfinance_price_scraper.py` untuk memeriksa Quote instan (mengutamakan *fast_info* ketimbang *.info* guna lolos dari batas *Rate Limit*) dan history Price Bar komputasi OHLCV penuh.
- **Grafik Interaktif PyQtGraph**: Format waktu pada absis-x chart disulap menjadi kustomisasi ramah baca.
- **Tinjauan Historis**: Tabel iterasi riwayat nilai penutupan, volume transaksi hingga *Adjusted Close*.
- **Pembersihan Logika Interval**: Secara pintar menolak kombinasi periode interval ekstrem, contoh: komputasi timeframe 1 menit untuk jangkauan tahunan akan diturunkan jadi 5 hari (`5d`).

### 3. Tab Market Overview (`market_tab.py`)
Tab fitur lanjut untuk pengamatan konstelasi makro.
- **Country Blueprint**: Menyokong koleksi struktur terdaftar (US, ID, GB, CN, SG dll) yang diset oleh konstanta `COUNTRY_TEMPLATES` di file *country market*.
- **Auto-Refresh Exponential Cooldown**: Menangani respons penolakan API kode `HTTP 429: Too Many Requests` dari infrastruktur Yahoo dengan cerdas mengundur jeda pemanggilan.
- **Real-Time Websocket & Proxy Management**: Integrasi ganda. Socket Finnhub mentransmisi harga _intra-second_, sedangkan rotasi `Round-Robin Proxy Pool` menyebarkan laju *throttle limit* I/O HTTP pada yfinance ke server berbeda.

---

## Metodologi Scraping

Aplikasi mendapatkan data melalui kombinasi pola agresif dan sopan teknis:

1. **ForexFactory API (`forexfactory_scraper.py`)**: 
   Menargetkan JSON feed terstruktur (`ff_calendar_thisweek.json`) untuk langsung mensintesis acara perekonomian AS (Mata Uang `USD` murni, dipetakan hingga zona Region benua).
   
2. **Investing.com AJAX API (`investing_scraper.py`)**:
   Lolos dari blokade Web Scrape dengan cara mendaftarkan diri secara `GET` *Session* (menyerap `cookies` dan `user-agent` otentik) mendahului injeksi internal `POST` berdasar filter negara 5 (US) dan 48 (IDR). Script mendukung *Pagination* mutakhir.

3. **Retries dan Robust Requests (`helpers.py`)**:
   Pengiriman diwadahi paket *Session* `urllib3.util.retry.Retry`. Ia bersabar mengulang paket bila peladen membanting *HTTP code* semisal 502/504 (timeout) sembari menjamin pelambatan pengingatan *delay* paksa sebelum setiap `request`.
   
4. **Yahoo Finance Library + Country Scraper**:
   Data terpadu diambil via `yfinance`. `CountryMarketScraper` berfungsi mem-pool kueri ke dalam *threads paralell* bersama sebuah instansiasi `TTL Cached`. Ini melenyapkan lonjakan spam apabila pengguna nekat mengklik tombol refresh secepat munggkin.

5. **Finnhub Websocket Client (`finnhub_websocket.py`)**:
   Implementasi koneksi WebSocket `wss://ws.finnhub.io` dikapsulasi menjadi modul latar `QThread`. Memasok balikan *Trade Price* asinkron tanpa memonopoli komputasi CPU GUI utama.

---

## Datasets Output

Proses scraping akan menghasilkan beberapa variasi output file secara otomatis di folder `output/`:

| Nama File | Keterangan |
|---|---|
| `economic_calendar_combined.json` | Penggabungan + deduplikasi seluruh *event* kalender ekonomi. |
| `economic_calendar_usd.json` | Khusus *event* menyangkut nilai tukar USD. |
| `economic_calendar_idr.json` | Khusus *event* menyangkut nilai tukar IDR. |
| `forexfactory_usd.json` | Hasil mentahan bersumber dari ForexFactory. |
| `investing_idr.json` | Hasil mentahan spesifik untuk Indonesia bersumber dari Investing.com. |
| `pipeline_summary.json` | Rekapitulasi meta dari hasil scraping (jumlah gagal, waktu unduh, dll). |

---

## Cara Instalasi dan Menjalankan

### Prasyarat Asar
- Python 3.8 atau lebih baru.
- Aplikasi menggunakan framework antarmuka `PyQt5`, jadi tak memerlukan dependensi `tkinter` bawaan sistem operasi.

### 1. Ekstraksi Proyek dan Pengaturan Virtual Environment
Disarankan memakai *Virtual Environment* demi menjaga dependensi sistem utama.

**Linux / macOS:**
```bash
cd demo1/scrape
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Paket pip pendukung UI telah tercakup: PyQt5, pyqtgraph
```

**Windows (PowerShell):**
```powershell
cd demo1\scrape
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Memulai Program / Entry Point
Sesudah seluruh pustaka Python terpasang, berpindahlah ke folder `desktop_app`, dan jalankan program utamanya:

**Linux / macOS:**
```bash
cd ../desktop_app
python main.py
```

**Windows:**
```powershell
cd ..\desktop_app
python main.py
```

3. **Pengoperasian Desktop App**
1. Setelah GUI termuat, Anda disajikan dengan *header* di atas yang berisikan referensi Jam UTC terukur.
2. Form **Economic Calendar**: Tentukan opsi (cth: Currency `IDR`) lalu tekan `Refresh Calendar` untuk mengunduh event. Tabel bisa Anda klik untuk menampilkan raw JSON.
3. Form **Prices**: Tentukan `IHSG`, Interpal `1wk`, dan klik `Refresh Prices` untuk mengisi kanvas grafik.
4. Form **Market Overview**: Ganti mode target negara `Indonesia`. Klik `Fetch All`. Biarkan skrip mengakuisisi profil quote puluhan nama aset populer saat itu. Aktifkan *checkbox* "Auto-Refresh quotes" untuk simulasi detak pasar.

---

## Troubleshooting Tambahan
- **Blank Window / PyQt5 Error pada Linux (Wayland/X11)**: Jika antarmuka gagal *render* akibat limitasi sesi Wayland pada distromu, operasikan via xcb plugin dengan format inisiasi `QT_QPA_PLATFORM=xcb python main.py`.
- **Yahoo Rate Limit (429 HTTP Code)**: Jika tab _Market Overview_ terlalu membebani ping-pong server pada *auto-refresh*, maka indikator status di pojok UI akan melapor status "Exponential Cooldown". Anda dapat memasukkan baris Proxy aktif (*HTTP Proxy*) pada menu `Proxies...` untuk membantu memperpanjang rentang napas laju jaringan.
- **WebSocket Finnhub Tak Muncul (Error/Closed)**: Status bar bertuliskan **WSS: Error** menandakan Anda perlu verifikasi koneksi internet berkesinambungan atau meluruskan API otentikasi kunci Finnhub pada Input terkait. Pastikan kuncinya *valid*.
