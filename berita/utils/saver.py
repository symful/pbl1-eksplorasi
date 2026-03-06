import csv
import json

class DataSaver:
    @staticmethod
    def save_to_csv(data, filename="berita.csv"):
        if not data:
            return
        keys = data[0].__dict__.keys()
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for item in data:
                writer.writerow(item.__dict__)

    @staticmethod
    def save_to_json(data, filename="berita.json"):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump([item.__dict__ for item in data], f, ensure_ascii=False, indent=4)
