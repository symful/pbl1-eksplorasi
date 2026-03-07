import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from ui.threading import ScrapeWorker

BG_BASE = "#0d1117"
BG_CARD = "#161b22"
BG_HOVER = "#21262d"
BORDER = "#30363d"
TEXT_PRI = "#e6edf3"
TEXT_SEC = "#8b949e"
ACCENT = "#1f6feb"
GREEN = "#238636"
GREEN_HVR = "#2ea043"
RED = "#da3633"

STYLESHEET = f"""
    QMainWindow, QWidget {{
        background-color: {BG_BASE};
        color: {TEXT_PRI};
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        font-size: 13px;
    }}
    QLineEdit, QComboBox {{
        background-color: {BG_CARD};
        color: {TEXT_PRI};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 7px 12px;
    }}
    QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
    QComboBox QAbstractItemView {{
        background-color: {BG_CARD};
        color: {TEXT_PRI};
        border: 1px solid {BORDER};
        selection-background-color: {ACCENT};
    }}
    QPushButton {{
        background-color: {GREEN};
        color: #fff;
        font-weight: 700;
        padding: 8px 18px;
        border: 1px solid rgba(240,246,252,0.1);
        border-radius: 6px;
    }}
    QPushButton:hover  {{ background-color: {GREEN_HVR}; }}
    QPushButton:pressed{{ background-color: {GREEN}; }}
    QPushButton:disabled{{ background-color: {BG_HOVER}; color: {TEXT_SEC}; border-color: transparent; }}
    QPushButton#dangerBtn {{
        background-color: transparent;
        color: {RED};
        border: 1px solid {RED};
    }}
    QPushButton#dangerBtn:hover {{ background-color: {RED}; color: #fff; }}
    QTextEdit, QListWidget {{
        background-color: {BG_BASE};
        color: {TEXT_PRI};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 10px;
        line-height: 1.6;
    }}
    QListWidget::item {{ padding: 10px 14px; border-bottom: 1px solid {BG_HOVER}; }}
    QListWidget::item:selected {{ background-color: {ACCENT}; color: #fff; border-radius: 4px; }}
    QListWidget::item:hover:!selected {{ background-color: {BG_CARD}; }}
    QTabWidget::pane {{
        border: 1px solid {BORDER};
        border-radius: 0 6px 6px 6px;
        background: {BG_BASE};
    }}
    QTabBar::tab {{
        background: {BG_CARD};
        color: {TEXT_SEC};
        padding: 9px 22px;
        border: 1px solid transparent;
        border-bottom: 1px solid {BORDER};
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 3px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {BG_BASE};
        color: {TEXT_PRI};
        border: 1px solid {BORDER};
        border-bottom: 1px solid {BG_BASE};
    }}
    QTabBar::tab:hover:!selected {{ color: {TEXT_PRI}; background: {BG_HOVER}; }}
    QScrollBar:vertical {{
        border: none; background: {BG_BASE}; width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER}; min-height: 24px; border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #484f58; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{
        border: none; background: {BG_BASE}; height: 8px;
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER}; min-width: 24px; border-radius: 4px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QSplitter::handle {{ background: {BORDER}; }}
    QSplitter::handle:horizontal {{ width: 3px; }}
    QScrollArea {{ border: none; background: transparent; }}
    QProgressBar {{
        border: none; border-radius: 3px;
        background: {BG_CARD}; height: 4px;
    }}
    QProgressBar::chunk {{ background: {GREEN}; border-radius: 3px; }}
    QStatusBar {{ background: {BG_CARD}; color: {TEXT_SEC}; border-top: 1px solid {BORDER}; }}
    QFrame#card {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    QLabel#sectionTitle {{
        font-size: 20px; font-weight: 700; color: {TEXT_PRI};
    }}
    QLabel#metaLabel {{ color: {TEXT_SEC}; font-size: 12px; }}
    QLabel#articleTitle {{
        font-size: 16px; font-weight: 700; color: {TEXT_PRI};
    }}
"""


