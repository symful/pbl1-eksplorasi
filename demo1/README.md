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

## Struktur Folder

```text
demo1/
├── desktop_app/
│   └── main.py                          # Entry point aplikasi GUI (Tkinter)
│
└── scrape/
    ├── main.py                          # Orchestrator utama pemrosesan scraping
    ├── config.py                        # Konfigurasi dan konstanta scraping
    ├── requirements.txt                 # Daftar dependensi Python
    ├── .env.example                     # Template pengaturan environment variables
    │
    ├── models/
    │   └── economic_event.py            # Model dataclass untuk data EconomicEvent
    │
    ├── scrapers/
    │   ├── forexfactory_scraper.py      # Module scraping untuk ForexFactory
    │   ├── investing_scraper.py         # Module scraping untuk Investing.com
    │   └── yfinance_price_scraper.py    # Module scraping untuk harga (Yahoo Finance)
    │
    ├── utils/
    │   └── helpers.py                   # Utilitas: log, request HTTP, manipulasi waktu, dan ekspor data
    │
    └── output/                          # Folder tempat hasil output (JSON/CSV) bermuara
```

---

## Tech Stack

| Komponen | Teknologi | Keterangan |
|---|---|---|
| **Bahasa Utama** | Python | Bahasa pemrograman inti yang digunakan |
| **GUI Framework** | Tkinter | Membangun antarmuka grafis desktop terintegrasi (built-in Python) |
| **HTTP & Web Parsing** | `requests`, `beautifulsoup4`, `lxml` | Menarik dan memparsing data HTML/JSON dari portal web |
| **Financial Data API** | `yfinance`, `pandas` | Mengambil dan mengolah data harga historis dan kutipan dari Yahoo Finance |
| **Data Visualization** | `matplotlib` | Merender grafik pergerakan harga di atas kanvas Tkinter |

---

## Arsitektur Aplikasi & Desain Threading

Aplikasi ini menggunakan perpaduan **PyQt5** untuk antarmuka pengguna (GUI) dan arsitektur *multithreading* (`QThread`) untuk memastikan UI tetap responsif (tidak *freeze*) ketika proses *scraping* atau operasi *network* berjalan di latar belakang.

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
           │ memicu eksekusi       │ (FullFetchWorker, 
 ┌─────────▼───────────▼───────────▼─────────┐
 │                  scrape/                  │
 │       Pipeline Scraping & Processing      │
 └─────────┬───────────┬───────────┬─────────┘
           │           │           │
 ┌─────────▼─┐   ┌─────▼─────┐   ┌─▼─────────┐
 │eco cal API│   │yfinance   │   │Websocket /│
 │(Investing/│   │(Yahoo)    │   │Yahoo API  │
 │ FF)       │   │           │   │           │
 └─────────┬─┘   └─────┬─────┘   └─┬─────────┘
           │           │           │
           └──►  output/ (JSON)  ◄─┘
```

Setiap Tab mendelegasikan pemanggilan data ke sebuah kelas _Worker_ seperti `CalendarWorker`, `PricesWorker`, atau `FullFetchWorker` dan berkomunikasi melalui Qt *Signals/Slots* (`finished` & `error`).

---

## Fitur-Fitur Aplikasi Detil

### 1. Tab Economic Calendar (`calendar_tab.py`)
- **Filter Data Terpadu**: Pengguna bisa menyortir event ekonomi berdasarkan **Mata Uang** (`ALL`, `USD`, `IDR`), **Tingkat Dampak / Impact** (`High`, `Medium`, `Low`), serta jendela hari ke belakang (`Days back`).
- **Tabel Responsif**: Menampilkan acara ekonomi dengan kolom Tanggal, Waktu, Mata Uang, Dampak, dan Judul. Mendukung seleksi baris (row).
- **Inspeksi JSON Lagsung**: Panel pratinjau data mentah berformat JSON dari setiap *event* ketika diklik.
- **Refresh & Eksekusi Asinkron**: Tombol `Refresh Calendar` menjalankan pengambilan data kalender di latar belakang (`CalendarWorker`).
- **Export Mandiri**: Tombol `Export JSON` memungkinkan ekspor status kalender di layar ke dalam *file* JSON khusus.

### 2. Tab Prices (`prices_tab.py`)
- **Pemilihan Instrumen**: Memantau aset kustom yang ditetapkan pengguna, cth:`USDIDR`, `IHSG`, `BBCA` (dan penyesuaian interval 1m sampai 3mo, juga periode 5d sampai opsi Max tahun).
- **Grafik Interaktif QtGraph**: Merender representasi interaktif grafik pergerakan harga komplit dengan Sumbu X berformat tanggal/jam yang bisa di-zoom maupun di-pan.
- **Tinjauan Historis**: Daftar riwayat nilai OHLCV (Open, High, Low, Close, Volume).
- **Export Data Harga**: Snapshot yang tersaji termasuk *Quote* saat itu beserta seluruh rentang historis dapat di-export via dialog file `.json`.

### 3. Tab Market Overview (`market_tab.py`)
Tab fitur lanjut (Advanced) untuk memantau ratusan instrumen finansial berdasarkan direktori aset suatu negara.
- **Country Filter**: Filter aset berdasarkan `US` (Amerika) atau `ID` (Indonesia) untuk mengkurasi daftar Indeks, Obligasi, dan Saham.
- **Auto-Refresh**: Dapat dijadwalkan secara periodik (30 detik hingga 5 menit) untuk mem-fetch pembaruan _quotes_ tanpa menggangu UI. Mendukung pencegahan limit rate (Exponential Cooldown saat HTTP 429).
- **Real-Time Websocket**: Integrasi opsional pada aset Amerika dengan masukan API key `Finnhub`. Seluruh perubahan harga akan disorot pada tabel serta memperbarui instan letak titik harga terakhir grafik dalam satuan _milisecond_.
- **Proxy Management**: Mencegah pemblokiran pengikisan (_scraping blocks_) dari API eksternal dengan kapabilitas konfigurasi Custom HTTP Proxy.

---

## Metodologi Scraping

Aplikasi mendapatkan data melalui kombinasi beberapa pendekatan teknis:

1. **ForexFactory API (`forexfactory_scraper.py`)**: 
   Menargetkan JSON API resmi (`nfs.faireconomy.media`) untuk langsung mensintesis acara perekonomian Amerika Serikat (USD).
   
2. **Investing.com AJAX API (`investing_scraper.py`)**:
   Melakukan permintaan HTTP awal dengan parsing BeautifulSoup untuk mendapatkan session/cookie, kemudian meminta data AJAX dengan menggunakan parameter negara target (`IDR` / `USD`). Penanganan blokir dihindari dengan merotasi `User-Agent` serta menangani rate limiting melalui *exponential backoff*.

3. **Yahoo Finance Library + Country Scraper**:
   Data historis harga saham/foreks diambil menggunakan *library* `yfinance` dan komponen kustom (`CountryMarketScraper`) yang menyederhanakan panggilan API Yahoo Finance serta melakukan abstraksi manajemen direktori instrumen negara.

4. **Finnhub Websocket Client (`finnhub_websocket.py`)**:
   Implementasi TCP koneksi berkecepatan tinggi berbasis token otorisasi yang menerima *streaming* data transaksi market aslinya untuk menyulap performa "Real-Time".

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
