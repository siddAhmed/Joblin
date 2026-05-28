import re

from backend.scrapers.base import ScrapedJob

SENIORITY_PATTERNS = {
    "junior": r"\bjunior\b|\bjr\.?\b|\bentry.level\b",
    "mid": r"\bmid\b|\bintermediate\b",
    "senior": r"\bsenior\b|\bsr\.?\b",
    "staff": r"\bstaff\b",
    "principal": r"\bprincipal\b",
    "lead": r"\blead\b",
    "manager": r"\bmanager\b|\bem\b|\beng\.?\s?mgr\b",
}


def _infer_seniority(title: str) -> str | None:
    lower = title.lower()
    for level, pattern in SENIORITY_PATTERNS.items():
        if re.search(pattern, lower):
            return level
    return None


def passes_heuristic(job: ScrapedJob, criteria: dict) -> bool:
    title_lower = job.title.lower()

    if criteria.get("title_allowlist"):
        if not re.search(criteria["title_allowlist"], title_lower):
            return False

    if criteria.get("title_denylist"):
        if re.search(criteria["title_denylist"], title_lower):
            return False

    loc = (job.location or "").lower()
    if criteria.get("location_allowlist") and loc:
        if not re.search(criteria["location_allowlist"], loc):
            return False
    if criteria.get("location_denylist") and loc:
        if re.search(criteria["location_denylist"], loc):
            return False

    allowed_seniority: list = criteria.get("seniority_allowlist", [])
    if allowed_seniority:
        inferred = _infer_seniority(job.title)
        if inferred and inferred not in allowed_seniority:
            return False

    desc_lower = (job.raw_description or "").lower()
    for kw in criteria.get("exclusion_keywords", []):
        if kw.lower() in desc_lower:
            return False

    return True
