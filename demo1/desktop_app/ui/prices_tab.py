import json
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QCheckBox, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QTextEdit, QMessageBox,
    QFileDialog, QSplitter, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import pyqtgraph as pg

from scrape.scrapers.yfinance_price_scraper import YahooFinancePriceScraper
from desktop_app.ui.utils import _utc_now_rfc3339, _pretty_json, _format_dt_str

class PricesWorker(QThread):
    finished = pyqtSignal(dict, list, str, str, str) # quote, history, label, symbol, msg
    error = pyqtSignal(str)

    def __init__(self, instrument, interval, period, auto_adjust):
        super().__init__()
        self.instrument = instrument
        self.interval = interval
        self.period = period
        self.auto_adjust = auto_adjust
        self.scraper = YahooFinancePriceScraper(output_dir=None)

    def run(self):
        try:
            label, symbol = self._symbol_for_instrument(self.instrument)
            
            # Use raw interval/period as requested, standard scraper will handle limits
            quote = self.scraper.fetch_quote(symbol=symbol, ticker_label=label)
            bars = self.scraper.fetch_history(
                symbol=symbol,
                ticker_label=label,
                interval=self.interval,
                period=self.period,
                start=None,
                end=None,
                auto_adjust=self.auto_adjust,
            )
            
            quote_row = asdict(quote) if quote else {}
            history_rows = [asdict(b) for b in bars] if bars else []
            
            msg = f"Fetched {len(history_rows)} bars."
            if not history_rows:
                msg = "History is empty (rate limit or interval not supported)."
            
            self.finished.emit(quote_row, history_rows, label, symbol, msg)
        except Exception as e:
            self.error.emit(f"Price refresh failed:\n{e}\n{traceback.format_exc()}")

    def _symbol_for_instrument(self, inst: str):
        inst = (inst or "").strip().upper()
        if inst == "USDIDR": return "USDIDR", "IDR=X"
        if inst == "IHSG": return "IHSG", "^JKSE"
        if inst == "BBCA": return "BBCA", "BBCA.JK"
        return inst, inst


