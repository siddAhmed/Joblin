import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_usage_returns_provider_stats(client: AsyncClient):
    resp = await client.get("/api/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert "groq" in data["providers"]
    assert "cerebras" in data["providers"]
    assert "gemini" in data["providers"]
    for stats in data["providers"].values():
        assert "total_tokens_all_time" in stats
        assert "total_tokens_7d" in stats
        assert "total_tokens_30d" in stats
        assert "filter_calls" in stats
        assert "summarize_calls" in stats


@pytest.mark.anyio
async def test_usage_recent_runs_empty_initially(client: AsyncClient):
    resp = await client.get("/api/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["recent_runs"] == []
    for stats in data["providers"].values():
        assert stats["total_tokens_all_time"] == 0
