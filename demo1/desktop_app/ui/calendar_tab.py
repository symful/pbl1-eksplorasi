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

from scrape.scrapers.forexfactory_scraper import ForexFactoryScraper
from scrape.scrapers.investing_scraper import InvestingComScraper
from desktop_app.ui.utils import event_to_dict, pretty_json, format_datetime, safe_int


class CalendarWorker(QThread):
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str)

    def __init__(self, sources: List[str], currencies: List[str], impacts: List[str], days_back: int, days_ahead: int):
        super().__init__()
        self.sources = sources
        self.currencies = currencies
        self.impacts = impacts
        self.days_back = days_back
        self.days_ahead = days_ahead

    def run(self):
        try:
            events = []
            currency_filter = self.currencies if self.currencies != ["ALL"] else None
            impact_filter = self.impacts if self.impacts else None

            if "forexfactory" in self.sources or "ff" in self.sources:
                try:
                    ff = ForexFactoryScraper(target_currencies=self.currencies if self.currencies != ["ALL"] else ["USD"])
                    ff_events = ff.fetch()
                    for e in ff_events:
                        if impact_filter is None or e.impact in impact_filter:
                            events.append(event_to_dict(e))
                except Exception as ex:
                    print(f"ForexFactory error: {ex}")

            if "investing" in self.sources or "inv" in self.sources:
                try:
                    inv = InvestingComScraper(
                        impact_filter=impact_filter,
                        days_back=self.days_back,
                        days_ahead=self.days_ahead,
                    )
                    inv_events = inv.fetch()
                    for e in inv_events:
                        if currency_filter is None or e.currency in currency_filter:
                            events.append(event_to_dict(e))
                except Exception as ex:
                    print(f"Investing.com error: {ex}")

            events = self._deduplicate(events)
            events.sort(key=lambda x: (x.get("date", ""), x.get("time", "00:00")))

            msg = f"Loaded {len(events)} events"
            self.finished.emit(events, msg)
        except Exception as e:
            self.error.emit(f"Error:\n{e}\n{traceback.format_exc()}")

    def _deduplicate(self, events: List[Dict]) -> List[Dict]:
        seen = set()
        unique = []
        for e in events:
            key = (e.get("date", ""), e.get("time", ""), e.get("currency", ""), e.get("title", "").lower())
            if key not in seen:
                seen.add(key)
                unique.append(e)
        return unique


class CalendarTab(QWidget):
    def __init__(self):
        super().__init__()
        self._events: List[Dict[str, Any]] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        controls = QHBoxLayout()

        controls.addWidget(QLabel("Source:"))
        self.source_cb = QComboBox()
        self.source_cb.addItems(["All", "ForexFactory", "Investing.com"])
        self.source_cb.setMinimumWidth(140)
        controls.addWidget(self.source_cb)

        controls.addWidget(QLabel("Currency:"))
        self.currency_cb = QComboBox()
        self.currency_cb.addItems(["ALL", "USD", "IDR"])
        self.currency_cb.setMinimumWidth(80)
        controls.addWidget(self.currency_cb)

        controls.addWidget(QLabel("Impact:"))
        self.cb_high = QCheckBox("High")
        self.cb_high.setChecked(True)
        self.cb_med = QCheckBox("Medium")
        self.cb_med.setChecked(True)
        self.cb_low = QCheckBox("Low")
        self.cb_low.setChecked(True)
        controls.addWidget(self.cb_high)
        controls.addWidget(self.cb_med)
        controls.addWidget(self.cb_low)

        controls.addWidget(QLabel("Days:"))
        self.days_input = QLineEdit("7")
        self.days_input.setFixedWidth(50)
        controls.addWidget(self.days_input)

        controls.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh)
        controls.addWidget(self.refresh_btn)

        self.export_btn = QPushButton("Export JSON")
        self.export_btn.clicked.connect(self._export)
        controls.addWidget(self.export_btn)

        layout.addLayout(controls)

        self.status_lbl = QLabel("Ready. Click Refresh to load events.")
        self.status_lbl.setStyleSheet("color: #a6adc8; padding: 4px;")
        layout.addWidget(self.status_lbl)

        splitter = QSplitter(Qt.Vertical)

        self.table = QTableWidget()
        cols = ["Date", "Time", "Cur", "Impact", "Title", "Actual", "Forecast", "Previous"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_select)
        splitter.addWidget(self.table)

        json_container = QWidget()
        json_layout = QVBoxLayout(json_container)
        json_layout.setContentsMargins(0, 4, 0, 0)
        json_layout.addWidget(QLabel("Event JSON:"))
        self.json_text = QTextEdit()
        self.json_text.setReadOnly(True)
        self.json_text.setStyleSheet("font-family: Consolas, monospace; background-color: #1e1e2e; color: #cdd6f4;")
        json_layout.addWidget(self.json_text)
        splitter.addWidget(json_container)
        splitter.setSizes([500, 200])

        layout.addWidget(splitter)

    def _refresh(self):
        self.refresh_btn.setEnabled(False)
        self.status_lbl.setText("Fetching events...")
        self.table.setRowCount(0)
        self._events.clear()
        self.json_text.clear()

        source_map = {
            "All": ["forexfactory", "investing"],
            "ForexFactory": ["forexfactory"],
            "Investing.com": ["investing"],
        }
        sources = source_map.get(self.source_cb.currentText(), ["forexfactory", "investing"])
        currencies = [self.currency_cb.currentText().strip().upper()]
        impacts = []
        if self.cb_high.isChecked():
            impacts.append("High")
        if self.cb_med.isChecked():
            impacts.append("Medium")
        if self.cb_low.isChecked():
            impacts.append("Low")
        days = safe_int(self.days_input.text(), 7)

        self.worker = CalendarWorker(sources, currencies, impacts, 1, days)
        self.worker.finished.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_done(self, events: List[Dict], msg: str):
        self.refresh_btn.setEnabled(True)
        self.status_lbl.setText(msg)
        self._events = events

        self.table.setRowCount(len(events))
        for i, e in enumerate(events):
            self.table.setItem(i, 0, QTableWidgetItem(str(e.get("date", "") or "")))
            self.table.setItem(i, 1, QTableWidgetItem(str(e.get("time", "") or "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(e.get("currency", "") or "")))

            impact = str(e.get("impact", "") or "")
            impact_item = QTableWidgetItem(impact)
            if impact == "High":
                impact_item.setBackground(Qt.red)
                impact_item.setForeground(Qt.white)
            elif impact == "Medium":
                impact_item.setBackground(Qt.yellow)
                impact_item.setForeground(Qt.black)
            self.table.setItem(i, 3, impact_item)

            self.table.setItem(i, 4, QTableWidgetItem(str(e.get("title", "") or "")))
            self.table.setItem(i, 5, QTableWidgetItem(str(e.get("actual", "") or "")))
            self.table.setItem(i, 6, QTableWidgetItem(str(e.get("forecast", "") or "")))
            self.table.setItem(i, 7, QTableWidgetItem(str(e.get("previous", "") or "")))

    def _on_error(self, err: str):
        self.refresh_btn.setEnabled(True)
        self.status_lbl.setText("Error loading events")
        QMessageBox.critical(self, "Error", err)

    def _on_select(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if 0 <= row < len(self._events):
            self.json_text.setPlainText(pretty_json(self._events[row]))

    def _export(self):
        if not self._events:
            QMessageBox.information(self, "Export", "No events loaded.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Calendar", "economic_calendar.json", "JSON (*.json)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._events, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "Export", f"Saved:\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Export Error", str(exc))
