import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, _PROJECT_ROOT)

from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QWidget,
    QLabel, QHBoxLayout, QStatusBar
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from desktop_app.ui.calendar_tab import CalendarTab
from desktop_app.ui.prices_tab import PricesTab
from desktop_app.ui.market_tab import MarketTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PBL Dashboard - Economic Calendar & Market Prices")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)

        self._init_ui()
        self._init_timer()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(12)

        title = QLabel("PBL Economic & Market Dashboard")
        title_font = QFont("Segoe UI", 18, QFont.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(title)

        self.clock_label = QLabel()
        self.clock_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        self.clock_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.clock_label)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #45475a;
                border-radius: 6px;
                background: #1e1e2e;
            }
            QTabBar::tab {
                background: #313244;
                color: #cdd6f4;
                padding: 10px 24px;
                margin-right: 4px;
                border-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #45475a;
            }
        """)

        self.cal_tab = CalendarTab()
        self.prices_tab = PricesTab()
        self.market_tab = MarketTab()

        self.tabs.addTab(self.cal_tab, "Economic Calendar")
        self.tabs.addTab(self.prices_tab, "Prices")
        self.tabs.addTab(self.market_tab, "Market Overview")

        layout.addWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("color: #6c7086;")
        self.status_bar.showMessage("Ready")
        self.setStatusBar(self.status_bar)

    def _init_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_clock)
        self.timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        from datetime import datetime, timezone
        utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.clock_label.setText(utc_now)

    def set_status(self, msg: str):
        self.status_bar.showMessage(msg)
