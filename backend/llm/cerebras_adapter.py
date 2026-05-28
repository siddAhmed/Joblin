import json
from cerebras.cloud.sdk import AsyncCerebras

from backend.llm.protocol import CriteriaConfig, FeedbackExample, FilterResult
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt


class CerebrasAdapter:
    def __init__(self, api_key: str):
        self._client = AsyncCerebras(api_key=api_key)
        self._model = "llama-3.3-70b"
        self.last_usage: dict = {}

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
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=128,
        )
        if response.usage:
            self.last_usage = {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            }
        raw = response.choices[0].message.content or ""
        try:
            parsed = json.loads(raw)
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
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        if response.usage:
            self.last_usage = {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            }
        return response.choices[0].message.content or ""
