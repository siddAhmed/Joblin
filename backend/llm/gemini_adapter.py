import json
from google import genai

from backend.llm.protocol import CriteriaConfig, FeedbackExample, FilterResult
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt


class GeminiAdapter:
    FILTER_MODEL = "gemini-2.0-flash-lite"
    SUMMARIZE_MODEL = "gemini-2.0-flash-lite"

    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    async def filter(
        self,
        title: str,
        company_name: str,
        location: str | None,
        description: str,
        criteria: CriteriaConfig,
        negative_examples: list[FeedbackExample],
    ) -> FilterResult:
        system, user = build_filter_prompt(title, company_name, location, description, criteria, negative_examples)
        prompt = f"{system}\n\n{user}"
        response = await self._client.aio.models.generate_content(
            model=self.FILTER_MODEL,
            contents=prompt,
        )
        raw = response.text or ""
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            parsed = json.loads(raw[start:end])
            return FilterResult(score=float(parsed["score"]), reasoning=parsed.get("reasoning", ""))
        except Exception:
            return FilterResult(score=0.0, reasoning=f"parse error: {raw[:80]}")

    async def summarize(
        self,
        title: str,
        company_name: str,
        description: str,
        score: float,
    ) -> str:
        prompt = build_summarize_prompt(title, company_name, description, score)
        response = await self._client.aio.models.generate_content(
            model=self.SUMMARIZE_MODEL,
            contents=prompt,
        )
        return response.text or ""
