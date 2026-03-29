import os
from PyQt5.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer
from datetime import datetime, timezone

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PBL Dashboard - Economic Calendar & Prices")
        self.resize(1400, 860)
        self.setMinimumSize(1100, 740)
        
        self.init_ui()
        self.init_timer()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("PBL Desktop App")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet("font-size: 12px; color: #a6adc8;")
        self.clock_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.clock_label)
        
        main_layout.addLayout(header_layout)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #45475a; border-radius: 4px; }")
        
        from desktop_app.ui.calendar_tab import CalendarTab
        from desktop_app.ui.prices_tab import PricesTab
        from desktop_app.ui.market_tab import MarketOverviewTab
        
        self.cal_tab = CalendarTab()
        self.prices_tab = PricesTab()
        self.market_tab = MarketOverviewTab()
        
        self.tabs.addTab(self.cal_tab, "Economic Calendar")
        self.tabs.addTab(self.prices_tab, "Prices (Manual)")
        self.tabs.addTab(self.market_tab, "Market Overview")
        
        main_layout.addWidget(self.tabs)
        
        # Footer
        footer_label = QLabel("Tip: Market Overview auto-refreshes quotes. Output is viewed securely inside each tab.")
        footer_label.setStyleSheet("font-size: 11px; color: #6c7086;")
        main_layout.addWidget(footer_label)
        
    def init_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)
        self.update_clock()
        
    def update_clock(self):
        utc_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.clock_label.setText(f"UTC: {utc_now}")
