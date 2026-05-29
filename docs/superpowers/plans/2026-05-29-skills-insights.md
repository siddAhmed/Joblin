# Skills Insights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual skill-extraction feature that accumulates a ranked list of skills demanded by matched jobs, with per-skill citation drill-down, powered by the configured LLM and displayed on a dedicated Insights page.

**Architecture:** A new `job_skills` table stores (job_id, skill_name) pairs extracted by the LLM filter provider. The Matches page navigates to `/insights?analyze=<ids>` where the Insights page loops through IDs one-at-a-time calling `POST /api/insights/analyze`, updating a live progress line and incrementally refreshing the ranked skill table after each job.

**Tech Stack:** SQLAlchemy 2.x async + Alembic (backend), SQLite dialect `insert().on_conflict_do_nothing()`, FastAPI, React 18 + TanStack Query v5, React Router v6, TypeScript.

---

## File Map

**Create:**
- `backend/models/job_skill.py` - `JobSkill` SQLAlchemy model
- `backend/alembic/versions/c8f2a1b3d4e5_add_job_skills.py` - migration
- `backend/routers/insights.py` - three insights endpoints
- `frontend/src/api/insights.ts` - typed API client
- `frontend/src/pages/Insights.tsx` - insights page with live analysis progress
- `tests/test_insights.py` - backend tests

**Modify:**
- `backend/models/__init__.py` - add `JobSkill` export
- `backend/llm/prompts.py` - add `build_skills_prompt()`
- `backend/llm/protocol.py` - add `extract_skills` to `LLMProvider` Protocol
- `backend/llm/groq_adapter.py` - implement `extract_skills()`
- `backend/llm/cerebras_adapter.py` - implement `extract_skills()`
- `backend/llm/gemini_adapter.py` - implement `extract_skills()`
- `backend/main.py` - register insights router
- `frontend/src/pages/Matches.tsx` - add "Analyze skills" button + navigate
- `frontend/src/App.tsx` - add `/insights` route
- `frontend/src/components/Sidebar.tsx` - add Insights nav entry
- `frontend/src/components/Layout.tsx` - add Insights title

---

### Task 1: JobSkill model + Alembic migration

**Files:**
- Create: `backend/models/job_skill.py`
- Create: `backend/alembic/versions/c8f2a1b3d4e5_add_job_skills.py`
- Modify: `backend/models/__init__.py`

- [ ] **Step 1: Create the model**

Create `backend/models/job_skill.py`:

