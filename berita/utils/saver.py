import csv
import json
import os
from urllib.parse import urlparse

import requests


class DataSaver:
    OUTPUT_DIR = "output"
    IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")

    @classmethod
    def _ensure_dirs(cls):
        os.makedirs(cls.OUTPUT_DIR, exist_ok=True)
        os.makedirs(cls.IMAGES_DIR, exist_ok=True)

    @classmethod
    def save_to_json(cls, data, filename="berita.json"):
        cls._ensure_dirs()
        filepath = os.path.join(cls.OUTPUT_DIR, filename)
        records = [item.to_dict() for item in data]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    @classmethod
    def save_to_csv(cls, data, filename="berita.csv"):
        if not data:
            return
        cls._ensure_dirs()
        filepath = os.path.join(cls.OUTPUT_DIR, filename)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "title",
                    "date",
                    "link",
                    "portal",
                    "content",
                    "image_url",
                    "image_path",
                ],
            )
            writer.writeheader()
            for item in data:
                writer.writerow(
                    {
                        "title": item.title,
                        "date": item.date,
                        "link": item.link,
                        "portal": item.portal,
                        "content": item.plain_text(),
                        "image_url": item.image_url,
                        "image_path": item.image_path,
                    }
                )

    @classmethod
    def download_image(cls, url: str, prefix: str = "img") -> str:
        if not url:
            return ""
        cls._ensure_dirs()
        try:
            parsed = urlparse(url)
            ext = os.path.splitext(parsed.path)[1] or ".jpg"
            filename = f"{prefix}_{abs(hash(url)) % 10**8}{ext}"
            filepath = os.path.join(cls.IMAGES_DIR, filename)

            if os.path.exists(filepath):
                return filepath
            response = requests.get(
                url, stream=True, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
            )
            if response.status_code == 200:
                with open(filepath, "wb") as f:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                return filepath
        except Exception:
            pass
        return ""
