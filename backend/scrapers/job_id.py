import hashlib
import re
from urllib.parse import urlparse

from backend.scrapers.base import ScrapedJob


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def compute_job_id(job: ScrapedJob, company_id: int) -> str:
    if job.ats_id:
        return job.ats_id

    if job.url:
        canonical = _canonical_url(job.url)
        return hashlib.sha256(canonical.encode()).hexdigest()

    composite = f"{company_id}:{_normalize(job.title)}:{_normalize(job.location or '')}"
    return hashlib.sha256(composite.encode()).hexdigest()
