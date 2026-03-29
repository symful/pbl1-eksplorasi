from PyQt5.QtCore import QThread, pyqtSignal
from scrapers.detik import DetikScraper
from scrapers.kompas import KompasScraper
from utils.saver import DataSaver


class ScrapeWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, portal, count):
        super().__init__()
        self.portal = portal
        self.count = count

    def run(self):
        try:

            def log_fn(msg):
                self.log.emit(msg)

            scraper = KompasScraper() if self.portal == "Kompas" else DetikScraper()
            results = scraper.scrape(self.count, log_fn=log_fn)
            DataSaver.save_to_csv(results)
            DataSaver.save_to_json(results)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))
