import json
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, List, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QMessageBox, QFileDialog, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor
import pyqtgraph as pg

from scrape.scrapers.country_market_scraper import (
    CountryMarketScraper,
    COUNTRY_TEMPLATES,
    get_country_display_list,
    parse_country_code,
)
from desktop_app.ui.utils import utc_now_rfc3339, pretty_json, format_datetime, format_price


INTERVALS = ["1m", "5m", "15m", "30m", "1h", "1d", "5d", "1wk", "1mo"]
PERIODS = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]
AUTO_REFRESH_OPTIONS = [("30s", 30000), ("1m", 60000), ("2m", 120000), ("5m", 300000)]


class QuotesWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, scraper: CountryMarketScraper, country_code: str):
        super().__init__()
        self.scraper = scraper
        self.country_code = country_code

    def run(self):
        try:
            quotes = self.scraper.fetch_all_quotes(self.country_code)
            result = {}
            for label, q in quotes.items():
                if q:
                    result[label] = asdict(q)
                else:
                    result[label] = None
            self.finished.emit(result)
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                self.error.emit("RATE_LIMIT")
            else:
                self.error.emit(str(e))


class HistoryWorker(QThread):
    finished = pyqtSignal(str, list)
    error = pyqtSignal(str)

    def __init__(self, scraper: CountryMarketScraper, label: str, symbol: str, interval: str, period: str):
        super().__init__()
        self.scraper = scraper
        self.label = label
        self.symbol = symbol
        self.interval = interval
        self.period = period

    def run(self):
        try:
            bars = self.scraper.fetch_history(self.symbol, self.label, self.interval, self.period)
            bar_dicts = [asdict(b) for b in bars] if bars else []
            self.finished.emit(self.label, bar_dicts)
        except Exception as e:
            self.error.emit(str(e))


