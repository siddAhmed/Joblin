import httpx
from backend.scrapers.base import ScrapedJob, clean_description


async def fetch_smartrecruiters_jobs(identifier: str) -> list[ScrapedJob]:
    url = f"https://api.smartrecruiters.com/v1/companies/{identifier}/postings"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    jobs = []
    for raw in data.get("content", []):
        loc = raw.get("location", {})
        location = f"{loc.get('city', '')}, {loc.get('country', '')}".strip(", ") or None
        jobs.append(
            ScrapedJob(
                ats_id=raw.get("id"),
                title=raw.get("name", ""),
                location=location,
                url=f"https://jobs.smartrecruiters.com/{identifier}/{raw.get('id')}",
                raw_description=clean_description(raw.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", "")),
            )
        )
    return jobs
