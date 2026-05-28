import json
from google import genai

from backend.llm.protocol import CriteriaConfig, FeedbackExample, FilterResult
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt


class GeminiAdapter:
    def __init__(self, api_key: str, filter_model: str = "gemini-2.0-flash-lite", summarize_model: str = "gemini-2.0-flash-lite"):
        self._client = genai.Client(api_key=api_key)
        self._filter_model = filter_model
        self._summarize_model = summarize_model
        self.last_usage: dict = {}

    def _record_usage(self, response) -> None:
        meta = getattr(response, "usage_metadata", None)
        if meta:
            prompt = getattr(meta, "prompt_token_count", 0) or 0
            completion = getattr(meta, "candidates_token_count", 0) or 0
            self.last_usage = {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": getattr(meta, "total_token_count", 0) or (prompt + completion),
            }
        else:
            self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

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
            model=self._filter_model,
            contents=prompt,
        )
        self._record_usage(response)
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
            model=self._summarize_model,
            contents=prompt,
        )
        self._record_usage(response)
        return response.text or ""
