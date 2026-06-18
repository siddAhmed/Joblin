from unittest.mock import patch
from backend.scrapers.probe import ProbeResult


async def test_health_returns_ok(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_stats_returns_zeros_on_empty_db(client):
    response = await client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_companies"] == 0
    assert data["todays_matches"] == 0
    assert data["quarantine_count"] == 0


async def test_onboarding_needed_on_fresh_user(client):
    response = await client.get("/api/onboarding-status")
    assert response.status_code == 200
    assert response.json()["needs_onboarding"] is True


async def test_onboarding_needed_when_keys_missing_but_has_companies(client):
    mock_probe = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        await client.post("/api/companies", json={"name": "Acme", "careers_url": "https://acme.com/jobs"})

    response = await client.get("/api/onboarding-status")
    assert response.status_code == 200
    assert response.json()["needs_onboarding"] is True


async def test_onboarding_not_needed_when_keys_and_companies_exist(client):
    mock_probe = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        await client.post("/api/companies", json={"name": "Acme", "careers_url": "https://acme.com/jobs"})
    await client.patch("/api/settings", json={
        "groq_api_key": "gsk_test",
        "cerebras_api_key": "csk_test",
    })

    response = await client.get("/api/onboarding-status")
    assert response.status_code == 200
    assert response.json()["needs_onboarding"] is False
