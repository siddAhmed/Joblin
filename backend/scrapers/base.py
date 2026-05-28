from dataclasses import dataclass


@dataclass
class ScrapedJob:
    ats_id: str | None
    title: str
    location: str | None
    url: str
    raw_description: str = ""
