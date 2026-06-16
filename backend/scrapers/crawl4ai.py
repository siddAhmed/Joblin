import asyncio
import re
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from backend.scrapers.base import ScrapedJob

_CRAWL_TIMEOUT = 60.0


def _extract_jobs_from_markdown(markdown: str) -> list[ScrapedJob]:
    jobs = []
    lines = [line.strip() for line in markdown.split("\n") if line.strip()]
    for line in lines:
        link_match = re.match(r"\[(.+?)\]\((https?://[^\)]+)\)", line)
        if link_match:
            title = link_match.group(1)
            url = link_match.group(2)
            if len(title) < 8 or any(w in title.lower() for w in ["home", "about", "blog", "sign in"]):
                continue
            jobs.append(ScrapedJob(ats_id=None, title=title, location=None, url=url))
    return jobs


async def fetch_crawl4ai_jobs(careers_url: str, css_selector: str | None) -> list[ScrapedJob]:
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, css_selector=css_selector)

    async with AsyncWebCrawler() as crawler:
        try:
            result = await asyncio.wait_for(
                crawler.arun(url=careers_url, config=config),
                timeout=_CRAWL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Crawl4AI timed out after {_CRAWL_TIMEOUT}s for {careers_url}")

    if not result.success:
        raise RuntimeError(f"Crawl4AI failed for {careers_url}: {result.error_message}")

    return _extract_jobs_from_markdown(result.markdown or "")
