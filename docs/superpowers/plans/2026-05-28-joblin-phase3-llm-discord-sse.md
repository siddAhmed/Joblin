# Joblin Phase 3 -- LLM Filter + Summarize + Discord + APScheduler

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Groq for filter scoring, Cerebras for summarization, Discord for notifications, APScheduler for cron scrapes, and the "not interested" feedback loop. After this phase a full end-to-end run (scrape + score + summarize + Discord) works.

**Prerequisite:** Phase 2 complete and all tests passing.

**Tech Stack:** groq SDK (AsyncGroq), cerebras-cloud-sdk (AsyncCerebras), google-genai (aio), httpx, APScheduler 4.x AsyncScheduler, pytest with AsyncMock.

---

## File Map

| File | Responsibility |
|---|---|
| `backend/llm/protocol.py` | `LLMProvider` Protocol, `FilterResult`, `CriteriaConfig` dataclasses |
| `backend/llm/prompts.py` | `build_filter_prompt()`, `build_summarize_prompt()` |
| `backend/llm/groq_adapter.py` | `GroqAdapter` implementing `LLMProvider` |
| `backend/llm/cerebras_adapter.py` | `CerebrasAdapter` |
| `backend/llm/gemini_adapter.py` | `GeminiAdapter` |
| `backend/llm/factory.py` | `get_filter_provider()`, `get_summarize_provider()` |
| `backend/discord.py` | `post_match_to_discord()` |
| `backend/scheduler.py` | APScheduler lifespan integration + cron job |
| `backend/routers/jobs.py` | GET /api/jobs, GET /api/jobs/{id}, POST /api/jobs/{id}/dismiss |
| `backend/routers/matches.py` | GET /api/matches, POST /api/matches/notify |
| `backend/routers/settings.py` | GET/PATCH /api/settings, POST discord/test, POST criteria/test |
| `tests/test_llm.py` | Unit tests for adapters and prompt builders |
| `tests/test_discord.py` | Unit test for Discord notifier |

---

## Task 13: LLM protocol + prompt builders

**Files:**
- Create: `backend/llm/protocol.py`
- Create: `backend/llm/prompts.py`

- [ ] **Step 1: Write `backend/llm/protocol.py`**

```python
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class FeedbackExample:
    company_name: str
    normalized_title: str
    normalized_location: str | None
    summary: str


@dataclass
class CriteriaConfig:
    title_allowlist: str = ""
    title_denylist: str = ""
    location_allowlist: str = ""
    location_denylist: str = ""
    seniority_allowlist: list[str] = field(default_factory=list)
    exclusion_keywords: list[str] = field(default_factory=list)
    profile_description: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "CriteriaConfig":
        return cls(
            title_allowlist=d.get("title_allowlist", ""),
            title_denylist=d.get("title_denylist", ""),
            location_allowlist=d.get("location_allowlist", ""),
            location_denylist=d.get("location_denylist", ""),
            seniority_allowlist=d.get("seniority_allowlist", []),
            exclusion_keywords=d.get("exclusion_keywords", []),
            profile_description=d.get("profile_description", ""),
        )


@dataclass
class FilterResult:
    score: float
    reasoning: str


@runtime_checkable
class LLMProvider(Protocol):
    async def filter(
        self,
        title: str,
        company_name: str,
        location: str | None,
        description: str,
        criteria: CriteriaConfig,
        negative_examples: list[FeedbackExample],
    ) -> FilterResult: ...

    async def summarize(
        self,
        title: str,
        company_name: str,
        description: str,
        score: float,
    ) -> str: ...
```

- [ ] **Step 2: Write `backend/llm/prompts.py`**

