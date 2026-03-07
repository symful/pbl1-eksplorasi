import time

from core.driver import DriverFactory
from models.news_item import ContentBlock, NewsItem
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from utils.saver import DataSaver

_ARTICLE_LINK_SEL = "a[href*='/read/']"
_READ_CONTENT_SEL = "div.read__content"
_SKIP_DOMAINS = [
    "kgnow.com",
    "video.kompas.com",
    "kognisi.id",
    "gramedia.com",
    "doubleclick",
]


def _safe_get(driver, url, log_fn=None):
    try:
        driver.get(url)
    except TimeoutException:
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass
        if log_fn:
            log_fn(f"  [WARN] Timed out loading {url[:60]}... — continuing.")


def _scrape_content_blocks(driver) -> list:
    blocks = []
    try:
        container = driver.find_element(By.CSS_SELECTOR, _READ_CONTENT_SEL)
        children = container.find_elements(By.XPATH, ".//*[self::p or self::img]")
        for child in children:
            tag = child.tag_name
            if tag == "p":
                txt = child.text.strip()
                if txt:
                    blocks.append(ContentBlock(block_type="text", value=txt))
            elif tag == "img":
                src = (
                    child.get_attribute("src") or child.get_attribute("data-src") or ""
                )
                if src and "data:image" not in src:
                    blocks.append(ContentBlock(block_type="image", value=src))
    except Exception:
        pass
    return blocks


class KompasScraper:
    URL = "https://www.kompas.com/"

    def scrape(self, num_items: int = 5, log_fn=None) -> list:
        def log(msg):
            if log_fn:
                log_fn(msg)

        driver = DriverFactory.get_driver()
        results = []
        try:
            log("[Kompas] Opening homepage...")
            _safe_get(driver, self.URL, log)
            time.sleep(2)

            for _ in range(5):
                driver.execute_script("window.scrollBy(0, 700);")
                time.sleep(0.35)

            link_elems = driver.find_elements(By.CSS_SELECTOR, _ARTICLE_LINK_SEL)
            seen_urls = set()
            metadata = []

            for elem in link_elems:
                if len(metadata) >= num_items:
                    break
                href = elem.get_attribute("href") or ""
                title_text = elem.text.strip()

                if not href or not title_text:
                    continue
                if any(d in href for d in _SKIP_DOMAINS):
                    continue
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                metadata.append(
                    {
                        "title": title_text.split("\n")[0],
                        "link": href,
                    }
                )

            log(f"[Kompas] Found {len(metadata)} article(s). Fetching content...")

            for i, data in enumerate(metadata, 1):
                log(f"  [{i}/{len(metadata)}] {data['title'][:60]}...")
                content_blocks = []
                cover_img_url = ""
                cover_img_path = ""
                date_text = ""

                try:
                    _safe_get(driver, data["link"], log)

                    for date_sel in [".read__time", "time", ".date"]:
                        try:
                            date_text = driver.find_element(
                                By.CSS_SELECTOR, date_sel
                            ).text.strip()
                            break
                        except Exception:
                            pass

                    try:
                        img = driver.find_element(
                            By.CSS_SELECTOR,
                            ".photo__wrap img, .read__photo img, figure img",
                        )
                        cover_img_url = (
                            img.get_attribute("src")
                            or img.get_attribute("data-src")
                            or ""
                        )
                    except Exception:
                        pass

                    content_blocks = _scrape_content_blocks(driver)

                except Exception as e:
                    log(f"  [WARN] Failed to fetch article: {e}")

                cover_img_path = (
                    DataSaver.download_image(cover_img_url, prefix="kompas")
                    if cover_img_url
                    else ""
                )

                results.append(
                    NewsItem(
                        title=data["title"],
                        date=date_text,
                        link=data["link"],
                        portal="Kompas",
                        content_blocks=content_blocks,
                        image_url=cover_img_url,
                        image_path=cover_img_path,
                    )
                )

        finally:
            driver.quit()

        log(f"[Kompas] Done. {len(results)} article(s) scraped.")
        return results
