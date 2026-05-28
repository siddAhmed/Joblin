from unittest.mock import AsyncMock, MagicMock, patch
from backend.discord import post_match_to_discord


async def test_post_strong_match_includes_mention():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch("backend.discord.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)

        await post_match_to_discord(
            webhook_url="https://discord.com/api/webhooks/test",
            title="Senior Backend Engineer",
            company_name="Stripe",
            location="Remote",
            score=0.91,
            tier="strong",
            summary="Great role.",
            job_url="https://stripe.com/jobs/123",
            mention_type="user",
            mention_id="1234567890",
        )

        call_kwargs = instance.post.call_args
        payload = call_kwargs[1]["json"]
        assert "<@1234567890>" in payload["content"]
        assert payload["embeds"][0]["color"] == 0x22c55e


async def test_post_borderline_match_no_mention():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch("backend.discord.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)

        await post_match_to_discord(
            webhook_url="https://discord.com/api/webhooks/test",
            title="Engineering Manager",
            company_name="Stripe",
            location="Remote",
            score=0.55,
            tier="borderline",
            summary="Borderline match.",
            job_url="https://stripe.com/jobs/456",
            mention_type="none",
            mention_id="",
        )

        call_kwargs = instance.post.call_args
        payload = call_kwargs[1]["json"]
        assert payload.get("content", "") == ""
        assert payload["embeds"][0]["color"] == 0xeab308
