from selenium.webdriver.common.by import By
from core.driver import DriverFactory
from models.news_item import NewsItem

class DetikScraper:
    def __init__(self):
        self.url = "https://www.detik.com/"

    def scrape(self, num_items=5):
        driver = DriverFactory.get_driver()
        driver.get(self.url)
        results = []
        try:
            articles = driver.find_elements(By.CSS_SELECTOR, "article")
            for article in articles[:num_items]:
                try:
                    title_elem = article.find_element(By.CSS_SELECTOR, ".media__title a")
                    date_elem = article.find_element(By.CSS_SELECTOR, ".media__date")
                    results.append(NewsItem(
                        title=title_elem.text,
                        date=date_elem.text if date_elem else "",
                        link=title_elem.get_attribute("href"),
                        portal="Detik"
                    ))
                except:
                    continue
        finally:
            driver.quit()
        return results
