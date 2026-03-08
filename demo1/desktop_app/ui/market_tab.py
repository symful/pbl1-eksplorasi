import json
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QCheckBox, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QTextEdit, QMessageBox,
    QFileDialog, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor
import pyqtgraph as pg

from scrape.scrapers.country_market_scraper import CountryMarketScraper, get_country_display_list, parse_country_code, format_price
from desktop_app.ui.utils import _utc_now_rfc3339, _pretty_json
from desktop_app.ui.prices_tab import TimeAxisItem

# Interval and period options
_AUTO_REFRESH_OPTIONS = [
    ("30 s", 30_000),
    ("1 min", 60_000),
    ("2 min", 120_000),
    ("5 min", 300_000),
]
_INTERVAL_OPTIONS = ["1m", "5m", "15m", "30m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]
_PERIOD_OPTIONS = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]

class FullFetchWorker(QThread):
    finished = pyqtSignal(str, dict, str, list, str, str) # code, quotes_dict, hist_label, history_dicts, interval, period
    error = pyqtSignal(str)

    def __init__(self, scraper, code, instruments, hist_label, interval, period):
        super().__init__()
        self.scraper = scraper
        self.code = code
        self.instruments = instruments
        self.hist_label = hist_label
        self.interval = interval
        self.period = period

    def run(self):
        try:
            # 1) Fetch quotes
            quotes_raw = self.scraper.fetch_all_quotes(self.code)
            
            # 2) Fetch history for selected label
            history_bars = []
            if self.hist_label:
                sym = next((s for l, s, _ in self.instruments if l == self.hist_label), None)
                if sym:
                    history_bars = self.scraper.fetch_history(
                        symbol=sym,
                        ticker_label=self.hist_label,
                        interval=self.interval,
                        period=self.period
                    )
            
            # Serialize
            quotes_dict = {}
            for lbl, q in quotes_raw.items():
                if q:
                    quotes_dict[lbl] = {
                        "ticker": q.ticker, "symbol": q.symbol, "fetched_at_utc": q.fetched_at_utc,
                        "currency": q.currency, "exchange": q.exchange, "quote_type": q.quote_type,
                        "last_price": q.last_price, "previous_close": q.previous_close,
                        "open": q.open, "day_high": q.day_high, "day_low": q.day_low,
                        "change": q.change, "change_percent": q.change_percent, "market_time_utc": q.market_time_utc
                    }
                else:
                    quotes_dict[lbl] = None
                    
            history_dicts = [asdict(b) for b in history_bars]
            
            self.finished.emit(self.code, quotes_dict, self.hist_label, history_dicts, self.interval, self.period)
        except Exception as e:
            self.error.emit(str(e))


class QuotesOnlyWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, scraper, code):
        super().__init__()
        self.scraper = scraper
        self.code = code

    def run(self):
        try:
            quotes_raw = self.scraper.fetch_all_quotes(self.code)
            quotes_dict = {}
            for lbl, q in quotes_raw.items():
                if q:
                    quotes_dict[lbl] = {
                        "ticker": q.ticker, "symbol": q.symbol, "fetched_at_utc": q.fetched_at_utc,
                        "currency": q.currency, "exchange": q.exchange, "quote_type": q.quote_type,
                        "last_price": q.last_price, "previous_close": q.previous_close,
                        "open": q.open, "day_high": q.day_high, "day_low": q.day_low,
                        "change": q.change, "change_percent": q.change_percent, "market_time_utc": q.market_time_utc
                    }
                else:
                    quotes_dict[lbl] = None
            self.finished.emit(quotes_dict)
        except Exception as e:
            self.error.emit(str(e))


class HistoryWorker(QThread):
    finished = pyqtSignal(str, str, list, str, str) # label, sym, dicts, interval, period
    
    def __init__(self, scraper, label, sym, interval, period):
        super().__init__()
        self.scraper = scraper
        self.label = label
        self.sym = sym
        self.interval = interval
        self.period = period
        
    def run(self):
        bars = self.scraper.fetch_history(self.sym, self.label, self.interval, self.period)
        dicts = [asdict(b) for b in bars]
        self.finished.emit(self.label, self.sym, dicts, self.interval, self.period)


