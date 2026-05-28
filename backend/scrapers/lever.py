import httpx
from backend.scrapers.base import ScrapedJob


async def fetch_lever_jobs(identifier: str) -> list[ScrapedJob]:
    url = f"https://api.lever.co/v0/postings/{identifier}?mode=json"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    jobs = []
    for raw in data:
        jobs.append(
            ScrapedJob(
                ats_id=raw.get("id"),
                title=raw.get("text", ""),
                location=raw.get("categories", {}).get("location"),
                url=raw.get("hostedUrl", ""),
                raw_description=raw.get("descriptionPlain", ""),
            )
        )
    return jobs
