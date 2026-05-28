import httpx
from backend.scrapers.base import ScrapedJob, clean_description


async def fetch_workable_jobs(identifier: str) -> list[ScrapedJob]:
    url = f"https://{identifier}.workable.com/spi/v3/jobs"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    jobs = []
    for raw in data.get("jobs", []):
        jobs.append(
            ScrapedJob(
                ats_id=raw.get("shortcode"),
                title=raw.get("title", ""),
                location=raw.get("location", {}).get("city"),
                url=raw.get("url", ""),
                raw_description=clean_description(raw.get("description", "")),
            )
        )
    return jobs
