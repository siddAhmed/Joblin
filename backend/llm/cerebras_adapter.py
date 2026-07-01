import json
from cerebras.cloud.sdk import AsyncCerebras

from backend.llm.protocol import CriteriaConfig, FeedbackExample, FilterResult
from backend.llm.prompts import (
    build_filter_prompt,
    build_summarize_prompt,
    build_skills_prompt,
    build_job_analysis_prompt,
    build_activity_selection_prompt,
    build_tailor_prompt,
)


class CerebrasAdapter:
    def __init__(self, api_key: str, model: str = "gpt-oss-120b"):
        self._client = AsyncCerebras(api_key=api_key)
        self._model = model
        self.last_usage: dict = {}

    def _record_usage(self, usage) -> None:
        if usage:
            self.last_usage = {
                "prompt_tokens": usage.prompt_tokens or 0,
                "completion_tokens": usage.completion_tokens or 0,
                "total_tokens": usage.total_tokens or 0,
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
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=128,
        )
        self._record_usage(response.usage)
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
        self._record_usage(response.usage)
        return response.choices[0].message.content or ""

    async def extract_skills(self, title: str, description: str) -> list[str]:
        prompt = build_skills_prompt(title, description)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        self._record_usage(response.usage)
        raw = response.choices[0].message.content or ""
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            return json.loads(raw[start:end])
        except Exception:
            return []

    async def analyze_job(self, job_description: str) -> dict:
        system, user = build_job_analysis_prompt(job_description)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=512,
        )
        self._record_usage(response.usage)
        raw = response.choices[0].message.content or ""
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            return json.loads(raw[start:end])
        except Exception:
            return {"required_skills": [], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []}

    async def select_activities(
        self,
        requirements: dict,
        tex_content: str,
        activities_content: str | None,
    ) -> str:
        system, user = build_activity_selection_prompt(requirements, tex_content, activities_content)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=1024,
        )
        self._record_usage(response.usage)
        return response.choices[0].message.content or ""

    async def tailor_resume(self, tex_content: str, selected_items: str) -> str:
        system, user = build_tailor_prompt(tex_content, selected_items)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=4096,
        )
        self._record_usage(response.usage)
        raw = response.choices[0].message.content or ""
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
        return raw.strip()
