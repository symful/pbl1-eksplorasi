from selenium.webdriver.common.by import By
from core.driver import DriverFactory
from models.news_item import NewsItem

class KompasScraper:
    def __init__(self):
        self.url = "https://www.kompas.com/"

    def scrape(self, num_items=5):
        driver = DriverFactory.get_driver()
        driver.get(self.url)
        results = []
        try:
            articles = driver.find_elements(By.CSS_SELECTOR, ".article__list")
            for article in articles[:num_items]:
                title_elem = article.find_element(By.CSS_SELECTOR, ".article__link")
                date_elem = article.find_element(By.CSS_SELECTOR, ".article__date")
                results.append(NewsItem(
                    title=title_elem.text,
                    date=date_elem.text,
                    link=title_elem.get_attribute("href"),
                    portal="Kompas"
                ))
        finally:
            driver.quit()
        return results
