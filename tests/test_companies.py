from unittest.mock import AsyncMock, patch
from backend.scrapers.probe import ProbeResult, ProbeAttempt


async def test_list_companies_empty(client):
    response = await client.get("/api/companies")
    assert response.status_code == 200
    assert response.json() == []


async def test_add_company_detects_greenhouse(client):
    mock_probe = ProbeResult(
        ats_type="greenhouse",
        identifier="stripe",
        probe_attempts=[ProbeAttempt(url="https://boards-api.greenhouse.io/v1/boards/stripe/jobs", status_code=200)],
    )
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        response = await client.post("/api/companies", json={"name": "Stripe", "careers_url": "https://stripe.com/jobs"})

    assert response.status_code == 201
    assert response.json()["ats_type"] == "greenhouse"


async def test_delete_company(client):
    mock_probe = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        create_resp = await client.post("/api/companies", json={"name": "Acme", "careers_url": "https://acme.com/jobs"})
    company_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/companies/{company_id}")
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/companies")
    assert list_resp.json() == []