def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"border: 1px solid {BORDER};")
    return f


class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("News Scraper Professional")
        self.setMinimumSize(1050, 660)
        self.setStyleSheet(STYLESHEET)
        self._articles_data = []
        self._build_ui()
        self._status_bar = QStatusBar()
        self._status_bar.showMessage("Ready")
        self.setStatusBar(self._status_bar)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_scraper_tab(), "  Scraper  ")
        self._tabs.addTab(self._build_viewer_tab(), "  Results  ")
        root.addWidget(self._tabs)

    def _build_scraper_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 16)

        title = QLabel("News Scraper")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        sub = QLabel("Scrape and store news articles from Indonesian portals.")
        sub.setObjectName("metaLabel")
        layout.addWidget(sub)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(12)

        card_layout.addWidget(QLabel("Portal:"))
        self._portal_combo = QComboBox()
        self._portal_combo.addItems(["Kompas", "Detik"])
        self._portal_combo.setMinimumWidth(110)
        card_layout.addWidget(self._portal_combo)

        card_layout.addWidget(QLabel("Limit:"))
        self._limit_input = QLineEdit("5")
        self._limit_input.setMaximumWidth(70)
        card_layout.addWidget(self._limit_input)

        card_layout.addStretch()

        self._clear_btn = QPushButton("Clear Log")
        self._clear_btn.setObjectName("dangerBtn")
        self._clear_btn.clicked.connect(lambda: self._log_area.clear())
        card_layout.addWidget(self._clear_btn)

        self._scrape_btn = QPushButton("  Start Scraping")
        self._scrape_btn.setMinimumWidth(150)
        self._scrape_btn.clicked.connect(self._start_scrape)
        card_layout.addWidget(self._scrape_btn)

        layout.addWidget(card)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._log_area = QTextEdit()
        self._log_area.setReadOnly(True)
        self._log_area.setPlaceholderText(
            "Logs will appear here when a scrape is running..."
        )
        self._log_area.setFont(QFont("Consolas, Monaco, monospace", 12))
        layout.addWidget(self._log_area, 1)

        return page

    def _build_viewer_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QWidget()
        toolbar.setStyleSheet(
            f"background:{BG_CARD}; border-bottom:1px solid {BORDER};"
        )
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 10, 16, 10)

        hdr = QLabel("Article Database")
        hdr.setObjectName("sectionTitle")
        hdr.setFont(QFont("Segoe UI", 16, QFont.Bold))
        tb_layout.addWidget(hdr)
        tb_layout.addStretch()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter articles...")
        self._search_input.setMaximumWidth(220)
        self._search_input.textChanged.connect(self._filter_articles)
        tb_layout.addWidget(self._search_input)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(
            f"background:{ACCENT}; border-color:{ACCENT}; padding:7px 14px;"
        )
        refresh_btn.clicked.connect(self._load_output_data)
        tb_layout.addWidget(refresh_btn)

        layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        self._article_list = QListWidget()
        self._article_list.itemClicked.connect(self._display_article)
        splitter.addWidget(self._article_list)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        detail_widget = QWidget()
        detail_widget.setStyleSheet(f"background:{BG_BASE};")
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(20, 20, 20, 20)
        detail_layout.setSpacing(10)

        self._lbl_title = QLabel("Select an article to read.")
        self._lbl_title.setObjectName("articleTitle")
        self._lbl_title.setWordWrap(True)
        self._lbl_title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        detail_layout.addWidget(self._lbl_title)

        self._lbl_meta = QLabel("")
        self._lbl_meta.setObjectName("metaLabel")
        detail_layout.addWidget(self._lbl_meta)

        self._lbl_link = QLabel("")
        self._lbl_link.setOpenExternalLinks(True)
        detail_layout.addWidget(self._lbl_link)

        detail_layout.addWidget(_hline())

        self._lbl_image = QLabel()
        self._lbl_image.setAlignment(Qt.AlignCenter)
        self._lbl_image.setMinimumHeight(200)
        self._lbl_image.setStyleSheet(
            f"background:{BG_CARD}; border:1px dashed {BORDER}; border-radius:6px; color:{TEXT_SEC};"
        )
        detail_layout.addWidget(self._lbl_image)

        self._content_area = QTextEdit()
        self._content_area.setReadOnly(True)
        self._content_area.setPlaceholderText("Article content will appear here...")
        self._content_area.setMinimumHeight(160)
        self._content_area.setStyleSheet("border: none; padding: 0;")
        detail_layout.addWidget(self._content_area, 1)

        scroll_area.setWidget(detail_widget)
        splitter.addWidget(scroll_area)
        splitter.setSizes([280, 740])

        layout.addWidget(splitter, 1)
        return page

    def _start_scrape(self):
        portal = self._portal_combo.currentText()
        raw = self._limit_input.text()
        count = int(raw) if raw.isdigit() and int(raw) > 0 else 5

        self._log(f"── Starting scrape: {portal} | limit {count} ──")
        self._scrape_btn.setEnabled(False)
        self._progress.show()
        self._status_bar.showMessage(f"Scraping {portal}…")

        self._worker = ScrapeWorker(portal, count)
        self._worker.log.connect(self._log)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, results):
        ok = sum(1 for r in results if r.content_blocks)
        img = sum(1 for r in results if r.image_path)
        self._log(
            f"── Done: {len(results)} articles | {ok} with content | {img} with image ──"
        )
        self._scrape_btn.setEnabled(True)
        self._progress.hide()
        self._status_bar.showMessage(f"Scraped {len(results)} articles successfully.")
        self._load_output_data()

        self._tabs.setCurrentIndex(1)

    def _on_error(self, message):
        self._log(f"[ERROR] {message}")
        self._scrape_btn.setEnabled(True)
        self._progress.hide()
        self._status_bar.showMessage("Scrape failed — see log for details.")

    def _log(self, msg):
        self._log_area.append(msg)

    def _load_output_data(self):
        json_path = os.path.join("output", "berita.json")
        self._article_list.clear()
        self._articles_data = []
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    self._articles_data = json.load(f)
                for item in self._articles_data:
                    portal_tag = f"[{item.get('portal','?')}] "
                    self._article_list.addItem(
                        portal_tag + item.get("title", "Untitled")
                    )
            except Exception:
                pass
        count = len(self._articles_data)
        self._status_bar.showMessage(f"{count} article(s) in database.")

    def _filter_articles(self, text):
        q = text.lower()
        for i in range(self._article_list.count()):
            item = self._article_list.item(i)
            item.setHidden(q not in item.text().lower())

    def _display_article(self, item):
        idx = self._article_list.row(item)
        if idx < 0 or idx >= len(self._articles_data):
            return
        data = self._articles_data[idx]

        self._lbl_title.setText(data.get("title", "No Title"))

        portal = data.get("portal", "Unknown")
        date_str = data.get("date", "")
        self._lbl_meta.setText(f"{portal}  ·  {date_str}")

        link = data.get("link", "")
        if link:
            self._lbl_link.setText(
                f"<a href='{link}' style='color:#58a6ff;text-decoration:none;'>Read original article →</a>"
            )
        else:
            self._lbl_link.setText("")

        blocks = data.get("content_blocks", [])
        if blocks:
            parts = []
            for blk in blocks:
                if blk.get("type") == "text":
                    parts.append(blk.get("value", ""))

            self._content_area.setPlainText(
                "\n\n".join(parts) if parts else "No text content."
            )
        else:
            self._content_area.setPlainText(
                "No content was extracted for this article."
            )

        img_path = data.get("image_path", "")
        if img_path and os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            self._lbl_image.setPixmap(
                pixmap.scaled(720, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self._lbl_image.setStyleSheet("background: transparent; border: none;")
        else:
            self._lbl_image.clear()
            self._lbl_image.setText("No image available")
            self._lbl_image.setStyleSheet(
                f"background:{BG_CARD}; border:1px dashed {BORDER}; border-radius:6px; color:{TEXT_SEC};"
            )
