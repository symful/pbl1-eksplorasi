import json
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QMessageBox, QFileDialog, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import pyqtgraph as pg

from scrape.scrapers.yfinance_price_scraper import YahooFinancePriceScraper
from desktop_app.ui.utils import utc_now_rfc3339, pretty_json, format_datetime


INSTRUMENTS = {
    "USDIDR": ("USDIDR", "IDR=X"),
    "IHSG": ("IHSG", "^JKSE"),
    "BBCA": ("BBCA", "BBCA.JK"),
    "TLKM": ("TLKM", "TLKM.JK"),
    "ASII": ("ASII", "ASII.JK"),
}

INTERVALS = ["1m", "5m", "15m", "30m", "1h", "1d", "5d", "1wk", "1mo"]
PERIODS = ["5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]


class TimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [
            datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            for v in values
        ]


class PricesWorker(QThread):
    finished = pyqtSignal(dict, list, str, str, str)
    error = pyqtSignal(str)

    def __init__(self, instrument_key: str, interval: str, period: str):
        super().__init__()
        self.instrument_key = instrument_key
        self.interval = interval
        self.period = period
        self.scraper = YahooFinancePriceScraper()

    def run(self):
        try:
            label, symbol = INSTRUMENTS.get(self.instrument_key, (self.instrument_key, self.instrument_key))

            quote = self.scraper.fetch_quote(symbol=symbol, ticker_label=label)
            bars = self.scraper.fetch_history(
                symbol=symbol,
                ticker_label=label,
                interval=self.interval,
                period=self.period,
            )

            quote_dict = asdict(quote) if quote else {}
            bar_dicts = [asdict(b) for b in bars] if bars else []

            msg = f"Got {len(bar_dicts)} bars"
            if not bar_dicts:
                msg = "No data (rate limited or unsupported interval)"
            self.finished.emit(quote_dict, bar_dicts, label, symbol, msg)
        except Exception as e:
            self.error.emit(f"Error:\n{e}\n{traceback.format_exc()}")


class PricesTab(QWidget):
    def __init__(self):
        super().__init__()
        self._quote: Dict[str, Any] = {}
        self._bars: List[Dict[str, Any]] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        controls = QHBoxLayout()

        controls.addWidget(QLabel("Instrument:"))
        self.inst_cb = QComboBox()
        self.inst_cb.addItems(list(INSTRUMENTS.keys()))
        controls.addWidget(self.inst_cb)

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

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh)
        controls.addWidget(self.refresh_btn)

        self.export_btn = QPushButton("Export JSON")
        self.export_btn.clicked.connect(self._export)
        controls.addWidget(self.export_btn)

        layout.addLayout(controls)

        self.status_lbl = QLabel("Ready. Select instrument and click Refresh.")
        self.status_lbl.setStyleSheet("color: #a6adc8; padding: 4px;")
        layout.addWidget(self.status_lbl)

        splitter = QSplitter(Qt.Vertical)

        top_split = QSplitter(Qt.Horizontal)

        pg.setConfigOption("background", "#1e1e2e")
        pg.setConfigOption("foreground", "#cdd6f4")
        self.plot = pg.PlotWidget(axisItems={"bottom": TimeAxisItem(orientation="bottom")})
        self.plot.setLabel("left", "Close Price")
        self.plot.setLabel("bottom", "Time (UTC)")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        top_split.addWidget(self.plot)

        self.table = QTableWidget()
        cols = ["Datetime (UTC)", "Open", "High", "Low", "Close", "Volume"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        top_split.addWidget(self.table)
        top_split.setSizes([700, 400])
        splitter.addWidget(top_split)

        json_container = QWidget()
        json_layout = QVBoxLayout(json_container)
        json_layout.setContentsMargins(0, 4, 0, 0)
        json_layout.addWidget(QLabel("Quote JSON:"))
        self.json_text = QTextEdit()
        self.json_text.setReadOnly(True)
        self.json_text.setStyleSheet("font-family: Consolas, monospace; background-color: #1e1e2e; color: #cdd6f4;")
        json_layout.addWidget(self.json_text)
        splitter.addWidget(json_container)
        splitter.setSizes([500, 180])

        layout.addWidget(splitter)

    def _refresh(self):
        self.refresh_btn.setEnabled(False)
        self.status_lbl.setText("Fetching prices...")

        inst = self.inst_cb.currentText()
        interval = self.interval_cb.currentText()
        period = self.period_cb.currentText()

        self.worker = PricesWorker(inst, interval, period)
        self.worker.finished.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_done(self, quote: Dict, bars: List[Dict], label: str, symbol: str, msg: str):
        self.refresh_btn.setEnabled(True)
        self.status_lbl.setText(f"{label} ({symbol}): {msg}")
        self._quote = quote
        self._bars = bars

        self.json_text.setPlainText(pretty_json(quote))

        show = bars[-200:] if len(bars) > 200 else bars
        self.table.setRowCount(len(show))

        x_data, y_data = [], []
        for i, r in enumerate(show):
            dt = str(r.get("datetime_utc", ""))
            self.table.setItem(i, 0, QTableWidgetItem(format_datetime(dt)))
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("open", "") or "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(r.get("high", "") or "")))
            self.table.setItem(i, 3, QTableWidgetItem(str(r.get("low", "") or "")))
            self.table.setItem(i, 4, QTableWidgetItem(str(r.get("close", "") or "")))
            self.table.setItem(i, 5, QTableWidgetItem(str(r.get("volume", "") or "")))

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

        self.plot.clear()
        if x_data and y_data:
            self.plot.plot(x_data, y_data, pen=pg.mkPen("#89b4fa", width=2))
            self.plot.setTitle(f"{label} ({symbol})")
            last_dot = pg.ScatterPlotItem(
                x=[x_data[-1]], y=[y_data[-1]],
                size=10, brush=pg.mkBrush("#f9e2af")
            )
            self.plot.addItem(last_dot)

    def _on_error(self, err: str):
        self.refresh_btn.setEnabled(True)
        self.status_lbl.setText("Error fetching data")
        QMessageBox.critical(self, "Error", err)

    def _export(self):
        if not self._quote and not self._bars:
            QMessageBox.information(self, "Export", "No data loaded.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Prices", "prices.json", "JSON (*.json)")
        if not path:
            return
        try:
            payload = {
                "exported_at_utc": utc_now_rfc3339(),
                "quote": self._quote,
                "history": self._bars,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Export", f"Saved:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
