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