```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class JobSkill(Base):
    __tablename__ = "job_skills"
    __table_args__ = (
        UniqueConstraint("job_id", "skill_name", name="uq_job_skill"),
        Index("ix_job_skills_skill_name", "skill_name"),
        Index("ix_job_skills_job_id", "job_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False)
    skill_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 2: Create the migration**

Create `backend/alembic/versions/c8f2a1b3d4e5_add_job_skills.py`:

```python
"""add job_skills table

Revision ID: c8f2a1b3d4e5
Revises: b7e3f9a12c45
Create Date: 2026-05-29

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c8f2a1b3d4e5"
down_revision: Union[str, None] = "b7e3f9a12c45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("skill_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", "skill_name", name="uq_job_skill"),
    )
    op.create_index("ix_job_skills_skill_name", "job_skills", ["skill_name"])
    op.create_index("ix_job_skills_job_id", "job_skills", ["job_id"])


def downgrade() -> None:
    op.drop_table("job_skills")
```

- [ ] **Step 3: Export from models package**

In `backend/models/__init__.py`, add the import and export:

```python
from backend.models.job_skill import JobSkill
```

Add `"JobSkill"` to the `__all__` list.

- [ ] **Step 4: Verify migration chain**

Run from the repo root:
```bash
cd C:\dev\joblin
.venv\Scripts\python -m alembic history
```

Expected: `c8f2a1b3d4e5` listed after `b7e3f9a12c45`.

- [ ] **Step 5: Commit**

```bash
git add backend/models/job_skill.py backend/alembic/versions/c8f2a1b3d4e5_add_job_skills.py backend/models/__init__.py
git commit -m "feat: add job_skills model and migration"
```

---

### Task 2: Skills prompt + extract_skills on all three adapters

**Files:**
- Modify: `backend/llm/prompts.py`
- Modify: `backend/llm/protocol.py`
- Modify: `backend/llm/groq_adapter.py`
- Modify: `backend/llm/cerebras_adapter.py`
- Modify: `backend/llm/gemini_adapter.py`

- [ ] **Step 1: Add `build_skills_prompt` to prompts.py**

Append to `backend/llm/prompts.py`:

```python
def build_skills_prompt(title: str, description: str) -> str:
    return (
        "Extract skills from this job description. Return a JSON array of canonical skill name strings only. "
        "Include: programming languages, frameworks, libraries, databases, cloud platforms, infrastructure tools, "
        "and specific technical domain skills such as 'system design', 'distributed systems', 'API design', "
        "'event-driven architecture', 'data modeling'. "
        "Exclude generic soft skills like communication, ownership, leadership, or collaboration. "
        "Use canonical names: 'PostgreSQL' not 'Postgres', 'React' not 'React.js', "
        "'Kubernetes' not 'k8s', 'TypeScript' not 'TS'. "
        "Return only the JSON array with no other text, markdown, or explanation.\n\n"
        f"Job title: {title}\n"
        f"Description:\n{description[:3000]}"
    )
```

- [ ] **Step 2: Add `extract_skills` to the LLMProvider Protocol**

In `backend/llm/protocol.py`, add to the `LLMProvider` class body after `summarize`:

```python
    async def extract_skills(self, title: str, description: str) -> list[str]: ...
```

The full Protocol class should now have three abstract methods: `filter`, `summarize`, `extract_skills`.

- [ ] **Step 3: Implement `extract_skills` in GroqAdapter**

In `backend/llm/groq_adapter.py`, add this import at the top alongside the existing prompts import:

```python
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt, build_skills_prompt
```

Add the method to `GroqAdapter`:

```python
    async def extract_skills(self, title: str, description: str) -> list[str]:
        prompt = build_skills_prompt(title, description)
        response = await self._client.chat.completions.create(
            model=self._filter_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
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
```

- [ ] **Step 4: Implement `extract_skills` in CerebrasAdapter**

In `backend/llm/cerebras_adapter.py`, update the prompts import:

```python
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt, build_skills_prompt
```

Add the method to `CerebrasAdapter`:

```python
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
```

- [ ] **Step 5: Implement `extract_skills` in GeminiAdapter**

In `backend/llm/gemini_adapter.py`, update the prompts import:

```python
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt, build_skills_prompt
```

Add the method to `GeminiAdapter`:

```python
    async def extract_skills(self, title: str, description: str) -> list[str]:
        prompt = build_skills_prompt(title, description)
        response = await self._client.aio.models.generate_content(
            model=self._filter_model,
            contents=prompt,
        )
        self._record_usage(response)
        raw = response.text or ""
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            return json.loads(raw[start:end])
        except Exception:
            return []
```

- [ ] **Step 6: Run existing tests to confirm nothing broken**

```bash
cd C:\dev\joblin
.venv\Scripts\python -m pytest tests/ -v
```

Expected: all existing tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/llm/prompts.py backend/llm/protocol.py backend/llm/groq_adapter.py backend/llm/cerebras_adapter.py backend/llm/gemini_adapter.py
git commit -m "feat: add extract_skills to LLM adapters and skills prompt"
```

---

### Task 3: Insights backend router + registration + tests

**Files:**
- Create: `backend/routers/insights.py`
- Modify: `backend/main.py`
- Create: `tests/test_insights.py`

- [ ] **Step 1: Write the failing tests first**

Create `tests/test_insights.py`:

```python
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import insert

from backend.models.company import Company
from backend.models.job import Job
from backend.models.match import Match, MatchTier
from backend.models.run import Run, RunStatus
from backend.models.job_skill import JobSkill
from backend.database import get_session


@pytest.mark.anyio
async def test_analyze_empty_match_ids(client: AsyncClient):
    resp = await client.post("/api/insights/analyze", json={"match_ids": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"analyzed": 0, "skipped": 0, "skills_found": 0}


@pytest.mark.anyio
async def test_list_skills_empty(client: AsyncClient):
    resp = await client.get("/api/insights/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert data["skills"] == []
    assert data["total_jobs_analyzed"] == 0


@pytest.mark.anyio
async def test_citations_empty(client: AsyncClient):
    resp = await client.get("/api/insights/skills/Python/citations")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_analyze_records_skills_and_deduplicates(client: AsyncClient, app):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from backend.database import Base

    # Seed DB with company -> job -> run -> match
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        company = Company(name="Acme", careers_url="https://acme.com/careers", ats_type="greenhouse")
        session.add(company)
        await session.flush()

        job = Job(
            company_id=company.id,
            job_id="j1",
            title="Backend Engineer",
            url="https://acme.com/jobs/1",
            raw_description="Python, PostgreSQL, system design required.",
            normalized_title="backend engineer",
        )
        session.add(job)
        await session.flush()

        run = Run(status=RunStatus.completed)
        session.add(run)
        await session.flush()

        match = Match(job_id=job.id, run_id=run.id, score=0.85, tier=MatchTier.strong, summary="Good fit")
        session.add(match)
        await session.commit()

        match_id = match.id
        job_id = job.id

    async def override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override

    mock_provider = AsyncMock()
    mock_provider.extract_skills = AsyncMock(return_value=["Python", "PostgreSQL", "system design"])
    mock_provider.last_usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    with patch("backend.routers.insights.get_filter_provider", return_value=mock_provider):
        resp = await client.post("/api/insights/analyze", json={"match_ids": [match_id]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["analyzed"] == 1
    assert data["skipped"] == 0
    assert data["skills_found"] == 3

    # Second call: same match should be skipped
    with patch("backend.routers.insights.get_filter_provider", return_value=mock_provider):
        resp2 = await client.post("/api/insights/analyze", json={"match_ids": [match_id]})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["analyzed"] == 0
    assert data2["skipped"] == 1

    # Skills list should now show 3 skills
    resp3 = await client.get("/api/insights/skills")
    assert resp3.status_code == 200
    skills_data = resp3.json()
    skill_names = [s["name"] for s in skills_data["skills"]]
    assert "Python" in skill_names
    assert skills_data["total_jobs_analyzed"] == 1

    await engine.dispose()
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
cd C:\dev\joblin
.venv\Scripts\python -m pytest tests/test_insights.py -v
```

Expected: ImportError or 404 errors since `insights.py` doesn't exist yet.

- [ ] **Step 3: Create the router**

Create `backend/routers/insights.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.llm.factory import get_filter_provider
from backend.models.company import Company
from backend.models.job import Job
from backend.models.job_skill import JobSkill
from backend.models.match import Match

router = APIRouter(prefix="/insights", tags=["insights"])
Session = Annotated[AsyncSession, Depends(get_session)]


class AnalyzeRequest(BaseModel):
    match_ids: list[int]


@router.post("/analyze")
async def analyze_skills(req: AnalyzeRequest, session: Session):
    settings = await get_all_settings(session)
    provider = get_filter_provider(settings)

    analyzed = 0
    skipped = 0
    skills_found = 0

    for match_id in req.match_ids:
        match = await session.get(Match, match_id)
        if not match:
            continue

        job = await session.get(Job, match.job_id)
        if not job:
            continue

        existing = (await session.execute(
            select(func.count()).select_from(JobSkill).where(JobSkill.job_id == job.id)
        )).scalar() or 0
        if existing > 0:
            skipped += 1
            continue

        try:
            skills = await provider.extract_skills(job.title, job.raw_description)
        except Exception:
            continue

        for skill in skills:
            if not isinstance(skill, str) or not skill.strip():
                continue
            stmt = sqlite_insert(JobSkill).values(
                job_id=job.id, skill_name=skill.strip()
            ).on_conflict_do_nothing()
            await session.execute(stmt)
            skills_found += 1

        await session.commit()
        analyzed += 1

    return {"analyzed": analyzed, "skipped": skipped, "skills_found": skills_found}


@router.get("/skills")
async def list_skills(session: Session):
    rows = (await session.execute(
        select(JobSkill.skill_name, func.count(JobSkill.id).label("count"))
        .group_by(JobSkill.skill_name)
        .order_by(func.count(JobSkill.id).desc())
    )).all()

    total_jobs = (await session.execute(
        select(func.count(func.distinct(JobSkill.job_id)))
    )).scalar() or 0

    return {
        "skills": [{"name": row.skill_name, "count": row.count} for row in rows],
        "total_jobs_analyzed": total_jobs,
    }


@router.get("/skills/{name}/citations")
async def get_citations(name: str, session: Session):
    rows = (await session.execute(
        select(Company.name.label("company_name"), Job.title.label("job_title"))
        .select_from(JobSkill)
        .join(Job, JobSkill.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(JobSkill.skill_name == name)
        .order_by(JobSkill.created_at.desc())
    )).all()
    return [{"company_name": row.company_name, "job_title": row.job_title} for row in rows]
```

- [ ] **Step 4: Register the router in main.py**

In `backend/main.py`, add the import alongside existing router imports:

```python
from backend.routers.insights import router as insights_router
```

And inside `create_app()`, after the `admin_router` line:

```python
    app.include_router(insights_router, prefix="/api")
```

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
cd C:\dev\joblin
.venv\Scripts\python -m pytest tests/test_insights.py -v
```

Expected: all tests in `test_insights.py` pass.

- [ ] **Step 6: Run the full test suite**

```bash
.venv\Scripts\python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 7: Exclude job_skills from the Danger tab reset**

In `backend/routers/admin.py`, `job_skills` rows must survive a reset (same treatment as `token_usage`). The current `reset_job_data` function does not touch `job_skills`, so no deletion code needs to be added - just verify the import list doesn't include `JobSkill`. No code change is needed as long as `JobSkill` is never imported or deleted in `admin.py`. Confirm by reading `backend/routers/admin.py` and ensuring `JobSkill` / `job_skills` appears nowhere in it.

- [ ] **Step 8: Commit**

```bash
git add backend/routers/insights.py backend/main.py tests/test_insights.py
git commit -m "feat: insights backend router with analyze, skills, and citations endpoints"
```

---

### Task 4: Frontend API client + Matches page trigger

**Files:**
- Create: `frontend/src/api/insights.ts`
- Modify: `frontend/src/pages/Matches.tsx`

- [ ] **Step 1: Create the API client**

Create `frontend/src/api/insights.ts`:

```typescript
import { api } from "./client";

export interface Skill {
  name: string;
  count: number;
}

export interface Citation {
  company_name: string;
  job_title: string;
}

export interface AnalyzeResult {
  analyzed: number;
  skipped: number;
  skills_found: number;
}

export interface SkillsData {
  skills: Skill[];
  total_jobs_analyzed: number;
}

export const insightsApi = {
  analyze: (match_ids: number[]) =>
    api.post<AnalyzeResult>("/insights/analyze", { match_ids }).then((r) => r.data),
  skills: () =>
    api.get<SkillsData>("/insights/skills").then((r) => r.data),
  citations: (name: string) =>
    api.get<Citation[]>(`/insights/skills/${encodeURIComponent(name)}/citations`).then((r) => r.data),
};
```

- [ ] **Step 2: Add "Analyze skills" button to Matches page**

In `frontend/src/pages/Matches.tsx`, add `useNavigate` to the react-router-dom import. The current import at line 1 is:

```typescript
import { useState } from "react";
```

Change it to:

```typescript
import { useState } from "react";
import { useNavigate } from "react-router-dom";
```

Inside the `Matches` function body, add after the existing state declarations:

```typescript
  const navigate = useNavigate();
```

Find the existing `{selected.size > 0 && (` block and extend it to include the new button. The existing block is:

```tsx
        {selected.size > 0 && (
          <button onClick={() => bulkNotify.mutate()} className="text-xs border border-[#4e9eff] rounded px-3 py-1 text-[#4e9eff] bg-[#0e2040]">
            Re-notify {selected.size} selected
          </button>
        )}
```

Replace it with:

```tsx
        {selected.size > 0 && (
          <>
            <button onClick={() => bulkNotify.mutate()} className="text-xs border border-[#4e9eff] rounded px-3 py-1 text-[#4e9eff] bg-[#0e2040]">
              Re-notify {selected.size} selected
            </button>
            <button
              onClick={() => navigate(`/insights?analyze=${Array.from(selected).join(",")}`)}
              className="text-xs border border-[#2a2a2a] rounded px-3 py-1 text-[#888] hover:text-[#ccc]"
            >
              Analyze skills ({selected.size})
            </button>
          </>
        )}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/insights.ts frontend/src/pages/Matches.tsx
git commit -m "feat: insights API client and Analyze skills button on Matches page"
```

---

### Task 5: Insights page + routing + sidebar

**Files:**
- Create: `frontend/src/pages/Insights.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: Create the Insights page**

Create `frontend/src/pages/Insights.tsx`:

```tsx
import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { insightsApi, type Citation } from "@/api/insights";
import type { Match } from "@/api/matches";

export function Insights() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [progress, setProgress] = useState<string | null>(null);
  const [done, setDone] = useState<{ analyzed: number; skipped: number } | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loadingCitations, setLoadingCitations] = useState(false);
  const isAnalyzing = useRef(false);
  const qc = useQueryClient();

  const { data: skillsData = { skills: [], total_jobs_analyzed: 0 }, refetch: refetchSkills } = useQuery({
    queryKey: ["insights-skills"],
    queryFn: insightsApi.skills,
  });

  useEffect(() => {
    const analyzeParam = searchParams.get("analyze");
    if (!analyzeParam || isAnalyzing.current) return;
    const matchIds = analyzeParam.split(",").map(Number).filter(Boolean);
    if (matchIds.length === 0) return;
    isAnalyzing.current = true;
    runAnalysis(matchIds);
  }, []);

  async function runAnalysis(matchIds: number[]) {
    const cachedMatches = qc.getQueryData<Match[]>(["matches", ""]) ?? [];
    const matchMap = new Map(cachedMatches.map((m) => [m.id, m]));

    let totalAnalyzed = 0;
    let totalSkipped = 0;

    for (let i = 0; i < matchIds.length; i++) {
      const matchId = matchIds[i];
      const match = matchMap.get(matchId);
      const label = match
        ? `${match.job_title} at ${match.company_name}`
        : `job #${matchId}`;

      setProgress(`Analyzing ${i + 1} of ${matchIds.length}: ${label}`);

      try {
        const result = await insightsApi.analyze([matchId]);
        totalAnalyzed += result.analyzed;
        totalSkipped += result.skipped;
        await refetchSkills();
      } catch {
        setAnalysisError(`Failed on: ${label}`);
      }
    }

    setProgress(null);
    setDone({ analyzed: totalAnalyzed, skipped: totalSkipped });
    setSearchParams({}, { replace: true });
    isAnalyzing.current = false;
  }

  async function toggleCitations(skillName: string) {
    if (expandedSkill === skillName) {
      setExpandedSkill(null);
      setCitations([]);
      return;
    }
    setLoadingCitations(true);
    try {
      const data = await insightsApi.citations(skillName);
      setCitations(data);
      setExpandedSkill(skillName);
    } finally {
      setLoadingCitations(false);
    }
  }

  const { skills, total_jobs_analyzed } = skillsData;

  return (
    <div className="max-w-2xl">
      {(progress || done || analysisError) && (
        <div className="mb-5 p-3 bg-[#111] border border-[#1e1e1e] rounded text-xs space-y-1">
          {progress && <div className="text-[#888]">{progress}</div>}
          {analysisError && <div className="text-red-400">{analysisError}</div>}
          {done && (
            <div className="text-emerald-500">
              Done - analyzed {done.analyzed}, skipped {done.skipped} already processed
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <div className="text-xs text-[#555]">
          {skills.length} skills tracked across {total_jobs_analyzed} job{total_jobs_analyzed !== 1 ? "s" : ""}
        </div>
      </div>

      {skills.length === 0 && !progress && (
        <p className="text-sm text-[#555]">
          No skills yet. Select matches on the Matches page and click "Analyze skills".
        </p>
      )}

      <div className="space-y-0.5">
        {skills.map((skill, i) => (
          <div key={skill.name}>
            <div className="flex items-center gap-3 px-3 py-2 rounded hover:bg-[#111]">
              <span className="text-[10px] text-[#444] w-5 text-right">{i + 1}</span>
              <span className="flex-1 text-sm text-[#e5e5e5]">{skill.name}</span>
              <button
                onClick={() => toggleCitations(skill.name)}
                className={`text-xs font-mono px-2 py-0.5 rounded border ${
                  expandedSkill === skill.name
                    ? "border-[#4e9eff] text-[#4e9eff] bg-[#0e2040]"
                    : "border-[#2a2a2a] text-[#666] hover:text-[#ccc]"
                }`}
              >
                {skill.count}
              </button>
            </div>
            {expandedSkill === skill.name && (
              <div className="ml-8 mb-1 px-3 py-2 bg-[#0a0a0a] border border-[#1e1e1e] rounded text-xs">
                {loadingCitations ? (
                  <span className="text-[#555]">Loading...</span>
                ) : citations.length === 0 ? (
                  <span className="text-[#555]">No citations found.</span>
                ) : (
                  <ul className="space-y-0.5">
                    {citations.map((c, j) => (
                      <li key={j} className="text-[#888]">
                        {c.company_name} <span className="text-[#555]">- {c.job_title}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add the route in App.tsx**

In `frontend/src/App.tsx`, add the import after the `Usage` import:

```typescript
import { Insights } from "./pages/Insights";
```

Add the route inside the `<Route element={<Layout />}>` block, after the `/usage` route:

```tsx
        <Route path="/insights" element={<Insights />} />
```

- [ ] **Step 3: Add the sidebar entry**

In `frontend/src/components/Sidebar.tsx`, in the `NAV` array, add the Insights entry between Usage and Settings:

```typescript
  { label: "Insights", icon: "◎", path: "/insights" },
```

The full NAV array should be:
```typescript
const NAV = [
  { label: "Dashboard", icon: "◼", path: "/" },
  { label: "Matches", icon: "★", path: "/matches" },
  { label: "All Jobs", icon: "≡", path: "/jobs" },
  { label: "Companies", icon: "⊞", path: "/companies", warn: true },
  { label: "Runs", icon: "▶", path: "/runs" },
  { label: "Usage", icon: "◈", path: "/usage" },
  { label: "Insights", icon: "◎", path: "/insights" },
  { label: "Settings", icon: "⚙", path: "/settings" },
] as const;
```

- [ ] **Step 4: Add the page title in Layout.tsx**

In `frontend/src/components/Layout.tsx`, add to the `TITLES` record:

```typescript
  "/insights": "Insights",
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Insights.tsx frontend/src/App.tsx frontend/src/components/Sidebar.tsx frontend/src/components/Layout.tsx
git commit -m "feat: Insights page with live analysis progress and ranked skills table"
```
