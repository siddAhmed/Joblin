from unittest.mock import AsyncMock, patch


async def test_start_run_returns_run_id(client):
    with patch("backend.routers.runs.execute_run", new_callable=AsyncMock):
        response = await client.post("/api/runs", json={})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] == "running"


async def test_list_runs_empty(client):
    response = await client.get("/api/runs")
    assert response.status_code == 200
    assert response.json() == []
