from dataclasses import dataclass, field
from typing import List


@dataclass
class ContentBlock:
    block_type: str
    value: str


@dataclass
class NewsItem:
    title: str
    date: str
    link: str
    portal: str
    content_blocks: List[ContentBlock] = field(default_factory=list)
    image_url: str = ""
    image_path: str = ""

    def plain_text(self) -> str:
        return "\n\n".join(
            b.value for b in self.content_blocks if b.block_type == "text"
        )

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "date": self.date,
            "link": self.link,
            "portal": self.portal,
            "content_blocks": [
                {"type": b.block_type, "value": b.value} for b in self.content_blocks
            ],
            "image_url": self.image_url,
            "image_path": self.image_path,
        }