class MarketOverviewTab(QWidget):
    def __init__(self):
        super().__init__()
        self._scraper = CountryMarketScraper()
        self._country_display = get_country_display_list()
        
        self._instruments = []
        self._quotes = {}
        self._histories = {}
        self._selected_label = None
        self._fetch_inflight = False
        self._quote_only_inflight = False
        
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._auto_refresh_tick)
        self.next_refresh_ms = 0
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._update_countdown)
        self.countdown_timer.start(1000)
        
        self._init_ui()
        self._on_country_change() # Populate initial instruments

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Top Controls ---
        top_frame = QWidget()
        top_layout = QVBoxLayout(top_frame)
        
        # Row 1
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Country:"))
        self.country_cb = QComboBox()
        self.country_cb.addItems(self._country_display)
        self.country_cb.currentTextChanged.connect(self._on_country_change)
        r1.addWidget(self.country_cb)
        
        r1.addWidget(QLabel("Chart:"))
        self.chart_inst_cb = QComboBox()
        self.chart_inst_cb.currentTextChanged.connect(self._on_chart_inst_change)
        r1.addWidget(self.chart_inst_cb)
        
        r1.addWidget(QLabel("Interval:"))
        self.interval_cb = QComboBox()
        self.interval_cb.addItems(_INTERVAL_OPTIONS)
        self.interval_cb.setCurrentText("1d")
        r1.addWidget(self.interval_cb)
        
        r1.addWidget(QLabel("Period:"))
        self.period_cb = QComboBox()
        self.period_cb.addItems(_PERIOD_OPTIONS)
        self.period_cb.setCurrentText("3mo")
        r1.addWidget(self.period_cb)
        
        r1.addStretch()
        
        self.fetch_btn = QPushButton("Fetch All")
        self.fetch_btn.clicked.connect(self._fetch_all_async)
        r1.addWidget(self.fetch_btn)
        
        self.export_btn = QPushButton("Export JSON...")
        self.export_btn.clicked.connect(self._export_json)
        r1.addWidget(self.export_btn)
        
        top_layout.addLayout(r1)
        
        # Row 2 (Auto Refresh)
        r2 = QHBoxLayout()
        self.ar_cb = QCheckBox("Auto-Refresh quotes")
        self.ar_cb.stateChanged.connect(self._on_auto_refresh_toggle)
        r2.addWidget(self.ar_cb)
        
        r2.addWidget(QLabel("  Every:"))
        self.ar_interval_cb = QComboBox()
        self.ar_interval_cb.addItems([label for label, _ in _AUTO_REFRESH_OPTIONS])
        self.ar_interval_cb.currentTextChanged.connect(self._on_ar_interval_change)
        r2.addWidget(self.ar_interval_cb)
        
        r2.addWidget(QLabel("  Next:"))
        self.next_lbl = QLabel("—")
        self.next_lbl.setStyleSheet("color: #a6adc8; font-weight: bold;")
        r2.addWidget(self.next_lbl)
        
        r2.addWidget(QLabel("   (Quotes only | Full fetch updates history)"))
        r2.addStretch()
        top_layout.addLayout(r2)
        
        self.status = QLabel("Select a country and click Fetch All.")
        self.status.setStyleSheet("color: #a6adc8;")
        top_layout.addWidget(self.status)
        
        layout.addWidget(top_frame)
        
        # --- Splitters ---
        main_splitter = QSplitter(Qt.Vertical)
        
        # Top Splitter (Chart | Quotes Table)
        top_spl = QSplitter(Qt.Horizontal)
        
        # Chart
        pg.setConfigOption('background', '#1e1e2e')
        pg.setConfigOption('foreground', '#cdd6f4')
        self.chart = pg.PlotWidget(axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self.chart.setLabel('left', 'Close')
        self.chart.showGrid(x=True, y=True, alpha=0.3)
        top_spl.addWidget(self.chart)
        
        # Quotes Table
        self.quote_tv = QTableWidget()
        q_cols = ["#", "Name", "Symbol", "Type", "Last", "Change", "Chg %", "Cur"]
        self.quote_tv.setColumnCount(len(q_cols))
        self.quote_tv.setHorizontalHeaderLabels(q_cols)
        self.quote_tv.setSelectionBehavior(QTableWidget.SelectRows)
        self.quote_tv.setEditTriggers(QTableWidget.NoEditTriggers)
        self.quote_tv.itemSelectionChanged.connect(self._on_quote_row_selected)
        self.quote_tv.cellDoubleClicked.connect(self._on_quote_row_double_click)
        top_spl.addWidget(self.quote_tv)
        
        top_spl.setSizes([600, 400])
        main_splitter.addWidget(top_spl)
        
        # Middle: History Table
        self.hist_tv = QTableWidget()
        h_cols = ["Datetime (UTC)", "Open", "High", "Low", "Close", "Volume"]
        self.hist_tv.setColumnCount(len(h_cols))
        self.hist_tv.setHorizontalHeaderLabels(h_cols)
        self.hist_tv.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.hist_tv.setSelectionBehavior(QTableWidget.SelectRows)
        self.hist_tv.setEditTriggers(QTableWidget.NoEditTriggers)
        main_splitter.addWidget(self.hist_tv)
        
        # Bottom: JSON View
        json_container = QWidget()
        json_layout = QVBoxLayout(json_container)
        json_layout.setContentsMargins(0, 0, 0, 0)
        
        j_hdr = QHBoxLayout()
        j_hdr.addWidget(QLabel("Quote JSON (selected):"))
        self.show_json_cb = QCheckBox("Show")
        self.show_json_cb.setChecked(True)
        self.show_json_cb.stateChanged.connect(self._toggle_json)
        j_hdr.addWidget(self.show_json_cb)
        j_hdr.addStretch()
        json_layout.addLayout(j_hdr)
        
        self.json_text = QTextEdit()
        self.json_text.setReadOnly(True)
        self.json_text.setStyleSheet("font-family: Consolas, monospace; background-color: #1e1e2e;")
        json_layout.addWidget(self.json_text)
        
        main_splitter.addWidget(json_container)
        
        main_splitter.setSizes([400, 200, 150])
        layout.addWidget(main_splitter)

    # -----------------------------------------------
    # UI Interactions
    # -----------------------------------------------
    def _toggle_json(self):
        self.json_text.setVisible(self.show_json_cb.isChecked())

    def _on_country_change(self):
        code = parse_country_code(self.country_cb.currentText())
        instruments = self._scraper.get_instruments(code)
        self._instruments = instruments
        
        self.chart_inst_cb.clear()
        labels = [lbl for lbl, _, _ in instruments]
        if labels:
            self.chart_inst_cb.addItems(labels)
            self.chart_inst_cb.setCurrentIndex(0)
            self._selected_label = labels[0]
            
        self.quote_tv.setRowCount(0)
        self.hist_tv.setRowCount(0)
        self.chart.clear()
        self.json_text.clear()
        self._quotes = {}
        self._histories = {}
        
        self.quote_tv.setRowCount(len(instruments))
        for i, (label, symbol, itype) in enumerate(instruments):
            prefix = "★" if itype == "index" else ""
            self.quote_tv.setItem(i, 0, QTableWidgetItem(prefix))
            self.quote_tv.setItem(i, 1, QTableWidgetItem(label))
            self.quote_tv.setItem(i, 2, QTableWidgetItem(symbol))
            self.quote_tv.setItem(i, 3, QTableWidgetItem(itype[:3].upper()))
            for col in range(4, 8):
                self.quote_tv.setItem(i, col, QTableWidgetItem("..."))

    def _on_chart_inst_change(self, label):
        if not label: return
        self._selected_label = label
        if label in self._histories:
            self._update_chart_and_hist_table(label)
        else:
            self._fetch_history_async(label)

    def _on_quote_row_selected(self):
        sel = self.quote_tv.selectedItems()
        if not sel: return
        row = sel[0].row()
        label = self._instruments[row][0]
        q = self._quotes.get(label)
        if q:
            self.json_text.setPlainText(_pretty_json(q))

    def _on_quote_row_double_click(self, row, col):
        label = self._instruments[row][0]
        self.chart_inst_cb.setCurrentText(label)

    # -----------------------------------------------
    # Auto Refresh Logic
    # -----------------------------------------------
    def _get_ar_ms(self):
        label = self.ar_interval_cb.currentText()
        for l, ms in _AUTO_REFRESH_OPTIONS:
            if l == label: return ms
        return 60_000

    def _on_auto_refresh_toggle(self):
        if self.ar_cb.isChecked():
            self._schedule_next()
        else:
            self.auto_timer.stop()
            self.next_refresh_ms = 0
            self.next_lbl.setText("—")

    def _on_ar_interval_change(self):
        if self.ar_cb.isChecked():
            self._schedule_next()

    def _schedule_next(self):
        ms = self._get_ar_ms()
        self.auto_timer.start(ms)
        self.next_refresh_ms = ms

    def _update_countdown(self):
        if self.ar_cb.isChecked() and self.next_refresh_ms > 0:
            self.next_refresh_ms -= 1000
            if self.next_refresh_ms <= 0:
                self.next_lbl.setText("Fetching...")
            else:
                s = self.next_refresh_ms // 1000
                m = s // 60
                s = s % 60
                self.next_lbl.setText(f"{m:02d}:{s:02d}")

    def _auto_refresh_tick(self):
        if not self.ar_cb.isChecked() or not self._instruments:
            return
        if self._quote_only_inflight or self._fetch_inflight:
            self._schedule_next()
            return
            
        self._quote_only_inflight = True
        code = parse_country_code(self.country_cb.currentText())
        self.status.setText(f"Auto-refreshing quotes for {code}...")
        
        self.qr_worker = QuotesOnlyWorker(self._scraper, code)
        self.qr_worker.finished.connect(self._apply_quotes_update)
        self.qr_worker.error.connect(lambda e: self.status.setText(f"Auto-refresh error: {e}"))
        self.qr_worker.finished.connect(self._reset_qr_inflight)
        self.qr_worker.error.connect(self._reset_qr_inflight)
        self.qr_worker.start()

    def _reset_qr_inflight(self, *args):
        self._quote_only_inflight = False
        self._schedule_next()

    # -----------------------------------------------
    # Data Fetching
    # -----------------------------------------------
    def _fetch_all_async(self):
        if self._fetch_inflight: return
        code = parse_country_code(self.country_cb.currentText())
        if not code or not self._instruments: return
        
        self._fetch_inflight = True
        self.fetch_btn.setEnabled(False)
        self.status.setText(f"Fetching all quotes for {code}...")
        
        interval = self.interval_cb.currentText()
        period = self.period_cb.currentText()
        sel_label = self._selected_label
        
        self.fw_worker = FullFetchWorker(self._scraper, code, self._instruments, sel_label, interval, period)
        self.fw_worker.finished.connect(self._apply_full_fetch)
        self.fw_worker.error.connect(self._on_fetch_error)
        self.fw_worker.start()
        
    def _fetch_history_async(self, label):
        sym = next((s for l, s, _ in self._instruments if l == label), None)
        if not sym: return
        
        self.status.setText(f"Fetching history for {label}...")
        interval = self.interval_cb.currentText()
        period = self.period_cb.currentText()
        
        self.h_worker = HistoryWorker(self._scraper, label, sym, interval, period)
        self.h_worker.finished.connect(self._apply_history_update)
        self.h_worker.start()

    def _on_fetch_error(self, err):
        self._fetch_inflight = False
        self.fetch_btn.setEnabled(True)
        self.status.setText("Error.")
        QMessageBox.critical(self, "Fetch Error", err)

    # -----------------------------------------------
    # Applying Data to UI
    # -----------------------------------------------
    def _apply_full_fetch(self, code, quotes_dict, hist_label, history_dicts, interval, period):
        self._fetch_inflight = False
        self.fetch_btn.setEnabled(True)
        self._quotes = quotes_dict
        if hist_label:
            self._histories[hist_label] = history_dicts
            
        self._update_quote_table(quotes_dict)
        
        if hist_label and history_dicts:
            self._update_chart_and_hist_table(hist_label)
            
        n_ok = sum(1 for v in quotes_dict.values() if v)
        self.status.setText(f"{code}: {n_ok}/{len(quotes_dict)} quotes loaded. History for {hist_label}: {len(history_dicts)} bars.")

    def _apply_quotes_update(self, quotes_dict):
        self._quotes = quotes_dict
        self._update_quote_table(quotes_dict)
        n_ok = sum(1 for v in quotes_dict.values() if v)
        self.status.setText(f"Quotes refreshed: {n_ok}/{len(quotes_dict)} ok. Last: {_utc_now_rfc3339()}")

    def _apply_history_update(self, label, symbol, dicts, interval, period):
        self._histories[label] = dicts
        if dicts:
            self._update_chart_and_hist_table(label)
            self.status.setText(f"History for {label} ({symbol}): {len(dicts)} bars.")
        else:
            self.status.setText(f"History empty for {label}.")

    def _update_quote_table(self, quotes_dict):
        for i, (label, symbol, itype) in enumerate(self._instruments):
            q = quotes_dict.get(label)
            if not q: continue
            
            last_p = q.get("last_price")
            chg = q.get("change")
            chg_pct = q.get("change_percent")
            cur = q.get("currency") or ""
            
            last_s = format_price(last_p)
            chg_s = f"{chg:+.4g}" if chg is not None else "—"
            chg_pct_s = f"{chg_pct:+.2f}%" if chg_pct is not None else "—"
            
            for col, text in enumerate(["", label, symbol, itype[:3].upper(), last_s, chg_s, chg_pct_s, cur]):
                if col == 0:
                    text = "★" if itype == "index" else ""
                item = QTableWidgetItem(text)
                
                # Colors
                if col in [4, 5, 6]: # Prices/Change
                    if chg is not None and chg > 0: item.setForeground(QColor("#a6e3a1")) # Green
                    elif chg is not None and chg < 0: item.setForeground(QColor("#f38ba8")) # Red
                if itype == "index":
                    item.setForeground(QColor("#cba6f7")) # Mauve for index
                
                self.quote_tv.setItem(i, col, item)

    def _update_chart_and_hist_table(self, label):
        bars = self._histories.get(label) or []
        
        show = bars[-300:] if len(bars) > 300 else bars
        self.hist_tv.setRowCount(len(show))
        
        x_data, y_data = [], []
        for i, r in enumerate(show):
            dt_s = r.get("datetime_utc", "")
            self.hist_tv.setItem(i, 0, QTableWidgetItem(dt_s))
            self.hist_tv.setItem(i, 1, QTableWidgetItem(str(r.get("open", ""))))
            self.hist_tv.setItem(i, 2, QTableWidgetItem(str(r.get("high", ""))))
            self.hist_tv.setItem(i, 3, QTableWidgetItem(str(r.get("low", ""))))
            self.hist_tv.setItem(i, 4, QTableWidgetItem(str(r.get("close", ""))))
            self.hist_tv.setItem(i, 5, QTableWidgetItem(str(r.get("volume", ""))))
            
            if dt_s and r.get("close") is not None:
                try:
                    dt = datetime.fromisoformat(dt_s.replace("Z", "+00:00")).astimezone(timezone.utc)
                    x_data.append(dt.timestamp())
                    y_data.append(float(r.get("close")))
                except: pass
                
        self.chart.clear()
        if x_data and y_data:
            itype = next((t for l, _, t in self._instruments if l == label), "stock")
            sym = next((s for l, s, _ in self._instruments if l == label), label)
            
            self.chart.plot(x_data, y_data, pen=pg.mkPen('#89b4fa', width=2))
            self.chart.setTitle(f"{label} ({'Index' if itype == 'index' else 'Stock'}) - {sym}")
            
            scatter = pg.ScatterPlotItem(x=[x_data[-1]], y=[y_data[-1]], size=10, brush=pg.mkBrush('#f9e2af'))
            self.chart.addItem(scatter)

    def _export_json(self):
        if not self._quotes:
            QMessageBox.information(self, "Export", "No data loaded.")
            return
        code = parse_country_code(self.country_cb.currentText())
        payload = {
            "exported_at_utc": _utc_now_rfc3339(),
            "country_code": code,
            "quotes": self._quotes,
            "histories": self._histories
        }
        
        path, _ = QFileDialog.getSaveFileName(self, "Export market snapshot", f"{code}_market_snapshot.json", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Export", f"Saved:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