```python
from backend.llm.protocol import CriteriaConfig, FeedbackExample


def build_filter_prompt(
    title: str,
    company_name: str,
    location: str | None,
    description: str,
    criteria: CriteriaConfig,
    negative_examples: list[FeedbackExample],
) -> tuple[str, str]:
    criteria_lines = []
    if criteria.profile_description:
        criteria_lines.append(f"Profile: {criteria.profile_description}")
    if criteria.title_allowlist:
        criteria_lines.append(f"Title must match: {criteria.title_allowlist}")
    if criteria.title_denylist:
        criteria_lines.append(f"Title must NOT match: {criteria.title_denylist}")
    if criteria.seniority_allowlist:
        criteria_lines.append(f"Seniority: {', '.join(criteria.seniority_allowlist)}")
    criteria_text = "\n".join(criteria_lines) or "No specific criteria set."

    neg_lines = ""
    if negative_examples:
        bullets = "\n".join(
            f"- {ex.normalized_title} at {ex.company_name}: {ex.summary[:100]}"
            for ex in negative_examples[:5]
        )
        neg_lines = f"\nJobs the candidate dismissed as not interested:\n{bullets}\n"

    system = (
        "You are a job relevance filter. Score the job 0.0-1.0 against the criteria. "
        'Return JSON only: {"score": <float>, "reasoning": "<one sentence>"}. '
        "Score >= 0.70 means strong match. 0.40-0.69 means borderline. < 0.40 means discard."
    )

    user = (
        f"Criteria:\n{criteria_text}\n"
        f"{neg_lines}"
        f"\nJob to score:\n"
        f"Title: {title}\n"
        f"Company: {company_name}\n"
        f"Location: {location or 'Not specified'}\n"
        f"Description:\n{description[:2000]}"
    )

    return system, user


def build_summarize_prompt(
    title: str,
    company_name: str,
    description: str,
    score: float,
) -> str:
    return (
        f"Summarize this job posting for a candidate deciding whether to apply. "
        f"Return exactly 4 labeled sections: Role snapshot, Key requirements, Why it matched, Red flags. "
        f"Be direct. Max 200 words total.\n\n"
        f"Job: {title} at {company_name} (relevance score: {score:.2f})\n"
        f"Description:\n{description[:3000]}"
    )
```

- [ ] **Step 3: Write test for prompt builders**

Create `tests/test_llm.py`:

```python
from backend.llm.protocol import CriteriaConfig, FeedbackExample
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt


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
```

- [ ] **Step 4: Run tests**

```powershell
cd C:\dev\joblin
.venv/Scripts/pytest tests/test_llm.py -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/llm/protocol.py backend/llm/prompts.py tests/test_llm.py
git commit -m "feat: LLM provider protocol and prompt builders"
```

---

## Task 14: GroqAdapter + CerebrasAdapter + GeminiAdapter + factory

**Files:**
- Create: `backend/llm/groq_adapter.py`
- Create: `backend/llm/cerebras_adapter.py`
- Create: `backend/llm/gemini_adapter.py`
- Create: `backend/llm/factory.py`
- Update: `backend/llm/__init__.py`

- [ ] **Step 1: Fetch Cerebras SDK docs via Context7 before writing**

Run this at the start of the task to get the latest Cerebras SDK usage:
```powershell
# Context7 fetch: resolve cerebras-cloud-sdk then query async usage
# (Do this via the MCP tool in your environment; the import pattern is shown in Step 2)
```

- [ ] **Step 2: Write `backend/llm/groq_adapter.py`**

```python
import json
from groq import AsyncGroq

from backend.llm.protocol import CriteriaConfig, FeedbackExample, FilterResult
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt


class GroqAdapter:
    def __init__(self, api_key: str):
        self._client = AsyncGroq(api_key=api_key)
        self._filter_model = "llama-3.1-8b-instant"
        self._summarize_model = "llama-3.1-8b-instant"

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
            model=self._filter_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=128,
        )
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
            model=self._summarize_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        return response.choices[0].message.content or ""
```

- [ ] **Step 3: Write `backend/llm/cerebras_adapter.py`**

Use Context7 to verify the current Cerebras SDK async import before finalizing:
```
# Context7: mcp__context7__resolve-library-id("cerebras-cloud-sdk")
# then mcp__context7__query-docs(id, "async chat completions create")
```

