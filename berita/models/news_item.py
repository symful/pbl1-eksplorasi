from dataclasses import dataclass

@dataclass
class NewsItem:
    title: str
    date: str
    link: str
    portal: str
