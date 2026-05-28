# Joblin Phase 4 -- Remaining ATS Adapters + Crawl4AI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Lever, Ashby, Workable, SmartRecruiters, Workday, and Crawl4AI adapters. Wire them into `pipeline._fetch_jobs`. CSS selector overrides work from the UI.

**Prerequisite:** Phase 3 complete and all tests passing.

**Tech Stack:** httpx, crawl4ai, playwright, pytest with AsyncMock.

---

## File Map

| File | Responsibility |
|---|---|
| `backend/scrapers/lever.py` | Lever adapter |
| `backend/scrapers/ashby.py` | Ashby adapter |
| `backend/scrapers/workable.py` | Workable adapter |
| `backend/scrapers/smartrecruiters.py` | SmartRecruiters adapter |
| `backend/scrapers/workday.py` | Workday adapter |
| `backend/scrapers/crawl4ai.py` | Crawl4AI + Playwright fallback |
| `backend/pipeline.py` | Update `_fetch_jobs` to dispatch all adapter types |

---

## Task 19: Lever adapter

**Files:**
- Create: `backend/scrapers/lever.py`

- [ ] **Step 1: Add test**

Append to `tests/test_scrapers.py`:

```python
from backend.scrapers.lever import fetch_lever_jobs


async def test_lever_returns_scraped_jobs():
    mock_data = [
        {
            "id": "abc-123",
            "text": "Senior Engineer",
            "categories": {"location": "Remote"},
            "hostedUrl": "https://jobs.lever.co/stripe/abc-123",
            "descriptionPlain": "Great Python role.",
        }
    ]
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data

    with patch("backend.scrapers.lever.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        jobs = await fetch_lever_jobs("stripe")

    assert len(jobs) == 1
    assert jobs[0].ats_id == "abc-123"
    assert jobs[0].title == "Senior Engineer"
```

- [ ] **Step 2: Run to verify it fails**

```powershell
.venv/Scripts/pytest tests/test_scrapers.py::test_lever_returns_scraped_jobs -v
```

Expected: ImportError.

- [ ] **Step 3: Write `backend/scrapers/lever.py`**

```python
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
```

- [ ] **Step 4: Run test**

```powershell
.venv/Scripts/pytest tests/test_scrapers.py::test_lever_returns_scraped_jobs -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/scrapers/lever.py
git commit -m "feat: Lever ATS adapter"
```

---

## Task 20: Ashby adapter

**Files:**
- Create: `backend/scrapers/ashby.py`

- [ ] **Step 1: Add test**

Append to `tests/test_scrapers.py`:

```python
from backend.scrapers.ashby import fetch_ashby_jobs


async def test_ashby_returns_scraped_jobs():
    mock_data = {
        "jobs": [
            {
                "id": "ashby-001",
                "title": "Staff Engineer",
                "jobPostingLocations": [{"name": "San Francisco, CA"}],
                "jobUrl": "https://jobs.ashbyhq.com/stripe/ashby-001",
                "descriptionHtml": "<p>Great role at Stripe.</p>",
            }
        ]
    }
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data

    with patch("backend.scrapers.ashby.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        jobs = await fetch_ashby_jobs("stripe")

    assert len(jobs) == 1
    assert jobs[0].ats_id == "ashby-001"
    assert jobs[0].title == "Staff Engineer"
```

- [ ] **Step 2: Write `backend/scrapers/ashby.py`**

```python
import re
import httpx
from backend.scrapers.base import ScrapedJob


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


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
                raw_description=_strip_html(raw.get("descriptionHtml", "")),
            )
        )
    return jobs
```

- [ ] **Step 3: Run test**

```powershell
.venv/Scripts/pytest tests/test_scrapers.py::test_ashby_returns_scraped_jobs -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add backend/scrapers/ashby.py
git commit -m "feat: Ashby ATS adapter"
```

---

## Task 21: Workable + SmartRecruiters + Workday adapters

**Files:**
- Create: `backend/scrapers/workable.py`
- Create: `backend/scrapers/smartrecruiters.py`
- Create: `backend/scrapers/workday.py`

- [ ] **Step 1: Write `backend/scrapers/workable.py`**

```python
import httpx
from backend.scrapers.base import ScrapedJob


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
                raw_description=raw.get("description", ""),
            )
        )
    return jobs
```

- [ ] **Step 2: Write `backend/scrapers/smartrecruiters.py`**

```python
import httpx
from backend.scrapers.base import ScrapedJob


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
                raw_description=raw.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", ""),
            )
        )
    return jobs
```

- [ ] **Step 3: Write `backend/scrapers/workday.py`**

```python
import re
import httpx
from backend.scrapers.base import ScrapedJob


def _extract_workday_tenant(url: str) -> tuple[str | None, str | None]:
    # Pattern: https://{company}.wd{N}.myworkdayjobs.com/en-US/{board}/jobs
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
```

- [ ] **Step 4: Add basic tests for all three**

Append to `tests/test_scrapers.py`:

```python
from backend.scrapers.workable import fetch_workable_jobs
from backend.scrapers.smartrecruiters import fetch_smartrecruiters_jobs
from backend.scrapers.workday import fetch_workday_jobs, _extract_workday_tenant


def test_workday_tenant_extraction():
    tenant, wd_num = _extract_workday_tenant(
        "https://stripe.wd5.myworkdayjobs.com/en-US/External/jobs"
    )
    assert tenant == "stripe"
    assert wd_num == "wd5"


def test_workday_tenant_extraction_fails_gracefully():
    tenant, wd_num = _extract_workday_tenant("https://example.com/careers")
    assert tenant is None
```

