import re


def normalize_careers_url(url: str) -> str:
    """Canonical form for deduplication: no protocol, no www., no trailing slash, lowercase."""
    url = url.lower().strip()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    url = url.rstrip("/")
    return url
