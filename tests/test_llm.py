from unittest.mock import AsyncMock, MagicMock
from backend.llm.protocol import CriteriaConfig, FeedbackExample
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt
from backend.llm.groq_adapter import GroqAdapter


def test_filter_prompt_includes_criteria():
    criteria = CriteriaConfig(profile_description="Backend engineer with Python experience")
    system, user = build_filter_prompt(
        title="Senior Backend Engineer",
        company_name="Stripe",
        location="Remote",
        description="We are looking for a backend engineer.",
        criteria=criteria,
        negative_examples=[],
    )
    assert "Backend engineer with Python experience" in user
    assert "Senior Backend Engineer" in user
    assert "score" in system


def test_filter_prompt_includes_negative_examples():
    criteria = CriteriaConfig()
    examples = [FeedbackExample("Acme", "marketing manager", None, "Not a tech role")]
    _, user = build_filter_prompt("Engineer", "Co", None, "desc", criteria, examples)
    assert "marketing manager" in user


def test_summarize_prompt_includes_job_details():
    result = build_summarize_prompt("Staff Engineer", "Linear", "Great team.", 0.85)
    assert "Staff Engineer" in result
    assert "Linear" in result
    assert "0.85" in result


async def test_groq_adapter_returns_filter_result():
    mock_choice = MagicMock()
    mock_choice.message.content = '{"score": 0.85, "reasoning": "Strong backend match"}'
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    adapter = GroqAdapter(api_key="test-key")
    adapter._client.chat.completions.create = AsyncMock(return_value=mock_completion)

    result = await adapter.filter(
        title="Senior Backend Engineer",
        company_name="Stripe",
        location="Remote",
        description="Python, distributed systems",
        criteria=CriteriaConfig(),
        negative_examples=[],
    )

    assert result.score == 0.85
    assert "backend" in result.reasoning.lower()


async def test_groq_adapter_handles_json_parse_error():
    mock_choice = MagicMock()
    mock_choice.message.content = "not json"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    adapter = GroqAdapter(api_key="test-key")
    adapter._client.chat.completions.create = AsyncMock(return_value=mock_completion)

    result = await adapter.filter("Title", "Co", None, "desc", CriteriaConfig(), [])
    assert result.score == 0.0
