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


from backend.llm.prompts import (
    build_job_analysis_prompt,
    build_activity_selection_prompt,
    build_tailor_prompt,
)


def test_build_job_analysis_prompt_contains_job_description():
    system, user = build_job_analysis_prompt("We need a Python engineer with FastAPI experience.")
    assert "Python engineer" in user
    assert "required_skills" in system
    assert "JSON" in system


def test_build_activity_selection_prompt_includes_all_sources():
    requirements = {"required_skills": ["Python"], "preferred_skills": [], "key_themes": ["backend"], "seniority_signals": [], "keywords": []}
    tex = r"\documentclass{article}\begin{document}5 years Python\end{document}"
    activities = "## Side Projects\n- Built a CLI tool in Rust"
    system, user = build_activity_selection_prompt(requirements, tex, activities)
    assert "Python" in user
    assert "5 years Python" in user
    assert "CLI tool in Rust" in user
    assert "6-8" in system


def test_build_activity_selection_prompt_handles_none_activities():
    requirements = {"required_skills": ["Go"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []}
    tex = r"\documentclass{article}\begin{document}Go developer\end{document}"
    system, user = build_activity_selection_prompt(requirements, tex, None)
    assert "Go developer" in user
    assert "Activities bank" not in user


def test_build_tailor_prompt_uses_selected_items():
    tex = r"\documentclass{article}\begin{document}Resume\end{document}"
    selected = "1. Python experience\n2. REST API design"
    system, user = build_tailor_prompt(tex, selected)
    assert "Python experience" in user
    assert "REST API design" in user
    assert "job description" not in user.lower()
