import json
import traceback
from typing import List, Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QCheckBox, QLineEdit, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QTextEdit, QMessageBox,
    QFileDialog, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from scrape.main import run_pipeline
from desktop_app.ui.utils import _safe_int, _event_to_dict, _pretty_json

class CalendarWorker(QThread):
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str)

    def __init__(self, currency, impacts, days_back):
        super().__init__()
        self.currency = currency
        self.impacts = impacts
        self.days_back = days_back

    def run(self):
        try:
            curr_filter = None if self.currency == "ALL" else [self.currency]
            result = run_pipeline(
                sources=["inv"],
                impact_filter=self.impacts if self.impacts else None,
                currency_filter=curr_filter,
                days_back=self.days_back,
                days_ahead=0,
                export_fmt="json"
            )
            events = [_event_to_dict(e) for e in (result.events or [])]
            msg = f"Loaded {len(events)} events."
            self.finished.emit(events, msg)
        except Exception as e:
            self.error.emit(f"Calendar refresh failed:\n{e}\n{traceback.format_exc()}")

class CalendarTab(QWidget):
    def __init__(self):
        super().__init__()
        self._events: List[Dict[str, Any]] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Controls Frame
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Currency:"))
        self.currency_cb = QComboBox()
        self.currency_cb.addItems(["ALL", "USD", "IDR"])
        controls_layout.addWidget(self.currency_cb)
        
        controls_layout.addWidget(QLabel("Impact:"))
        self.cb_high = QCheckBox("High")
        self.cb_high.setChecked(True)
        self.cb_med = QCheckBox("Med")
        self.cb_med.setChecked(True)
        self.cb_low = QCheckBox("Low")
        self.cb_low.setChecked(True)
        
        controls_layout.addWidget(self.cb_high)
        controls_layout.addWidget(self.cb_med)
        controls_layout.addWidget(self.cb_low)
        
        controls_layout.addWidget(QLabel("Days back:"))
        self.days_back_input = QLineEdit("1")
        self.days_back_input.setFixedWidth(50)
        controls_layout.addWidget(self.days_back_input)
        
        controls_layout.addStretch()
        
        self.refresh_btn = QPushButton("Refresh Calendar")
        self.refresh_btn.clicked.connect(self.refresh_async)
        self.export_btn = QPushButton("Export JSON...")
        self.export_btn.clicked.connect(self.export_json)
        
        controls_layout.addWidget(self.refresh_btn)
        controls_layout.addWidget(self.export_btn)
        
        layout.addLayout(controls_layout)
        
        self.status_lbl = QLabel("Ready.")
        self.status_lbl.setStyleSheet("color: #a6adc8;")
        layout.addWidget(self.status_lbl)
        
        # Splitter for Table and JSON view
        splitter = QSplitter(Qt.Vertical)
        
        # Table
        self.table = QTableWidget()
        cols = ["Date", "Time", "Cur", "Impact", "Title", "Source", "Actual", "Forecast", "Prev"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_select)
        
        splitter.addWidget(self.table)
        
        # JSON output
        json_container = QWidget()
        json_layout = QVBoxLayout(json_container)
        json_layout.setContentsMargins(0, 0, 0, 0)
        json_layout.addWidget(QLabel("Selected event (JSON):"))
        self.json_text = QTextEdit()
        self.json_text.setReadOnly(True)
        self.json_text.setStyleSheet("font-family: Consolas, monospace; background-color: #1e1e2e;")
        json_layout.addWidget(self.json_text)
        
        splitter.addWidget(json_container)
        splitter.setSizes([500, 200])
        
        layout.addWidget(splitter)

    def refresh_async(self):
        self.refresh_btn.setEnabled(False)
        self.status_lbl.setText("Fetching calendar...")
        self.table.setRowCount(0)
        self._events.clear()
        self.json_text.clear()
        
        currency = self.currency_cb.currentText().strip().upper()
        impacts = []
        if self.cb_high.isChecked(): impacts.append("High")
        if self.cb_med.isChecked(): impacts.append("Medium")
        if self.cb_low.isChecked(): impacts.append("Low")
        
        days_back = _safe_int(self.days_back_input.text(), 1)
        
        self.worker = CalendarWorker(currency, impacts, days_back)
        self.worker.finished.connect(self._on_refresh_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_refresh_done(self, events: List[Dict[str, Any]], msg: str):
        self.refresh_btn.setEnabled(True)
        self.status_lbl.setText(msg)
        self._events = events
        
        self.table.setRowCount(len(events))
        for i, e in enumerate(events):
            self.table.setItem(i, 0, QTableWidgetItem(str(e.get("date", ""))))
            self.table.setItem(i, 1, QTableWidgetItem(str(e.get("time", ""))))
            self.table.setItem(i, 2, QTableWidgetItem(str(e.get("currency", ""))))
            self.table.setItem(i, 3, QTableWidgetItem(str(e.get("impact", ""))))
            self.table.setItem(i, 4, QTableWidgetItem(str(e.get("title", ""))))
            self.table.setItem(i, 5, QTableWidgetItem(str(e.get("source", ""))))
            self.table.setItem(i, 6, QTableWidgetItem(str(e.get("actual", ""))))
            self.table.setItem(i, 7, QTableWidgetItem(str(e.get("forecast", ""))))
            self.table.setItem(i, 8, QTableWidgetItem(str(e.get("previous", ""))))

    def _on_error(self, err_msg: str):
        self.refresh_btn.setEnabled(True)
        self.status_lbl.setText("Error.")
        QMessageBox.critical(self, "Error", err_msg)

    def _on_select(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if 0 <= row < len(self._events):
            obj = self._events[row]
            self.json_text.setPlainText(_pretty_json(obj))

    def export_json(self):
        if not self._events:
            QMessageBox.information(self, "Export", "No events loaded yet.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export calendar JSON", "economic_calendar_ui_export.json", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._events, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Export", f"Saved:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
