from unittest.mock import AsyncMock, MagicMock, patch


async def test_validate_keys_all_valid(client):
    mock_resp = MagicMock()
    with patch("backend.routers.settings.AsyncGroq") as mock_groq, \
         patch("backend.routers.settings.AsyncCerebras") as mock_cerebras:
        mock_groq.return_value.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_cerebras.return_value.chat.completions.create = AsyncMock(return_value=mock_resp)
        response = await client.post("/api/settings/validate-keys", json={
            "groq_api_key": "gsk_valid",
            "cerebras_api_key": "csk_valid",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["groq"]["valid"] is True
    assert data["groq"]["error"] is None
    assert data["cerebras"]["valid"] is True
    assert data["cerebras"]["error"] is None
    assert "gemini" not in data


async def test_validate_keys_invalid_groq_returns_422(client):
    mock_resp = MagicMock()
    with patch("backend.routers.settings.AsyncGroq") as mock_groq, \
         patch("backend.routers.settings.AsyncCerebras") as mock_cerebras:
        mock_groq.return_value.chat.completions.create = AsyncMock(
            side_effect=Exception("Invalid API key")
        )
        mock_cerebras.return_value.chat.completions.create = AsyncMock(return_value=mock_resp)
        response = await client.post("/api/settings/validate-keys", json={
            "groq_api_key": "gsk_bad",
            "cerebras_api_key": "csk_valid",
        })
    assert response.status_code == 422
    data = response.json()
    assert data["groq"]["valid"] is False
    assert "Invalid API key" in data["groq"]["error"]
    assert data["cerebras"]["valid"] is True


async def test_validate_keys_empty_fields_skipped(client):
    response = await client.post("/api/settings/validate-keys", json={
        "groq_api_key": "",
        "cerebras_api_key": "",
    })
    assert response.status_code == 200
    assert response.json() == {}


async def test_validate_keys_optional_gemini_included_when_provided(client):
    mock_resp = MagicMock()
    with patch("backend.routers.settings.AsyncGroq") as mock_groq, \
         patch("backend.routers.settings.AsyncCerebras") as mock_cerebras, \
         patch("backend.routers.settings.genai") as mock_genai:
        mock_groq.return_value.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_cerebras.return_value.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        response = await client.post("/api/settings/validate-keys", json={
            "groq_api_key": "gsk_valid",
            "cerebras_api_key": "csk_valid",
            "gemini_api_key": "AIza_valid",
        })
    assert response.status_code == 200
    data = response.json()
    assert "gemini" in data
    assert data["gemini"]["valid"] is True