- [ ] **Step 5: Run tests**

```powershell
.venv/Scripts/pytest tests/test_scrapers.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/scrapers/workable.py backend/scrapers/smartrecruiters.py backend/scrapers/workday.py
git commit -m "feat: Workable, SmartRecruiters, and Workday ATS adapters"
```

---

## Task 22: Crawl4AI + Playwright fallback adapter

**Files:**
- Create: `backend/scrapers/crawl4ai.py`

- [ ] **Step 1: Install Playwright browsers (run once after pip install)**

```powershell
.venv/Scripts/playwright install chromium
```

Expected: downloads Chromium browser (~150MB).

- [ ] **Step 2: Add test**

Append to `tests/test_scrapers.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from backend.scrapers.crawl4ai import fetch_crawl4ai_jobs


async def test_crawl4ai_returns_empty_on_no_jobs():
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.markdown = "No open positions at this time."

    with patch("backend.scrapers.crawl4ai.AsyncWebCrawler") as MockCrawler:
        instance = MockCrawler.return_value.__aenter__.return_value
        instance.arun = AsyncMock(return_value=mock_result)
        jobs = await fetch_crawl4ai_jobs("https://example.com/careers", css_selector=None)

    assert jobs == []
```

- [ ] **Step 3: Write `backend/scrapers/crawl4ai.py`**

Use Context7 to fetch the current crawl4ai async API before finalizing:
```
# Context7: mcp__context7__resolve-library-id("crawl4ai")
# then mcp__context7__query-docs(id, "AsyncWebCrawler arun css selector extraction")
```

```python
import re
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from backend.scrapers.base import ScrapedJob


def _extract_jobs_from_markdown(markdown: str) -> list[ScrapedJob]:
    jobs = []
    lines = [l.strip() for l in markdown.split("\n") if l.strip()]
    for line in lines:
        # Look for lines that look like job titles (linked text followed by location hints)
        link_match = re.match(r"\[(.+?)\]\((https?://[^\)]+)\)", line)
        if link_match:
            title = link_match.group(1)
            url = link_match.group(2)
            # Skip nav links, short lines
            if len(title) < 8 or any(w in title.lower() for w in ["home", "about", "blog", "sign in"]):
                continue
            jobs.append(ScrapedJob(ats_id=None, title=title, location=None, url=url))
    return jobs


async def fetch_crawl4ai_jobs(careers_url: str, css_selector: str | None) -> list[ScrapedJob]:
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    if css_selector:
        config.css_selector = css_selector

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=careers_url, config=config)

    if not result.success:
        raise RuntimeError(f"Crawl4AI failed for {careers_url}: {result.error_message}")

    return _extract_jobs_from_markdown(result.markdown or "")
```

- [ ] **Step 4: Run test**

```powershell
.venv/Scripts/pytest tests/test_scrapers.py::test_crawl4ai_returns_empty_on_no_jobs -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/scrapers/crawl4ai.py
git commit -m "feat: Crawl4AI Playwright fallback adapter"
```

---

## Task 23: Wire all adapters into pipeline `_fetch_jobs`

**Files:**
- Modify: `backend/pipeline.py`

- [ ] **Step 1: Replace `_fetch_jobs` in `pipeline.py` with the full dispatch function**

```python
async def _fetch_jobs(company: Company) -> list[ScrapedJob]:
    from backend.scrapers import (
        greenhouse as gh_mod,
        lever as lever_mod,
        ashby as ashby_mod,
        workable as workable_mod,
        smartrecruiters as sr_mod,
        workday as wd_mod,
        crawl4ai as c4ai_mod,
    )

    ats = company.ats_type.value if company.ats_type else "crawl4ai"

    if ats == "greenhouse":
        return await gh_mod.fetch_greenhouse_jobs(company.ats_identifier or "")
    if ats == "lever":
        return await lever_mod.fetch_lever_jobs(company.ats_identifier or "")
    if ats == "ashby":
        return await ashby_mod.fetch_ashby_jobs(company.ats_identifier or "")
    if ats == "workable":
        return await workable_mod.fetch_workable_jobs(company.ats_identifier or "")
    if ats == "smartrecruiters":
        return await sr_mod.fetch_smartrecruiters_jobs(company.ats_identifier or "")
    if ats == "workday":
        return await wd_mod.fetch_workday_jobs(company.custom_api_url or company.careers_url)
    if ats == "custom":
        # Custom ATS URL -- use Crawl4AI with optional CSS selector
        return await c4ai_mod.fetch_crawl4ai_jobs(
            company.custom_api_url or company.careers_url,
            css_selector=company.css_selector,
        )
    # Default: crawl4ai
    return await c4ai_mod.fetch_crawl4ai_jobs(
        company.careers_url,
        css_selector=company.css_selector,
    )
```

- [ ] **Step 2: Run all tests**

```powershell
.venv/Scripts/pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```powershell
git add backend/pipeline.py backend/scrapers/
git commit -m "feat: wire all ATS adapters and Crawl4AI into pipeline dispatch"
```

---

**Phase 4 complete.** All six ATS types and the Crawl4AI fallback are implemented and wired into the pipeline. Proceed to Phase 5.
