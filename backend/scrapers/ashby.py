import httpx
from backend.scrapers.base import ScrapedJob, clean_description


async def fetch_ashby_jobs(identifier: str) -> list[ScrapedJob]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{identifier}"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    jobs = []
    for raw in data.get("jobs", []):
        locations = raw.get("jobPostingLocations", [])
        location = locations[0].get("name") if locations else None
        jobs.append(
            ScrapedJob(
                ats_id=raw.get("id"),
                title=raw.get("title", ""),
                location=location,
                url=raw.get("jobUrl", ""),
                raw_description=clean_description(raw.get("descriptionHtml", "")),
            )
        )
    return jobs
