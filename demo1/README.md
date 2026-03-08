# PBL Desktop App (Economic Calendar & Prices)

Aplikasi desktop berbasis **Python (Tkinter)** yang terintegrasi dengan pipeline data scraping untuk memantau **Kalender Ekonomi** (bersumber dari ForexFactory & Investing.com) serta pergerakan **Harga Instrumen Finansial** (bersumber dari Yahoo Finance). Aplikasi ini mencakup pencatatan data ke dalam format JSON/CSV dan visualisasi data secara langsung melalui antarmuka grafis.

---

## Tampilan Aplikasi

*(Tambahkan screenshot aplikasi di sini jika ada)*
- **Tab Economic Calendar**: Menampilkan tabel event ekonomi beserta detail JSON saat baris (row) diklik.
- **Tab Prices**: Menampilkan grafik harga (line close chart), tabel historis OHLCV (Open, High, Low, Close, Volume), dan snapshot quote JSON.

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

## Arsitektur Aplikasi

```text
┌─────────────────────────────────────────────────────┐
│                 desktop_app/main.py                 │
│              Tkinter GUI (App Desktop)              │
└──────────────────────┬──────────────────────────────┘
                       │
           ┌───────────┴───────────┐
           │                       │
 ┌─────────▼─────────┐   ┌─────────▼─────────┐
 │ Tab: Eco Calendar │   │    Tab: Prices    │
 └─────────┬─────────┘   └─────────┬─────────┘
           │                       │ memanggil ulang data
           │ memicu eksekusi       │
 ┌─────────▼───────────────────────▼─────────┐
 │                  scrape/                  │
 │       Pipeline Scraping & Processing      │
 └─────────┬───────────────────────┬─────────┘
           │                       │
 ┌─────────▼─────────┐   ┌─────────▼─────────┐
 │  Kalender Ekonomi │   │   Harga Finansial │
 │ (ForexFactory,    │   │ (Yahoo Finance)   │
 │  Investing.com)   │   │                   │
 └─────────┬─────────┘   └─────────┬─────────┘
           │                       │
           └──►  output/ (JSON)  ◄─┘
```

---

## Fitur-Fitur Aplikasi

### 1. Tab Economic Calendar
- **Filter Data Terpadu**: Pengguna bisa menyortir event ekonomi berdasarkan **Mata Uang** (`ALL`, `USD`, `IDR`), **Tingkat Dampak / Impact** (`High`, `Medium`, `Low`), serta jendela waktu (jumlah hari ke depan/belakang).
- **Refresh & Eksekusi Pipeline**: Tombol `Refresh Calendar` menjalankan engine kalender di latar belakang lalu memperbarui data di tabel.
- **Export Mandiri**: Tombol `Export JSON` memungkinkan pengguna menyimpan event yang tengah tampil ke file JSON pilihan secara manual.
- **Auto-Save Output**: Selama refreshing, data pipeline secara otomatis disimpan ke direktori `scrape/output/` agar bisa diakses untuk olah data mandiri (misal: `economic_calendar_usd.json`).

### 2. Tab Prices
- **Pemilihan Instrumen**: Memantau aset yang ditetapkan pengguna seperti `USDIDR` (`IDR=X`), `IHSG` (`^JKSE`), dan `BBCA` (`BBCA.JK`).
- **Kostumisasi Interval & Rentang Waktu**: Dapat menarik histori dalam rentang seperti `1d`, `3mo`, dll. Mendukung *start/end date* spesifik.
- **Visualisasi Dinamis**: Menghasilkan matplotlib chart berisikan harga grafik *Close* langsung di dalam jendela Tkinter.
- **Tinjauan Historis**: Daftar riwayat nilai OHLCV (Open, High, Low, Close, Volume) ditampilkan dalam bentuk tabel.
- **Export Data Harga**: Tombol `Export JSON` untuk mengeluarkan snapshot historis dan kutipan harga yang sedang diamati.

---

## Metodologi Scraping

Aplikasi mendapatkan data melalui kombinasi beberapa pendekatan teknis:

1. **ForexFactory API (`forexfactory_scraper.py`)**: 
   Menargetkan JSON API resmi (`nfs.faireconomy.media`) untuk langsung mensintesis acara perekonomian Amerika Serikat (USD).
   
2. **Investing.com AJAX API (`investing_scraper.py`)**:
   Melakukan permintaan HTTP awal dengan parsing BeautifulSoup untuk mendapatkan session/cookie, kemudian meminta data AJAX dengan menggunakan parameter negara target (`IDR` / `USD`). Penanganan blokir dihindari dengan merotasi `User-Agent` serta menangani rate limiting melalui *exponential backoff*.

3. **Yahoo Finance Library (`yfinance_price_scraper.py`)**:
   Data historis harga saham/foreks diambil menggunakan lib `yfinance` yang menyederhanakan call API Yahoo secara efisien dan menghasilkan wujud DataFrame `pandas`.

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
- Dukungan instalasi paket `tkinter` (apabila pengguna Linux, mungkin membutuhkan eksekusi `sudo apt-get install python3-tk`).

### 1. Ekstraksi Proyek dan Pengaturan Virtual Environment
Disarankan memakai *Virtual Environment* demi menjaga dependensi sistem utama.

**Linux / macOS:**
```bash
cd demo1/scrape
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install matplotlib
```

**Windows (PowerShell):**
```powershell
cd demo1\scrape
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install matplotlib
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

### 3. Pengoperasian Desktop App
1. Sesudah aplikasi terbuka, pada form **Economic Calendar**, mulailah dengan menentukan filter (cth: Currency: `USD`, Impact: `High`) lalu klik **Refresh Calendar**.
2. Berpindahlah ke bagian **Prices**, ubah Instrumen (cth: `BBCA`), atur interpal (*Interval*) ke `1d`, dan *Period* ke `3mo`, kemudian tekan **Refresh Prices** untuk menampilkan grafis *chart* `matplotlib`.

---

## Troubleshooting Tambahan
- Jika GUI **batal/gagal muncul**, kemungkinan besar engine library Tk/Tcl tidak dikenali sistem, segera pertimbangkan untuk melakukan penambahan pada level package manajer OS (`python3-tk` di Ubuntu/Debian).
- Apabila terjadi kelumpuhan pada pengambilan saham (`yfinance error`), dianjurkan memperbarui input parameter `interval`/`period` lalu dicoba kembali beberapa detik kemudian. (Yahoo Finance membatasi secara dinamis rate *request*-nya).
- Masalah penarikan data dari Investing.com yang gagal serentak (Error HTTP 429 - *Too Many Requests*) bisa disiasati dengan mengurangi beban klik ganda secara cepat pada form refresh di UI.