```python
import json
from cerebras.cloud.sdk import AsyncCerebras

from backend.llm.protocol import CriteriaConfig, FeedbackExample, FilterResult
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt


class CerebrasAdapter:
    def __init__(self, api_key: str):
        self._client = AsyncCerebras(api_key=api_key)
        self._model = "llama-3.3-70b"  # verify current model via Context7 at implementation

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
        return response.choices[0].message.content or ""
```

- [ ] **Step 4: Write `backend/llm/gemini_adapter.py`**

Use Context7 to fetch exact Flash Lite model ID before writing:
```
# Context7: mcp__context7__resolve-library-id("google-genai")
# then mcp__context7__query-docs(id, "async generate content model name flash lite")
```

```python
import json
from google import genai

from backend.llm.protocol import CriteriaConfig, FeedbackExample, FilterResult
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt


class GeminiAdapter:
    # Verify exact model ID via Context7 at implementation -- model names change frequently
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
```

- [ ] **Step 5: Write `backend/llm/factory.py`**

```python
from backend.llm.protocol import LLMProvider
from backend.llm.groq_adapter import GroqAdapter
from backend.llm.cerebras_adapter import CerebrasAdapter
from backend.llm.gemini_adapter import GeminiAdapter


def get_filter_provider(settings: dict) -> LLMProvider:
    provider = settings.get("llm_filter_provider", "groq")
    if provider == "groq":
        return GroqAdapter(api_key=settings.get("groq_api_key", ""))
    if provider == "cerebras":
        return CerebrasAdapter(api_key=settings.get("cerebras_api_key", ""))
    if provider == "gemini":
        return GeminiAdapter(api_key=settings.get("gemini_api_key", ""))
    raise ValueError(f"Unknown filter provider: {provider}")


def get_summarize_provider(settings: dict) -> LLMProvider:
    provider = settings.get("llm_summarize_provider", "cerebras")
    if provider == "cerebras":
        return CerebrasAdapter(api_key=settings.get("cerebras_api_key", ""))
    if provider == "groq":
        return GroqAdapter(api_key=settings.get("groq_api_key", ""))
    if provider == "gemini":
        return GeminiAdapter(api_key=settings.get("gemini_api_key", ""))
    raise ValueError(f"Unknown summarize provider: {provider}")
```

- [ ] **Step 6: Add adapter unit tests to `tests/test_llm.py`**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.llm.groq_adapter import GroqAdapter
from backend.llm.protocol import CriteriaConfig


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
```

- [ ] **Step 7: Run tests**

```powershell
.venv/Scripts/pytest tests/test_llm.py -v
```

Expected: all 5 PASS.

- [ ] **Step 8: Commit**

```powershell
git add backend/llm/
git commit -m "feat: Groq, Cerebras, Gemini LLM adapters and factory"
```

---

## Task 15: Discord notifier

**Files:**
- Create: `backend/discord.py`
- Create: `tests/test_discord.py`

- [ ] **Step 1: Write `tests/test_discord.py`**

```python
import pytest
from unittest.mock import AsyncMock, patch
from backend.discord import post_match_to_discord


