import asyncio
from dataclasses import dataclass, field
import httpx


@dataclass
class ProbeAttempt:
    url: str
    status_code: int | None
    error: str | None = None


@dataclass
class ProbeResult:
    ats_type: str
    identifier: str | None
    probe_attempts: list[ProbeAttempt] = field(default_factory=list)


def _slug_from_url(url: str) -> str:
    from urllib.parse import urlparse
    parts = urlparse(url).path.strip("/").split("/")
    return parts[-1] if parts and parts[-1] else url.split("//")[-1].split(".")[0]


async def probe_ats(careers_url: str, name_hint: str) -> ProbeResult:
    url_slug = _slug_from_url(careers_url)
    generic_segments = {"jobs", "careers", "job", "career", "openings", "positions", ""}
    if url_slug and url_slug.lower() not in generic_segments:
        slug = url_slug
    else:
        slug = name_hint.lower().replace(" ", "-")

    candidates = [
        ("greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"),
        ("lever", f"https://api.lever.co/v0/postings/{slug}"),
        ("ashby", f"https://api.ashbyhq.com/posting-api/job-board/{slug}"),
        ("workable", f"https://{slug}.workable.com/spi/v3/jobs"),
        ("smartrecruiters", f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"),
        ("workday", careers_url),
    ]

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:

        async def try_one(ats_type: str, url: str) -> tuple[str, str, int | None, str | None]:
            try:
                resp = await client.get(url)
                return (ats_type, url, resp.status_code, None)
            except Exception as exc:
                return (ats_type, url, None, str(exc))

        results = await asyncio.gather(*[try_one(t, u) for t, u in candidates])

    attempts = [
        ProbeAttempt(url=url, status_code=status_code, error=error)
        for _, url, status_code, error in results
    ]

    for ats_type, _, status_code, _ in results:
        if status_code == 200:
            if ats_type == "workday":
                if "workday.com" in careers_url or "myworkdayjobs.com" in careers_url:
                    return ProbeResult(ats_type="workday", identifier=careers_url, probe_attempts=attempts)
            else:
                return ProbeResult(ats_type=ats_type, identifier=slug, probe_attempts=attempts)

    return ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=attempts)
