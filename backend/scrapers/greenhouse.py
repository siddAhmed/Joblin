import inspect
import re
import httpx

from backend.scrapers.base import ScrapedJob


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


async def fetch_greenhouse_jobs(identifier: str) -> list[ScrapedJob]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{identifier}/jobs?content=true"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        if resp.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {resp.status_code}", request=resp.request, response=resp
            )
        raw_data = resp.json()
        data = await raw_data if inspect.isawaitable(raw_data) else raw_data

    jobs = []
    for raw in data.get("jobs", []):
        jobs.append(
            ScrapedJob(
                ats_id=str(raw["id"]),
                title=raw.get("title", ""),
                location=raw.get("location", {}).get("name"),
                url=raw.get("absolute_url", ""),
                raw_description=_strip_html(raw.get("content", "")),
            )
        )
    return jobs