class TimeAxisItem(pg.AxisItem):
    """Custom format for X-axis (timestamps)"""
    def tickStrings(self, values, scale, spacing):
        return [datetime.fromtimestamp(val, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") for val in values]

class PricesTab(QWidget):
    def __init__(self):
        super().__init__()
        self._quote_row = {}
        self._history_rows = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Controls Group
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Instrument:"))
        self.inst_cb = QComboBox()
        self.inst_cb.addItems(["USDIDR", "IHSG", "BBCA"])
        controls_layout.addWidget(self.inst_cb)
        
        controls_layout.addWidget(QLabel("Interval:"))
        self.interval_cb = QComboBox()
        self.interval_cb.addItems(["1m", "5m", "15m", "30m", "1h", "1d", "5d", "1wk", "1mo", "3mo"])
        self.interval_cb.setCurrentText("1d")
        controls_layout.addWidget(self.interval_cb)
        
        controls_layout.addWidget(QLabel("Period:"))
        self.period_cb = QComboBox()
        self.period_cb.addItems(["5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"])
        self.period_cb.setCurrentText("3mo")
        controls_layout.addWidget(self.period_cb)
        
        self.auto_adjust_cb = QCheckBox("Auto-adjust")
        controls_layout.addWidget(self.auto_adjust_cb)
        
        controls_layout.addStretch()
        
        self.refresh_btn = QPushButton("Refresh Prices")
        self.refresh_btn.clicked.connect(self.refresh_async)
        self.export_btn = QPushButton("Export JSON...")
        self.export_btn.clicked.connect(self.export_json)
        
        controls_layout.addWidget(self.refresh_btn)
        controls_layout.addWidget(self.export_btn)
        
        layout.addLayout(controls_layout)
        
        self.status_lbl = QLabel("Ready.")
        self.status_lbl.setStyleSheet("color: #a6adc8;")
        layout.addWidget(self.status_lbl)
        
        # Splitter to separate Chart/Table and JSON
        main_splitter = QSplitter(Qt.Vertical)
        
        # Top half: Chart and Table side-by-side
        top_splitter = QSplitter(Qt.Horizontal)
        
        # Chart using PyQtGraph
        pg.setConfigOption('background', '#1e1e2e')
        pg.setConfigOption('foreground', '#cdd6f4')
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self.plot_widget.setLabel('left', 'Close Price')
        self.plot_widget.setLabel('bottom', 'Time (UTC)')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        top_splitter.addWidget(self.plot_widget)
        
        # Table for OHLCV
        self.table = QTableWidget()
        cols = ["Datetime (UTC)", "Open", "High", "Low", "Close", "Vol"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        top_splitter.addWidget(self.table)
        
        top_splitter.setSizes([800, 400])
        main_splitter.addWidget(top_splitter)
        
        # JSON output at the bottom
        json_container = QWidget()
        json_layout = QVBoxLayout(json_container)
        json_layout.setContentsMargins(0, 0, 0, 0)
        json_layout.addWidget(QLabel("Quote snapshot (JSON):"))
        self.json_text = QTextEdit()
        self.json_text.setReadOnly(True)
        self.json_text.setStyleSheet("font-family: Consolas, monospace; background-color: #1e1e2e;")
        json_layout.addWidget(self.json_text)
        
        main_splitter.addWidget(json_container)
        main_splitter.setSizes([500, 150])
        
        layout.addWidget(main_splitter)

    def refresh_async(self):
        self.refresh_btn.setEnabled(False)
        self.status_lbl.setText("Fetching prices...")
        
        inst = self.inst_cb.currentText().strip()
        interv = self.interval_cb.currentText().strip()
        period = self.period_cb.currentText().strip()
        adj = self.auto_adjust_cb.isChecked()
        
        self.worker = PricesWorker(inst, interv, period, adj)
        self.worker.finished.connect(self._on_refresh_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_refresh_done(self, quote_row, history_rows, label, symbol, msg):
        self.refresh_btn.setEnabled(True)
        self.status_lbl.setText(msg)
        self._quote_row = quote_row
        self._history_rows = history_rows
        
        self.json_text.setPlainText(_pretty_json(quote_row))
        
        self.table.setRowCount(0)
        show_rows = history_rows[-200:] if len(history_rows) > 200 else history_rows
        self.table.setRowCount(len(show_rows))
        
        x_data = []
        y_data = []
        
        for i, r in enumerate(show_rows):
            dt_s = str(r.get("datetime_utc", ""))
            self.table.setItem(i, 0, QTableWidgetItem(_format_dt_str(dt_s)))
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("open", ""))))
            self.table.setItem(i, 2, QTableWidgetItem(str(r.get("high", ""))))
            self.table.setItem(i, 3, QTableWidgetItem(str(r.get("low", ""))))
            self.table.setItem(i, 4, QTableWidgetItem(str(r.get("close", ""))))
            self.table.setItem(i, 5, QTableWidgetItem(str(r.get("volume", ""))))
            
            if dt_s and r.get("close") is not None:
                try:
                    # More robust parsing for pyqtgraph timestamp conversion
                    if dt_s.endswith("Z"):
                        dt_s = dt_s[:-1] + "+00:00"
                    
                    # Split fractional seconds manually if fromisoformat fails
                    dt = datetime.fromisoformat(dt_s)
                    if not dt.tzinfo:
                        dt = dt.replace(tzinfo=timezone.utc)
                        
                    x_data.append(dt.timestamp())
                    y_data.append(float(r.get("close")))
                except Exception as e:
                    pass

        self.plot_widget.clear()
        if x_data and y_data:
            self.plot_widget.plot(x_data, y_data, pen=pg.mkPen('#89b4fa', width=2))
            self.plot_widget.setTitle(f"{label} ({symbol})")
            
            # Scatter for the last point
            scatter = pg.ScatterPlotItem(x=[x_data[-1]], y=[y_data[-1]], size=10, brush=pg.mkBrush('#f9e2af'))
            self.plot_widget.addItem(scatter)

    def _on_error(self, err_msg):
        self.refresh_btn.setEnabled(True)
        self.status_lbl.setText("Error.")
        QMessageBox.critical(self, "Error", err_msg)

    def export_json(self):
        if not self._quote_row and not self._history_rows:
            QMessageBox.information(self, "Export", "No data loaded yet.")
            return
        
        payload = {
            "exported_at_utc": _utc_now_rfc3339(),
            "quote": self._quote_row,
            "history": self._history_rows,
        }
        
        path, _ = QFileDialog.getSaveFileName(self, "Export prices JSON", "prices_ui_export.json", "JSON (*.json)")
        if not path:
            return
            
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Export", f"Saved:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
