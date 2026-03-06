from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit
from ui.threading import ScrapeWorker

class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("News Scraper Pro")
        self.setMinimumSize(600, 400)
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        form_layout = QHBoxLayout()
        self.portal_combo = QComboBox()
        self.portal_combo.addItems(["Kompas", "Detik"])
        
        self.range_input = QLineEdit()
        self.range_input.setPlaceholderText("Range (e.g. 5)")
        self.range_input.setText("5")

        self.scrape_btn = QPushButton("Scrape Now")
        self.scrape_btn.clicked.connect(self.start_scrape)

        form_layout.addWidget(QLabel("Portal:"))
        form_layout.addWidget(self.portal_combo)
        form_layout.addWidget(QLabel("Range:"))
        form_layout.addWidget(self.range_input)
        form_layout.addWidget(self.scrape_btn)

        layout.addLayout(form_layout)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

    def start_scrape(self):
        portal = self.portal_combo.currentText()
        count = int(self.range_input.text())
        self.log_output.append(f"Starting scrape for {portal} (Range: {count})...")
        self.scrape_btn.setEnabled(False)

        self.worker = ScrapeWorker(portal, count)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_finished(self, results):
        self.log_output.append(f"Successfully scraped {len(results)} items.")
        for item in results:
            self.log_output.append(f"- {item.title}")
        self.scrape_btn.setEnabled(True)

    def on_error(self, message):
        self.log_output.append(f"Error: {message}")
        self.scrape_btn.setEnabled(True)
