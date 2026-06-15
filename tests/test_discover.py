import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.scrapers.discover import discover_company
from backend.scrapers.probe import ProbeResult


async def test_catalog_fastpath_skips_web_search():
    """When name matches catalog, web search is skipped and probe_ats is called with the known URL."""
    mock_probe = ProbeResult(ats_type="greenhouse", identifier="google", probe_attempts=[])

    with (
        patch("backend.scrapers.discover.probe_ats", return_value=mock_probe) as mock_pa,
        patch("backend.scrapers.discover._update_status", new_callable=AsyncMock),
        patch("backend.scrapers.discover._resolve", new_callable=AsyncMock) as mock_resolve,
        patch("backend.scrapers.discover._search_web", new_callable=AsyncMock) as mock_search,
        patch("backend.scrapers.discover._make_client", new_callable=AsyncMock),
    ):
        await discover_company(1, "Google", user_id=1)

    mock_search.assert_not_called()
    mock_resolve.assert_awaited_once_with(1, "greenhouse", "google", "https://careers.google.com/")


async def test_catalog_lookup_case_insensitive():
    """Catalog lookup is case-insensitive ('google' matches 'Google')."""
    mock_probe = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])

    with (
        patch("backend.scrapers.discover.probe_ats", return_value=mock_probe),
        patch("backend.scrapers.discover._update_status", new_callable=AsyncMock),
        patch("backend.scrapers.discover._resolve", new_callable=AsyncMock) as mock_resolve,
        patch("backend.scrapers.discover._search_web", new_callable=AsyncMock) as mock_search,
        patch("backend.scrapers.discover._make_client", new_callable=AsyncMock),
    ):
        await discover_company(1, "google", user_id=1)

    mock_search.assert_not_called()
    mock_resolve.assert_awaited_once()


async def test_unknown_company_probes_candidates():
    """Unknown company triggers web search, LLM filter, and ATS probe."""
    mock_probe_crawl = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])
    mock_probe_ashby = ProbeResult(ats_type="ashby", identifier="acmecorp", probe_attempts=[])

    # Heuristics produce 3 URLs; combined with 1 search result = 4 candidates.
    # _llm_filter passes them all through. probe_ats hits crawl4ai on the first,
    # ashby on the second -- discover should resolve with ashby immediately.
    heuristic_urls = [
        "https://careers.acmecorp.com/",
        "https://jobs.acmecorp.com/",
        "https://acmecorp.com/careers",
    ]

    with (
        patch("backend.scrapers.discover._search_web", new_callable=AsyncMock,
              return_value=["https://acmecorp.io/jobs"]),
        patch("backend.scrapers.discover._heuristic_candidates", return_value=heuristic_urls),
        patch("backend.scrapers.discover._llm_filter", new_callable=AsyncMock,
              side_effect=lambda name, candidates, client: candidates),
        patch("backend.scrapers.discover.probe_ats",
              side_effect=[mock_probe_crawl, mock_probe_ashby, mock_probe_crawl, mock_probe_crawl]),
        patch("backend.scrapers.discover._update_status", new_callable=AsyncMock),
        patch("backend.scrapers.discover._resolve", new_callable=AsyncMock) as mock_resolve,
        patch("backend.scrapers.discover._make_client", new_callable=AsyncMock),
    ):
        await discover_company(42, "Acme Corp", user_id=1)

    mock_resolve.assert_awaited_once()
    call_args = mock_resolve.call_args[0]
    assert call_args[0] == 42
    assert call_args[1] == "ashby"


async def test_timeout_marks_company_failed():
    """When discovery exceeds 90s, company is marked failed."""
    async def slow(*args, **kwargs):
        raise asyncio.TimeoutError()

    with (
        patch("backend.scrapers.discover._run_discovery", side_effect=slow),
        patch("backend.scrapers.discover._update_status", new_callable=AsyncMock) as mock_status,
    ):
        await discover_company(99, "Slow Corp", user_id=1)

    mock_status.assert_awaited_with(99, "Could not find — paste URL manually", "failed")


async def test_no_candidates_marks_failed():
    """When web search and heuristics return nothing, mark failed."""
    with (
        patch("backend.scrapers.discover._search_web", new_callable=AsyncMock, return_value=[]),
        patch("backend.scrapers.discover._heuristic_candidates", return_value=[]),
        patch("backend.scrapers.discover._update_status", new_callable=AsyncMock) as mock_status,
        patch("backend.scrapers.discover._resolve", new_callable=AsyncMock),
        patch("backend.scrapers.discover._make_client", new_callable=AsyncMock),
    ):
        await discover_company(7, "Nonexistent Co", user_id=1)

    mock_status.assert_awaited_with(7, "Could not find — paste URL manually", "failed")
