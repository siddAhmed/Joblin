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
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data

    with patch("backend.scrapers.greenhouse.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        jobs = await fetch_greenhouse_jobs("stripe")

    assert len(jobs) == 1
    assert jobs[0].ats_id == "9001"
    assert jobs[0].title == "Senior Backend Engineer"
    assert "backend engineer" in jobs[0].raw_description.lower()
