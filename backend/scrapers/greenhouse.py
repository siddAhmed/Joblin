import httpx

from backend.scrapers.base import ScrapedJob, clean_description


async def fetch_greenhouse_jobs(identifier: str) -> list[ScrapedJob]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{identifier}/jobs?content=true"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    jobs = []
    for raw in data.get("jobs", []):
        jobs.append(
            ScrapedJob(
                ats_id=str(raw["id"]),
                title=raw.get("title", ""),
                location=raw.get("location", {}).get("name"),
                url=raw.get("absolute_url", ""),
                raw_description=clean_description(raw.get("content", "")),
            )
        )
    return jobs