async def test_post_strong_match_includes_mention():
    with patch("backend.discord.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=AsyncMock(status_code=204))

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
        assert payload["embeds"][0]["color"] == 0x22c55e  # green


async def test_post_borderline_match_no_mention():
    with patch("backend.discord.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=AsyncMock(status_code=204))

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
        assert payload["embeds"][0]["color"] == 0xeab308  # yellow
```

- [ ] **Step 2: Run to verify they fail**

```powershell
.venv/Scripts/pytest tests/test_discord.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write `backend/discord.py`**

```python
import httpx


async def post_match_to_discord(
    webhook_url: str,
    title: str,
    company_name: str,
    location: str | None,
    score: float,
    tier: str,
    summary: str,
    job_url: str,
    mention_type: str,
    mention_id: str,
) -> None:
    if not webhook_url:
        return

    is_strong = tier == "strong"
    color = 0x22c55e if is_strong else 0xeab308
    tier_label = "STRONG MATCH" if is_strong else "BORDERLINE"

    content = ""
    if is_strong and mention_type in ("user", "role") and mention_id:
        prefix = "@" if mention_type == "role" else ""
        content = f"<{prefix}@{mention_id}>"

    embed = {
        "title": title,
        "url": job_url,
        "color": color,
        "description": summary,
        "fields": [
            {"name": "Company", "value": company_name, "inline": True},
            {"name": "Location", "value": location or "Not specified", "inline": True},
            {"name": "Score", "value": f"{score:.2f} | {tier_label}", "inline": True},
        ],
    }

    payload: dict = {"embeds": [embed]}
    if content:
        payload["content"] = content

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()
```

- [ ] **Step 4: Run tests**

```powershell
.venv/Scripts/pytest tests/test_discord.py -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/discord.py tests/test_discord.py
git commit -m "feat: Discord webhook notifier with mention types and color-coded embeds"
```

---

## Task 16: Wire LLM + Discord into pipeline

**Files:**
- Modify: `backend/pipeline.py`

- [ ] **Step 1: Extend `execute_run` to call LLM filter, summarize, and Discord**

Replace the `# LLM placeholder` section in `pipeline.py` with full LLM + Discord logic. The complete updated `execute_run` function (replace the existing one entirely):

```python
async def execute_run(run_id: int, session: AsyncSession) -> None:
    from datetime import datetime, timezone
    from backend.config import get_all_settings
    from backend.llm.factory import get_filter_provider, get_summarize_provider
    from backend.llm.protocol import CriteriaConfig, FeedbackExample
    from backend.models.match import Match, MatchTier
    from backend.models.feedback import FeedbackExample as FeedbackExampleModel
    from backend.discord import post_match_to_discord

    run = await session.get(Run, run_id)
    if not run:
        return

    settings = await get_all_settings(session)
    criteria = CriteriaConfig.from_dict(settings.get("criteria") or {})
    quarantine_threshold = int(settings.get("quarantine_threshold") or 3)
    is_preview = run.is_preview

    filter_provider = get_filter_provider(settings)
    summarize_provider = get_summarize_provider(settings)

    # Load up to 5 most recent feedback examples
    from sqlalchemy import select as sa_select
    from backend.models.feedback import FeedbackExample as FBModel
    fb_rows = (await session.execute(
        sa_select(FBModel).order_by(FBModel.dismissed_at.desc()).limit(5)
    )).scalars().all()
    negative_examples = [
        FeedbackExample(
            company_name=r.company_name,
            normalized_title=r.normalized_title,
            normalized_location=r.normalized_location,
            summary=r.summary,
        )
        for r in fb_rows
    ]

    stmt = sa_select(Company).where(Company.is_active == True)
    if run.company_ids:
        stmt = stmt.where(Company.id.in_(run.company_ids))
    companies = (await session.execute(stmt)).scalars().all()

    await _emit(run_id, "run_started", {"run_id": run_id, "company_count": len(companies)})

    total_found = total_heuristic = total_confirmed = total_notified = 0

    for company in companies:
        result_row = RunCompanyResult(
            run_id=run_id, company_id=company.id, status=CompanyResultStatus.scraping
        )
        session.add(result_row)
        await session.commit()
        await session.refresh(result_row)

        await _emit(run_id, "company_scraping", {"company_id": company.id, "company_name": company.name})

        try:
            scraped = await _fetch_jobs(company)
        except Exception as exc:
            company.quarantine_count += 1
            if company.quarantine_count >= quarantine_threshold:
                company.quarantined_at = datetime.now(timezone.utc)
                company.quarantine_reason = str(exc)
            result_row.status = CompanyResultStatus.failed
            result_row.error_message = str(exc)
            await session.commit()
            await _emit(run_id, "company_failed", {"company_id": company.id, "error": str(exc)})
            continue

        total_found += len(scraped)
        new_jobs: list[tuple[Job, ScrapedJob]] = []

        for sj in scraped:
            job_id_str = compute_job_id(sj, company.id)
            existing = (await session.execute(
                sa_select(Job).where(Job.company_id == company.id, Job.job_id == job_id_str)
            )).scalar_one_or_none()

            if existing:
                existing.last_seen_at = datetime.now(timezone.utc)
                continue

            job = Job(
                company_id=company.id,
                job_id=job_id_str,
                title=sj.title,
                location=sj.location,
                url=sj.url,
                raw_description=sj.raw_description,
                normalized_title=_normalize(sj.title),
                normalized_location=_normalize(sj.location or ""),
                is_active=True,
            )
            session.add(job)
            await session.flush()
            new_jobs.append((job, sj))

        passed = [(job, sj) for job, sj in new_jobs if passes_heuristic(sj, criteria.__dict__)]
        total_heuristic += len(passed)

        confirmed_count = 0
        notified_count = 0

        for job, sj in passed:
            try:
                filter_result = await filter_provider.filter(
                    title=sj.title,
                    company_name=company.name,
                    location=sj.location,
                    description=sj.raw_description,
                    criteria=criteria,
                    negative_examples=negative_examples,
                )
            except Exception:
                filter_result = None

            if not filter_result or filter_result.score < 0.4:
                continue

            tier = MatchTier.strong if filter_result.score >= 0.7 else MatchTier.borderline

            try:
                summary = await summarize_provider.summarize(
                    title=sj.title,
                    company_name=company.name,
                    description=sj.raw_description,
                    score=filter_result.score,
                )
            except Exception:
                summary = ""

            match = Match(
                job_id=job.id,
                run_id=run_id,
                score=filter_result.score,
                tier=tier,
                summary=summary,
                filter_reasoning=filter_result.reasoning,
                is_preview=is_preview,
            )
            session.add(match)
            await session.flush()
            confirmed_count += 1

            if not is_preview and settings.get("discord_webhook_url"):
                try:
                    await post_match_to_discord(
                        webhook_url=settings["discord_webhook_url"],
                        title=sj.title,
                        company_name=company.name,
                        location=sj.location,
                        score=filter_result.score,
                        tier=tier.value,
                        summary=summary,
                        job_url=sj.url,
                        mention_type=settings.get("discord_mention_type", "none"),
                        mention_id=settings.get("discord_mention_id", ""),
                    )
                    match.notified_at = datetime.now(timezone.utc)
                    notified_count += 1
                except Exception:
                    pass

        await session.commit()
        total_confirmed += confirmed_count
        total_notified += notified_count

        await _emit(run_id, "company_done", {
            "company_id": company.id,
            "jobs_found": len(scraped),
            "passed_heuristic": len(passed),
            "confirmed": confirmed_count,
        })

        result_row.status = CompanyResultStatus.done
        result_row.jobs_found = len(scraped)
        result_row.passed_heuristic = len(passed)
        result_row.confirmed = confirmed_count
        company.quarantine_count = 0

    if total_notified > 0:
        await _emit(run_id, "discord_posted", {"count": total_notified})

    run.total_jobs_found = total_found
    run.total_passed_heuristic = total_heuristic
    run.total_confirmed = total_confirmed
    run.total_notified = total_notified
    run.status = RunStatus.completed
    run.completed_at = datetime.now(timezone.utc)
    await session.commit()

    await _emit(run_id, "run_done", {
        "run_id": run_id, "status": "completed", "total_confirmed": total_confirmed
    })
    _run_queues.pop(run_id, None)
```

- [ ] **Step 2: Remove the old partial `execute_run` from `pipeline.py` and replace with the above**

- [ ] **Step 3: Run all existing tests to confirm nothing broke**

```powershell
.venv/Scripts/pytest tests/ -v
```

Expected: all existing tests PASS (the new execute_run is tested via mock in test_runs.py).

- [ ] **Step 4: Commit**

```powershell
git add backend/pipeline.py
git commit -m "feat: wire LLM filter, summarize, and Discord into run pipeline"
```

---

## Task 17: Jobs + Matches routers + settings router

**Files:**
- Create: `backend/routers/jobs.py`
- Create: `backend/routers/matches.py`
- Create: `backend/routers/settings.py`
- Create: `backend/routers/presets.py`

- [ ] **Step 1: Write `backend/routers/jobs.py`**

```python
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models.job import Job
from backend.models.match import Match
from backend.models.company import Company
from backend.models.feedback import FeedbackExample

router = APIRouter(prefix="/jobs", tags=["jobs"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_jobs(
    session: Session,
    company_id: int | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    stmt = select(Job).order_by(Job.first_seen_at.desc())
    if company_id:
        stmt = stmt.where(Job.company_id == company_id)
    if search:
        stmt = stmt.where(Job.title.ilike(f"%{search}%"))
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": j.id, "company_id": j.company_id, "title": j.title,
            "location": j.location, "url": j.url,
            "first_seen_at": j.first_seen_at, "is_active": j.is_active,
        }
        for j in rows
    ]


@router.get("/{job_id}")
async def get_job(job_id: int, session: Session):
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    match = (await session.execute(
        select(Match).where(Match.job_id == job_id)
    )).scalar_one_or_none()
    return {
        "id": job.id, "title": job.title, "company_id": job.company_id,
        "location": job.location, "url": job.url,
        "raw_description": job.raw_description,
        "match": {"score": match.score, "tier": match.tier, "summary": match.summary} if match else None,
    }


@router.post("/{job_id}/dismiss")
async def dismiss_job(job_id: int, session: Session):
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    match = (await session.execute(
        select(Match).where(Match.job_id == job_id)
    )).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=400, detail="Job has no match to dismiss")

    match.not_interested_at = datetime.now(timezone.utc)

    company = await session.get(Company, job.company_id)
    fb = FeedbackExample(
        job_id=job_id,
        company_name=company.name if company else "",
        normalized_title=job.normalized_title,
        normalized_location=job.normalized_location,
        summary=match.summary,
    )
    session.add(fb)

    # Trim to 50 most recent
    all_fb = (await session.execute(
        select(FeedbackExample).order_by(FeedbackExample.dismissed_at.desc())
    )).scalars().all()
    for old in all_fb[50:]:
        await session.delete(old)

    await session.commit()
    return {"status": "dismissed"}
```

- [ ] **Step 2: Write `backend/routers/matches.py`**

```python
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.discord import post_match_to_discord
from backend.models.match import Match
from backend.models.job import Job
from backend.models.company import Company

router = APIRouter(prefix="/matches", tags=["matches"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_matches(
    session: Session,
    tier: str | None = Query(None),
    company_id: int | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    stmt = select(Match).order_by(Match.created_at.desc())
    if tier:
        stmt = stmt.where(Match.tier == tier)
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": m.id, "job_id": m.job_id, "score": m.score, "tier": m.tier,
            "summary": m.summary, "is_preview": m.is_preview,
            "notified_at": m.notified_at, "not_interested_at": m.not_interested_at,
            "created_at": m.created_at,
        }
        for m in rows
    ]


class BulkNotifyRequest(BaseModel):
    match_ids: list[int]


@router.post("/notify")
async def bulk_notify(req: BulkNotifyRequest, session: Session):
    settings = await get_all_settings(session)
    webhook_url = settings.get("discord_webhook_url", "")
    notified = 0

    for match_id in req.match_ids:
        match = await session.get(Match, match_id)
        if not match or match.is_preview:
            continue
        job = await session.get(Job, match.job_id)
        company = await session.get(Company, job.company_id) if job else None
        if not job or not company:
            continue
        try:
            await post_match_to_discord(
                webhook_url=webhook_url,
                title=job.title,
                company_name=company.name,
                location=job.location,
                score=match.score,
                tier=match.tier.value,
                summary=match.summary,
                job_url=job.url,
                mention_type=settings.get("discord_mention_type", "none"),
                mention_id=settings.get("discord_mention_id", ""),
            )
            match.notified_at = datetime.now(timezone.utc)
            notified += 1
        except Exception:
            pass

    await session.commit()
    return {"notified": notified}
```

- [ ] **Step 3: Write `backend/routers/settings.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings, set_setting
from backend.database import get_session
from backend.discord import post_match_to_discord

router = APIRouter(prefix="/settings", tags=["settings"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def get_settings(session: Session):
    return await get_all_settings(session)


@router.patch("")
async def update_settings(body: dict, session: Session):
    for key, value in body.items():
        await set_setting(session, key, value)
    return {"updated": list(body.keys())}


@router.post("/discord/test")
async def test_discord(session: Session):
    settings = await get_all_settings(session)
    webhook_url = settings.get("discord_webhook_url", "")
    if not webhook_url:
        return {"error": "No webhook URL configured"}
    try:
        await post_match_to_discord(
            webhook_url=webhook_url,
            title="Joblin test notification",
            company_name="Joblin",
            location="Self-hosted",
            score=1.0,
            tier="strong",
            summary="This is a test notification from Joblin.",
            job_url="https://github.com",
            mention_type="none",
            mention_id="",
        )
        return {"status": "sent"}
    except Exception as exc:
        return {"error": str(exc)}


class CriteriaTestRequest(BaseModel):
    description: str


@router.post("/criteria/test")
async def test_criteria(req: CriteriaTestRequest, session: Session):
    from backend.config import get_setting
    from backend.llm.factory import get_filter_provider
    from backend.llm.protocol import CriteriaConfig, FeedbackExample

    settings = await get_all_settings(session)
    criteria = CriteriaConfig.from_dict(settings.get("criteria") or {})
    provider = get_filter_provider(settings)
    try:
        result = await provider.filter(
            title="Test Job",
            company_name="Test Company",
            location=None,
            description=req.description,
            criteria=criteria,
            negative_examples=[],
        )
        return {"score": result.score, "reasoning": result.reasoning}
    except Exception as exc:
        return {"error": str(exc)}
```

- [ ] **Step 4: Write `backend/routers/presets.py`**

```python
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import set_setting
from backend.database import get_session

router = APIRouter(prefix="/presets", tags=["presets"])
Session = Annotated[AsyncSession, Depends(get_session)]

PRESETS_DIR = Path(__file__).parent.parent.parent / "presets"


@router.get("")
async def list_presets():
    presets = []
    for path in sorted(PRESETS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        presets.append({"name": path.stem, "description": data.get("description", ""), "criteria": data.get("criteria", {})})
    return presets


@router.post("/{name}/apply")
async def apply_preset(name: str, session: Session):
    path = PRESETS_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    data = json.loads(path.read_text())
    criteria = data.get("criteria")
    if not criteria:
        raise HTTPException(status_code=400, detail="Preset has no criteria field")
    await set_setting(session, "criteria", criteria)
    return {"applied": name}
```

- [ ] **Step 5: Register all new routers in `backend/main.py`**

```python
from backend.routers import system, companies, runs as runs_router, jobs, matches, settings as settings_router, presets

def create_app() -> FastAPI:
    app = FastAPI(title="Joblin", lifespan=lifespan)
    app.include_router(system.router, prefix="/api")
    app.include_router(companies.router, prefix="/api")
    app.include_router(runs_router.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(matches.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(presets.router, prefix="/api")
    ...
```

- [ ] **Step 6: Run all tests**

```powershell
.venv/Scripts/pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/routers/ backend/main.py
git commit -m "feat: jobs, matches, settings, and presets routers"
```

---

## Task 18: APScheduler integration + staleness gate

**Files:**
- Create: `backend/scheduler.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write `backend/scheduler.py`**

```python
from datetime import datetime, timezone, timedelta

from apscheduler import AsyncScheduler, ConflictPolicy
from apscheduler.triggers.cron import CronTrigger

from backend.database import AsyncSessionLocal
from backend.config import get_setting


async def _run_scrape_job() -> None:
    from backend.models.run import Run, RunStatus
    from backend.pipeline import execute_run
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        staleness_hours = float(await get_setting(session, "staleness_threshold_hours") or 4)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=staleness_hours)
        last_run = (await session.execute(
            select(Run)
            .where(Run.status == RunStatus.completed)
            .order_by(Run.completed_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        if last_run and last_run.completed_at and last_run.completed_at > cutoff:
            return  # still fresh, skip

        from backend.models.run import Run
        run = Run(is_preview=False)
        session.add(run)
        await session.commit()
        await session.refresh(run)

    async with AsyncSessionLocal() as session:
        await execute_run(run.id, session)


async def start_scheduler(scheduler: AsyncScheduler) -> None:
    async with AsyncSessionLocal() as session:
        cron_expr = await get_setting(session, "schedule_cron") or "0 */4 * * *"
        enabled = await get_setting(session, "scheduler_enabled") or False

    if not enabled:
        return

    parts = cron_expr.split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
    else:
        minute, hour, day, month, day_of_week = "0", "*/4", "*", "*", "*"

    await scheduler.add_schedule(
        _run_scrape_job,
        CronTrigger(
            minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week
        ),
        id="scrape_cron",
        conflict_policy=ConflictPolicy.replace,
    )
```

- [ ] **Step 2: Update lifespan in `backend/main.py` to start APScheduler**

```python
from contextlib import asynccontextmanager
from apscheduler import AsyncScheduler
from backend.scheduler import start_scheduler
from backend.database import AsyncSessionLocal
from backend.config import seed_defaults


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as session:
        await seed_defaults(session)

    async with AsyncScheduler() as scheduler:
        await start_scheduler(scheduler)
        await scheduler.start_in_background()
        yield
```

- [ ] **Step 3: Run the server and verify it starts cleanly**

```powershell
.venv/Scripts/uvicorn backend.main:app --port 8000
```

Expected: starts without errors. Scheduler skips adding a job because `scheduler_enabled` is False by default.

Stop with Ctrl+C.

- [ ] **Step 4: Write preset JSON files**

Create `presets/backend-generalist.json`:
```json
{
  "description": "Backend generalist: Python, distributed systems, infrastructure",
  "criteria": {
    "title_allowlist": "backend|platform|infrastructure|systems|distributed|data engineer|api",
    "title_denylist": "intern|contract|marketing|sales|design|front.?end",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["senior", "staff", "principal", "lead"],
    "exclusion_keywords": ["clearance required", "on-site only"],
    "profile_description": "Experienced backend engineer skilled in Python, distributed systems, and API design. Seeking senior or staff-level roles at product companies."
  }
}
```

Create `presets/python-ml.json`:
```json
{
  "description": "Python ML engineer: ML platform, MLOps, data science",
  "criteria": {
    "title_allowlist": "machine learning|ml engineer|ml platform|mlops|data scientist|ai engineer|research engineer",
    "title_denylist": "intern|contract|front.?end|mobile",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["senior", "staff", "principal", "lead", "mid"],
    "exclusion_keywords": ["clearance required"],
    "profile_description": "ML engineer with Python expertise seeking roles in ML platform engineering, MLOps, or applied ML at product companies."
  }
}
```

Create `presets/frontend.json`:
```json
{
  "description": "Frontend engineer: React, TypeScript, product UI",
  "criteria": {
    "title_allowlist": "front.?end|ui engineer|react|web engineer|javascript|typescript",
    "title_denylist": "intern|contract|backend|mobile",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["senior", "staff", "principal", "lead"],
    "exclusion_keywords": ["clearance required"],
    "profile_description": "Senior frontend engineer specializing in React, TypeScript, and design systems at product-focused companies."
  }
}
```

- [ ] **Step 5: Run all tests**

```powershell
.venv/Scripts/pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/scheduler.py backend/main.py presets/
git commit -m "feat: APScheduler cron integration with staleness gate and preset JSON files"
```

---

**Phase 3 complete.** Full end-to-end pipeline works: LLM filter via Groq, summarize via Cerebras (with Gemini fallback), Discord notifications with configurable @mention, SSE event stream, APScheduler cron, and the "not interested" feedback loop. Proceed to Phase 4.
