import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_reset_returns_200_with_deleted_counts(client: AsyncClient):
    resp = await client.post("/api/admin/reset")
    assert resp.status_code == 200
    data = resp.json()
    assert "deleted" in data
    assert set(data["deleted"].keys()) == {
        "feedback_examples", "matches", "run_company_results", "jobs", "runs"
    }
    for v in data["deleted"].values():
        assert isinstance(v, int)


@pytest.mark.anyio
async def test_reset_on_empty_db_returns_zeros(client: AsyncClient):
    resp = await client.post("/api/admin/reset")
    assert resp.status_code == 200
    data = resp.json()
    for v in data["deleted"].values():
        assert v == 0


@pytest.mark.anyio
async def test_reset_is_idempotent(client: AsyncClient):
    resp1 = await client.post("/api/admin/reset")
    resp2 = await client.post("/api/admin/reset")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    for v in resp2.json()["deleted"].values():
        assert v == 0
