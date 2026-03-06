from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class DriverFactory:
    @staticmethod
    def get_driver(headless=True):
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
