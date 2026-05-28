import html as _html
import re
from dataclasses import dataclass


def clean_description(raw: str) -> str:
    if not raw:
        return ""
    unescaped = _html.unescape(raw)
    stripped = re.sub(r"<[^>]+>", " ", unescaped)
    return re.sub(r"\s{2,}", " ", stripped).strip()


@dataclass
class ScrapedJob:
    ats_id: str | None
    title: str
    location: str | None
    url: str
    raw_description: str = ""
