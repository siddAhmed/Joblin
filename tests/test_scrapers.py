import pytest
from unittest.mock import AsyncMock, patch

from backend.scrapers.probe import probe_ats, ProbeResult, ProbeAttempt
from backend.scrapers.job_id import compute_job_id
from backend.scrapers.base import ScrapedJob
from backend.scrapers.heuristics import passes_heuristic
from backend.scrapers.greenhouse import fetch_greenhouse_jobs


async def test_probe_detects_greenhouse():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"jobs": []}

    with patch("backend.scrapers.probe.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        result = await probe_ats("https://stripe.com/jobs", "stripe")

    assert result.ats_type == "greenhouse"
    assert result.identifier == "stripe"


async def test_probe_returns_crawl4ai_when_all_fail():
    mock_response = AsyncMock()
    mock_response.status_code = 404

    with patch("backend.scrapers.probe.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        result = await probe_ats("https://example.com/careers", "example")

    assert result.ats_type == "crawl4ai"
    assert len(result.probe_attempts) == 6


def test_compute_job_id_uses_ats_id_first():
    job = ScrapedJob(ats_id="abc123", title="Backend Engineer", location="Remote", url="https://example.com/jobs/abc123")
    result = compute_job_id(job, company_id=1)
    assert result == "abc123"


def test_compute_job_id_falls_back_to_url_hash():
    job = ScrapedJob(ats_id=None, title="Backend Engineer", location="Remote", url="https://example.com/jobs/123?ref=x")
    result = compute_job_id(job, company_id=1)
    assert len(result) == 64  # SHA-256 hex


def test_heuristic_passes_matching_title():
    criteria = {
        "title_allowlist": "backend|platform",
        "title_denylist": "intern",
        "location_allowlist": "",
        "location_denylist": "",
        "seniority_allowlist": ["senior", "staff"],
        "exclusion_keywords": [],
    }
    job = ScrapedJob(ats_id="1", title="Senior Backend Engineer", location="Remote", url="https://x.com")
    assert passes_heuristic(job, criteria) is True


def test_heuristic_blocks_denylist_title():
    criteria = {
        "title_allowlist": "backend",
        "title_denylist": "intern",
        "location_allowlist": "",
        "location_denylist": "",
        "seniority_allowlist": ["senior"],
        "exclusion_keywords": [],
    }
    job = ScrapedJob(ats_id="2", title="Backend Intern", location="Remote", url="https://x.com")
    assert passes_heuristic(job, criteria) is False


async def test_greenhouse_returns_scraped_jobs():
    mock_data = {
        "jobs": [
            {
                "id": 9001,
                "title": "Senior Backend Engineer",
                "location": {"name": "Remote"},
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/9001",
                "content": "<p>We are hiring a backend engineer.</p>",
            }
        ]
    }
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = mock_data

    with patch("backend.scrapers.greenhouse.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        jobs = await fetch_greenhouse_jobs("stripe")

    assert len(jobs) == 1
    assert jobs[0].ats_id == "9001"
    assert jobs[0].title == "Senior Backend Engineer"
    assert "backend engineer" in jobs[0].raw_description.lower()


from backend.scrapers.lever import fetch_lever_jobs


async def test_lever_returns_scraped_jobs():
    from unittest.mock import MagicMock
    mock_data = [
        {
            "id": "abc-123",
            "text": "Senior Engineer",
            "categories": {"location": "Remote"},
            "hostedUrl": "https://jobs.lever.co/stripe/abc-123",
            "descriptionPlain": "Great Python role.",
        }
    ]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = mock_data

    with patch("backend.scrapers.lever.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        jobs = await fetch_lever_jobs("stripe")

    assert len(jobs) == 1
    assert jobs[0].ats_id == "abc-123"
    assert jobs[0].title == "Senior Engineer"


from backend.scrapers.ashby import fetch_ashby_jobs


async def test_ashby_returns_scraped_jobs():
    from unittest.mock import MagicMock
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
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = mock_data

    with patch("backend.scrapers.ashby.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        jobs = await fetch_ashby_jobs("stripe")

    assert len(jobs) == 1
    assert jobs[0].ats_id == "ashby-001"
    assert jobs[0].title == "Staff Engineer"


from backend.scrapers.workday import _extract_workday_tenant


def test_workday_tenant_extraction():
    tenant, wd_num = _extract_workday_tenant(
        "https://stripe.wd5.myworkdayjobs.com/en-US/External/jobs"
    )
    assert tenant == "stripe"
    assert wd_num == "wd5"


def test_workday_tenant_extraction_fails_gracefully():
    tenant, wd_num = _extract_workday_tenant("https://example.com/careers")
    assert tenant is None


from backend.scrapers.crawl4ai import fetch_crawl4ai_jobs


async def test_crawl4ai_returns_empty_on_no_jobs():
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.markdown = "No open positions at this time."

    with patch("backend.scrapers.crawl4ai.AsyncWebCrawler") as MockCrawler:
        instance = MockCrawler.return_value.__aenter__.return_value
        instance.arun = AsyncMock(return_value=mock_result)
        jobs = await fetch_crawl4ai_jobs("https://example.com/careers", css_selector=None)

    assert jobs == []
