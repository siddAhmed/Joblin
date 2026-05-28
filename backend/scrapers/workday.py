import re
import httpx
from backend.scrapers.base import ScrapedJob


def _extract_workday_tenant(url: str) -> tuple[str | None, str | None]:
    match = re.search(r"https://([^.]+)\.(wd\d+)\.myworkdayjobs\.com", url)
    if match:
        return match.group(1), match.group(2)
    return None, None


async def fetch_workday_jobs(careers_url: str) -> list[ScrapedJob]:
    tenant, wd_num = _extract_workday_tenant(careers_url)
    if not tenant or not wd_num:
        return []

    api_url = f"https://{tenant}.{wd_num}.myworkdayjobs.com/wday/cxs/{tenant}/External/jobs"
    headers = {"Content-Type": "application/json"}
    payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.post(api_url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    jobs = []
    for raw in data.get("jobPostings", []):
        job_path = raw.get("externalPath", "")
        job_url = f"https://{tenant}.{wd_num}.myworkdayjobs.com{job_path}" if job_path else careers_url
        jobs.append(
            ScrapedJob(
                ats_id=raw.get("bulletFields", [None])[0],
                title=raw.get("title", ""),
                location=raw.get("locationsText"),
                url=job_url,
                raw_description=raw.get("jobDescription", ""),
            )
        )
    return jobs