class MarketTab(QWidget):
    def __init__(self):
        super().__init__()
        self._scraper = CountryMarketScraper()
        self._quotes: Dict[str, Any] = {}
        self._histories: Dict[str, List[Dict]] = {}
        self._instruments: List[tuple] = []
        self._cooldown_ms = 120000
        self._cooldown_active = False
        self._init_ui()
        self._load_country("US")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        controls = QHBoxLayout()

        controls.addWidget(QLabel("Country:"))
        self.country_cb = QComboBox()
        self.country_cb.addItems(get_country_display_list())
        self.country_cb.currentTextChanged.connect(self._on_country_change)
        controls.addWidget(self.country_cb)

        controls.addWidget(QLabel("Chart:"))
        self.chart_cb = QComboBox()
        self.chart_cb.currentTextChanged.connect(self._on_chart_change)
        controls.addWidget(self.chart_cb)

        controls.addWidget(QLabel("Interval:"))
        self.interval_cb = QComboBox()
        self.interval_cb.addItems(INTERVALS)
        self.interval_cb.setCurrentText("1d")
        controls.addWidget(self.interval_cb)

        controls.addWidget(QLabel("Period:"))
        self.period_cb = QComboBox()
        self.period_cb.addItems(PERIODS)
        self.period_cb.setCurrentText("3mo")
        controls.addWidget(self.period_cb)

        controls.addStretch()

        self.refresh_btn = QPushButton("Fetch Quotes")
        self.refresh_btn.clicked.connect(self._fetch_quotes)
        controls.addWidget(self.refresh_btn)

        self.export_btn = QPushButton("Export JSON")
        self.export_btn.clicked.connect(self._export)
        controls.addWidget(self.export_btn)

        layout.addLayout(controls)

        auto_layout = QHBoxLayout()
        self.auto_cb = QCheckBox("Auto-Refresh")
        self.auto_cb.stateChanged.connect(self._on_auto_toggle)
        auto_layout.addWidget(self.auto_cb)

        auto_layout.addWidget(QLabel("Every:"))
        self.auto_interval_cb = QComboBox()
        self.auto_interval_cb.addItems([opt[0] for opt in AUTO_REFRESH_OPTIONS])
        self.auto_interval_cb.currentTextChanged.connect(self._on_auto_interval_change)
        auto_layout.addWidget(self.auto_interval_cb)

        self.next_lbl = QLabel("—")
        self.next_lbl.setStyleSheet("color: #a6adc8;")
        auto_layout.addWidget(QLabel("Next:"))
        auto_layout.addWidget(self.next_lbl)

        auto_layout.addStretch()
        layout.addLayout(auto_layout)

        self.status_lbl = QLabel("Select a country and click Fetch Quotes.")
        self.status_lbl.setStyleSheet("color: #a6adc8; padding: 4px;")
        layout.addWidget(self.status_lbl)

        splitter = QSplitter(Qt.Vertical)

        top_split = QSplitter(Qt.Horizontal)

        pg.setConfigOption("background", "#1e1e2e")
        pg.setConfigOption("foreground", "#cdd6f4")
        self.chart = pg.PlotWidget()
        self.chart.setLabel("left", "Close")
        self.chart.showGrid(x=True, y=True, alpha=0.3)
        top_split.addWidget(self.chart)

        self.table = QTableWidget()
        cols = ["Name", "Symbol", "Last", "Change", "Chg %", "Currency"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_row_select)
        self.table.cellDoubleClicked.connect(self._on_row_double_click)
        top_split.addWidget(self.table)
        top_split.setSizes([600, 400])
        splitter.addWidget(top_split)

        self.hist_tv = QTableWidget()
        h_cols = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
        self.hist_tv.setColumnCount(len(h_cols))
        self.hist_tv.setHorizontalHeaderLabels(h_cols)
        self.hist_tv.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.hist_tv.setEditTriggers(QTableWidget.NoEditTriggers)
        splitter.addWidget(self.hist_tv)

        json_container = QWidget()
        json_layout = QVBoxLayout(json_container)
        json_layout.setContentsMargins(0, 4, 0, 0)
        json_layout.addWidget(QLabel("Quote JSON:"))
        self.json_text = QTextEdit()
        self.json_text.setReadOnly(True)
        self.json_text.setStyleSheet("font-family: Consolas, monospace; background-color: #1e1e2e; color: #cdd6f4;")
        json_layout.addWidget(self.json_text)
        splitter.addWidget(json_container)
        splitter.setSizes([400, 200, 150])

        layout.addWidget(splitter)

        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._auto_refresh)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._update_countdown)
        self.countdown_timer.start(1000)
        self._next_refresh_ms = 0

    def _load_country(self, code: str):
        self._instruments = self._scraper.get_instruments(code)
        self._quotes = {}
        self._histories = {}

        self.chart_cb.clear()
        labels = [lbl for lbl, _, _ in self._instruments]
        if labels:
            self.chart_cb.addItems(labels)
            self.chart_cb.setCurrentIndex(0)

        self.table.setRowCount(len(self._instruments))
        for i, (label, symbol, itype) in enumerate(self._instruments):
            self.table.setItem(i, 0, QTableWidgetItem(label))
            self.table.setItem(i, 1, QTableWidgetItem(symbol))
            for col in range(2, 6):
                self.table.setItem(i, col, QTableWidgetItem("..."))

        self.chart.clear()
        self.hist_tv.setRowCount(0)
        self.json_text.clear()

    def _on_country_change(self, display: str):
        code = parse_country_code(display)
        self._load_country(code)
        if self.auto_cb.isChecked():
            self._schedule_auto()

    def _on_chart_change(self, label: str):
        if not label:
            return
        if label in self._histories and self._histories[label]:
            self._update_chart(label, self._histories[label])
        else:
            self._fetch_history(label)

    def _on_row_select(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        if row < len(self._instruments):
            label = self._instruments[row][0]
            q = self._quotes.get(label)
            if q:
                self.json_text.setPlainText(pretty_json(q))

    def _on_row_double_click(self, row: int, _col: int):
        if row < len(self._instruments):
            label = self._instruments[row][0]
            self.chart_cb.setCurrentText(label)

    def _fetch_quotes(self):
        code = parse_country_code(self.country_cb.currentText())
        self.refresh_btn.setEnabled(False)
        self.status_lbl.setText(f"Fetching quotes for {code}...")

        self._worker = QuotesWorker(self._scraper, code)
        self._worker.finished.connect(self._on_quotes_done)
        self._worker.error.connect(self._on_quotes_error)
        self._worker.start()

    def _fetch_history(self, label: str):
        sym = next((s for lbl, s, _ in self._instruments if lbl == label), None)
        if not sym:
            return
        interval = self.interval_cb.currentText()
        period = self.period_cb.currentText()
        self.status_lbl.setText(f"Fetching {label} history...")

        self._hist_worker = HistoryWorker(self._scraper, label, sym, interval, period)
        self._hist_worker.finished.connect(self._on_history_done)
        self._hist_worker.error.connect(self._on_history_error)
        self._hist_worker.start()

    def _on_quotes_done(self, quotes: Dict):
        self.refresh_btn.setEnabled(True)
        self._quotes = quotes
        self._update_table(quotes)

        ok_count = sum(1 for v in quotes.values() if v)
        self.status_lbl.setText(f"Loaded {ok_count}/{len(quotes)} quotes")

    def _on_quotes_error(self, err: str):
        self.refresh_btn.setEnabled(True)
        if err == "RATE_LIMIT":
            mins = self._cooldown_ms // 60000
            self.status_lbl.setText(f"Rate limited! Cooldown: {mins}m")
            self._cooldown_active = True
            self.auto_timer.stop()
            self._next_refresh_ms = self._cooldown_ms
        else:
            self.status_lbl.setText(f"Error: {err}")
            QMessageBox.critical(self, "Error", err)

    def _on_history_done(self, label: str, bars: List[Dict]):
        self._histories[label] = bars
        self._update_chart(label, bars)
        self.status_lbl.setText(f"{label}: {len(bars)} bars")

    def _on_history_error(self, err: str):
        self.status_lbl.setText(f"History error: {err}")

    def _update_table(self, quotes: Dict):
        for i, (label, symbol, itype) in enumerate(self._instruments):
            q = quotes.get(label)
            if not q:
                for col in range(2, 6):
                    self.table.setItem(i, col, QTableWidgetItem("—"))
                continue

            last = q.get("last_price")
            chg = q.get("change")
            chg_pct = q.get("change_percent")
            cur = q.get("currency", "")

            last_s = format_price(last)
            chg_s = f"{chg:+.4g}" if chg is not None else "—"
            pct_s = f"{chg_pct:+.2f}%" if chg_pct is not None else "—"

            for col, text in [(2, last_s), (3, chg_s), (4, pct_s), (5, cur or "")]:
                item = QTableWidgetItem(text)
                if col in (2, 3, 4) and chg is not None:
                    if chg > 0:
                        item.setForeground(QColor("#a6e3a1"))
                    elif chg < 0:
                        item.setForeground(QColor("#f38ba8"))
                self.table.setItem(i, col, item)

    def _update_chart(self, label: str, bars: List[Dict]):
        show = bars[-300:] if len(bars) > 300 else bars
        self.hist_tv.setRowCount(len(show))

        x_data, y_data = [], []
        for i, r in enumerate(show):
            dt = str(r.get("datetime_utc", ""))
            self.hist_tv.setItem(i, 0, QTableWidgetItem(format_datetime(dt)))
            self.hist_tv.setItem(i, 1, QTableWidgetItem(str(r.get("open", "") or "")))
            self.hist_tv.setItem(i, 2, QTableWidgetItem(str(r.get("high", "") or "")))
            self.hist_tv.setItem(i, 3, QTableWidgetItem(str(r.get("low", "") or "")))
            self.hist_tv.setItem(i, 4, QTableWidgetItem(str(r.get("close", "") or "")))
            self.hist_tv.setItem(i, 5, QTableWidgetItem(str(r.get("volume", "") or "")))

            if dt and r.get("close") is not None:
                try:
                    dt_s = dt.replace("Z", "+00:00")
                    dt_obj = datetime.fromisoformat(dt_s)
                    if dt_obj.tzinfo is None:
                        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
                    x_data.append(dt_obj.timestamp())
                    y_data.append(float(r.get("close")))
                except Exception:
                    pass

        self.chart.clear()
        if x_data and y_data:
            self.chart.plot(x_data, y_data, pen=pg.mkPen("#89b4fa", width=2))
            self.chart.setTitle(f"{label} Price History")

            last_dot = pg.ScatterPlotItem(
                x=[x_data[-1]], y=[y_data[-1]],
                size=10, brush=pg.mkBrush("#f9e2af")
            )
            self.chart.addItem(last_dot)

    def _on_auto_toggle(self, state: int):
        if state == Qt.Checked:
            self._schedule_auto()
        else:
            self.auto_timer.stop()
            self._next_refresh_ms = 0
            self.next_lbl.setText("—")

    def _on_auto_interval_change(self, text: str):
        if self.auto_cb.isChecked():
            self._schedule_auto()

    def _schedule_auto(self):
        for label, ms in AUTO_REFRESH_OPTIONS:
            if label == self.auto_interval_cb.currentText():
                self._next_refresh_ms = ms
                self.auto_timer.start(ms)
                return

    def _update_countdown(self):
        if not self.auto_cb.isChecked() or self._next_refresh_ms <= 0:
            return
        self._next_refresh_ms -= 1000
        if self._next_refresh_ms <= 0:
            if self._cooldown_active:
                self._cooldown_active = False
                self._schedule_auto()
                self.status_lbl.setText("Cooldown over. Resuming auto-refresh.")
            else:
                self.next_lbl.setText("Fetching...")
        else:
            s = self._next_refresh_ms // 1000
            prefix = "COOLDOWN " if self._cooldown_active else ""
            self.next_lbl.setText(f"{prefix}{s}s")

    def _auto_refresh(self):
        if self._cooldown_active:
            return
        self._fetch_quotes()

    def _export(self):
        if not self._quotes:
            QMessageBox.information(self, "Export", "No data loaded.")
            return
        code = parse_country_code(self.country_cb.currentText())
        payload = {
            "exported_at_utc": utc_now_rfc3339(),
            "country_code": code,
            "quotes": self._quotes,
            "histories": self._histories,
        }
        path, _ = QFileDialog.getSaveFileName(self, "Export Market Data", f"{code}_market.json", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Export", f"Saved:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
