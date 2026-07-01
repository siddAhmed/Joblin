# Career Activities Bank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a freeform career activities document per user and redesign the resume tailor pipeline into a 3-phase LLM flow with SSE progress streaming.

**Architecture:** A nullable `activities_content` column is added to the existing `resume` table. The single-step `tailor_resume` LLM call is replaced with three sequential calls — job analysis, activity selection (drawing from both the reference resume and the activities document), and final LaTeX rewriting — emitted as SSE events from the existing `/resume/tailor` endpoint. A new `/activities` frontend page gives users a Monaco editor with a live markdown preview panel.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, pytest-asyncio, React 19, TypeScript, TanStack Query v5, Monaco Editor, react-markdown, Tailwind CSS.

## Global Constraints

- Never use em dashes in any user-visible string or code comment.
- No `Co-Authored-By` trailer in any commit message.
- All LLM calls use the provider returned by `get_tailor_provider(settings)` — no separate model tier.
- `activities_content` is nullable; the pipeline must work when it is `None`.
- The tailor endpoint remains `POST /resume/tailor` — do not change the HTTP method or path.
- The `build_tailor_prompt` signature change is breaking: `job_description` parameter becomes `selected_items`. Update every call site.
- Follow existing test patterns: `pytest` with `asyncio_mode = auto`, `httpx.AsyncClient` via the `client` fixture, `AsyncMock` for provider methods.
- Frontend: follow the `Resume.tsx` pattern for state management (direct `useEffect` + API calls, not `useQuery` for mutable editor state).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/models/resume.py` | Modify | Add `activities_content` column |
| `backend/alembic/versions/f3a4b5c6d7e8_add_activities_content.py` | Create | DB migration |
| `backend/routers/resume.py` | Modify | GET/PUT activities endpoints; convert tailor to SSE 3-phase |
| `backend/llm/prompts.py` | Modify | Add `build_job_analysis_prompt`, `build_activity_selection_prompt`; update `build_tailor_prompt` |
| `backend/llm/protocol.py` | Modify | Add `analyze_job`, `select_activities` to `LLMProvider`; update `tailor_resume` signature |
| `backend/llm/groq_adapter.py` | Modify | Implement new protocol methods |
| `backend/llm/cerebras_adapter.py` | Modify | Implement new protocol methods |
| `backend/llm/gemini_adapter.py` | Modify | Implement new protocol methods |
| `tests/test_resume.py` | Modify | Tests for activities endpoints and new tailor SSE flow |
| `tests/test_llm.py` | Modify | Tests for new prompt builders and adapter methods |
| `frontend/src/api/activities.ts` | Create | API client for GET/PUT activities |
| `frontend/src/api/resume.ts` | Modify | Add `tailorWithProgress` SSE consumer |
| `frontend/src/pages/Activities.tsx` | Create | Monaco editor + markdown preview page |
| `frontend/src/App.tsx` | Modify | Add `/activities` route |
| `frontend/src/components/Sidebar.tsx` | Modify | Add Activities nav item |
| `frontend/src/pages/Resume.tsx` | Modify | Replace spinner with 3-step SSE progress indicator |

---

## Task 1: DB migration + model change

**Files:**
- Modify: `backend/models/resume.py`
- Create: `backend/alembic/versions/f3a4b5c6d7e8_add_activities_content.py`
- Test: `tests/test_resume.py`

**Interfaces:**
- Produces: `Resume.activities_content: Mapped[str | None]` — used by Tasks 2 and 5.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_resume.py` (after the existing imports):

```python
async def test_activities_column_exists(client):
    # activities_content should be null before any PUT
    response = await client.get("/api/resume/activities")
    assert response.status_code == 200
    assert response.json()["activities_content"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```
cd C:\dev\joblin
pytest tests/test_resume.py::test_activities_column_exists -v
```

Expected: FAIL — `404` or `AttributeError` because neither the column nor the endpoint exist yet.

- [ ] **Step 3: Update the Resume model**

Replace the entire contents of `backend/models/resume.py`:

```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class Resume(Base):
    __tablename__ = "resume"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    tex_content: Mapped[str] = mapped_column(Text, nullable=False)
    activities_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

- [ ] **Step 4: Create the Alembic migration**

Create `backend/alembic/versions/f3a4b5c6d7e8_add_activities_content.py`:

```python
"""add activities_content to resume

Revision ID: f3a4b5c6d7e8
Revises: d9213ed6bef3
Create Date: 2026-07-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "d9213ed6bef3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("resume", sa.Column("activities_content", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("resume", "activities_content")
```

- [ ] **Step 5: Apply the migration**

```
cd C:\dev\joblin
alembic upgrade head
```

Expected: `Running upgrade d9213ed6bef3 -> f3a4b5c6d7e8, add activities_content to resume`

- [ ] **Step 6: Verify test still fails for the right reason**

```
pytest tests/test_resume.py::test_activities_column_exists -v
```

Expected: FAIL — `404` because the endpoint doesn't exist yet (not an `AttributeError`).

- [ ] **Step 7: Commit**

```
git add backend/models/resume.py backend/alembic/versions/f3a4b5c6d7e8_add_activities_content.py
git commit -m "feat: add activities_content column to resume table"
```

---

## Task 2: Activities API endpoints + tests

**Files:**
- Modify: `backend/routers/resume.py`
- Modify: `tests/test_resume.py`

**Interfaces:**
- Consumes: `Resume.activities_content` from Task 1.
- Produces:
  - `GET /resume/activities` → `{"activities_content": str | None, "updated_at": str | None}`
  - `PUT /resume/activities` body `{"activities_content": str}` → same shape

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_resume.py`:

```python
async def test_get_activities_returns_null_when_no_resume(client):
    response = await client.get("/api/resume/activities")
    assert response.status_code == 200
    assert response.json()["activities_content"] is None
    assert response.json()["updated_at"] is None


async def test_save_activities_then_get(client):
    content = "# Work Experience\n- Built a thing\n"
    put = await client.put("/api/resume/activities", json={"activities_content": content})
    assert put.status_code == 200
    assert put.json()["activities_content"] == content
    assert "updated_at" in put.json()

    get = await client.get("/api/resume/activities")
    assert get.status_code == 200
    assert get.json()["activities_content"] == content


async def test_save_activities_twice_overwrites(client):
    await client.put("/api/resume/activities", json={"activities_content": "v1"})
    await client.put("/api/resume/activities", json={"activities_content": "v2"})
    get = await client.get("/api/resume/activities")
    assert get.json()["activities_content"] == "v2"


async def test_save_activities_does_not_change_tex_content(client):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    await client.put("/api/resume", json={"tex_content": tex})
    await client.put("/api/resume/activities", json={"activities_content": "# Activities"})
    get = await client.get("/api/resume")
    assert get.json()["tex_content"] == tex
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_resume.py::test_get_activities_returns_null_when_no_resume tests/test_resume.py::test_save_activities_then_get tests/test_resume.py::test_save_activities_twice_overwrites tests/test_resume.py::test_save_activities_does_not_change_tex_content -v
```

Expected: All FAIL with 404 or 405.

- [ ] **Step 3: Add the endpoints**

In `backend/routers/resume.py`, add after the existing `class ResumeSave(BaseModel)` and before `CompileRequest`:

```python
class ActivitiesSave(BaseModel):
    activities_content: str


@router.get("/activities")
async def get_activities(session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    if resume is None:
        return {"activities_content": None, "updated_at": None}
    return {
        "activities_content": resume.activities_content,
        "updated_at": resume.updated_at.isoformat() if resume.updated_at else None,
    }


@router.put("/activities")
async def save_activities(body: ActivitiesSave, session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if resume is None:
        resume = Resume(
            user_id=current_user.id,
            tex_content="",
            activities_content=body.activities_content,
            updated_at=now,
        )
        session.add(resume)
    else:
        resume.activities_content = body.activities_content
        resume.updated_at = now
    await session.commit()
    return {
        "activities_content": resume.activities_content,
        "updated_at": resume.updated_at.isoformat(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_resume.py::test_get_activities_returns_null_when_no_resume tests/test_resume.py::test_save_activities_then_get tests/test_resume.py::test_save_activities_twice_overwrites tests/test_resume.py::test_save_activities_does_not_change_tex_content -v
```

Expected: All PASS.

- [ ] **Step 5: Run the full test suite to check for regressions**

```
pytest tests/test_resume.py -v
```

Expected: All existing tests plus the 5 new ones pass. The `test_activities_column_exists` test from Task 1 should also pass now.

- [ ] **Step 6: Commit**

```
git add backend/routers/resume.py tests/test_resume.py
git commit -m "feat: add GET/PUT /resume/activities endpoints"
```

---

## Task 3: LLM prompt builders (3-phase) + tests

**Files:**
- Modify: `backend/llm/prompts.py`
- Modify: `tests/test_llm.py`

**Interfaces:**
- Produces:
  - `build_job_analysis_prompt(job_description: str) -> tuple[str, str]`
  - `build_activity_selection_prompt(requirements: dict, tex_content: str, activities_content: str | None) -> tuple[str, str]`
  - `build_tailor_prompt(tex_content: str, selected_items: str) -> tuple[str, str]` — **signature change**: `job_description` parameter replaced by `selected_items`

- [ ] **Step 1: Write the failing tests**

Read the current `tests/test_llm.py` to find where to insert new tests, then add:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_llm.py::test_build_job_analysis_prompt_contains_job_description tests/test_llm.py::test_build_activity_selection_prompt_includes_all_sources tests/test_llm.py::test_build_activity_selection_prompt_handles_none_activities tests/test_llm.py::test_build_tailor_prompt_uses_selected_items -v
```

Expected: All FAIL with `ImportError` or `AssertionError`.

- [ ] **Step 3: Update `backend/llm/prompts.py`**

Replace the entire file:

```python
import json
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
        "Score >= 0.70 means strong match. 0.40-0.69 means borderline. < 0.40 means discard. "
        "If the candidate's profile specifies a location or work authorization constraint, "
        "score any job < 0.40 that is not in the candidate's country, not fully remote, "
        "and does not explicitly mention visa sponsorship or work permit support."
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


def build_job_analysis_prompt(job_description: str) -> tuple[str, str]:
    system = (
        "You are a job requirements analyst. Extract the key requirements from a job description. "
        "Return JSON only, no other text: "
        '{"required_skills": [...], "preferred_skills": [...], "key_themes": [...], '
        '"seniority_signals": [...], "keywords": [...]}'
    )
    user = f"Job description:\n\n{job_description[:3000]}"
    return system, user


def build_activity_selection_prompt(
    requirements: dict,
    tex_content: str,
    activities_content: str | None,
) -> tuple[str, str]:
    system = (
        "You are a career coach selecting content for a resume tailoring task. "
        "Given job requirements, a reference resume, and optionally an activities bank, "
        "select the 6-8 most relevant items to emphasize in the final resume. "
        "Return a plain-text numbered list. Be selective - only items that genuinely strengthen this application. "
        "Do not reproduce LaTeX syntax. For items from the resume, quote or paraphrase the key phrase. "
        "For items from the activities bank, copy the relevant text verbatim."
    )
    req_text = json.dumps(requirements, indent=2)
    activities_section = (
        f"\n\nActivities bank:\n{activities_content}" if activities_content else ""
    )
    user = (
        f"Job requirements:\n{req_text}\n\n"
        f"Reference resume (LaTeX):\n{tex_content}"
        f"{activities_section}\n\n"
        "Select the 6-8 most relevant items from the resume"
        + (" and activities bank" if activities_content else "")
        + " for this role."
    )
    return system, user


def build_tailor_prompt(tex_content: str, selected_items: str) -> tuple[str, str]:
    system = (
        "You are a resume tailoring expert. Given a LaTeX resume and a curated list of items to emphasize, "
        "return ONLY the modified LaTeX source code. No explanation, no markdown code fences, "
        "no commentary of any kind - just the raw .tex content. "
        "Critical LaTeX rules: always escape special characters in text -- use \\& not &, "
        "\\% not %, \\$ not $, \\# not #, \\_ not _ (outside math/commands). "
        "Never introduce these characters unescaped inside \\textbf{}, \\textit{}, or any text context."
    )
    user = (
        f"Here is my LaTeX resume:\n\n{tex_content}\n\n"
        f"Items to emphasize in this tailored version:\n\n{selected_items}\n\n"
        "Please modify the resume to incorporate and highlight these items. "
        "Adjust bullet points, reorder sections if beneficial, and ensure the selected items are prominent. "
        "Preserve the original LaTeX template structure and commands exactly."
    )
    return system, user
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_llm.py::test_build_job_analysis_prompt_contains_job_description tests/test_llm.py::test_build_activity_selection_prompt_includes_all_sources tests/test_llm.py::test_build_activity_selection_prompt_handles_none_activities tests/test_llm.py::test_build_tailor_prompt_uses_selected_items -v
```

Expected: All PASS.

- [ ] **Step 5: Run full test_llm suite**

```
pytest tests/test_llm.py -v
```

Expected: All pass. If any existing tests import `build_tailor_prompt` with `job_description` kwarg, fix those calls to use `selected_items`.

- [ ] **Step 6: Commit**

```
git add backend/llm/prompts.py tests/test_llm.py
git commit -m "feat: add 3-phase LLM prompt builders for activity selection pipeline"
```

---

## Task 4: LLM protocol + adapter implementations + tests

**Files:**
- Modify: `backend/llm/protocol.py`
- Modify: `backend/llm/groq_adapter.py`
- Modify: `backend/llm/cerebras_adapter.py`
- Modify: `backend/llm/gemini_adapter.py`
- Modify: `tests/test_llm.py`

**Interfaces:**
- Consumes: `build_job_analysis_prompt`, `build_activity_selection_prompt`, `build_tailor_prompt` from Task 3.
- Produces:
  - `LLMProvider.analyze_job(job_description: str) -> dict`
  - `LLMProvider.select_activities(requirements: dict, tex_content: str, activities_content: str | None) -> str`
  - `LLMProvider.tailor_resume(tex_content: str, selected_items: str) -> str` — **signature change**

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_llm.py`:

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch
from backend.llm.groq_adapter import GroqAdapter


async def test_groq_analyze_job_returns_dict():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Docker"],
        "key_themes": ["backend"],
        "seniority_signals": ["senior"],
        "keywords": ["API"],
    })
    mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("backend.llm.groq_adapter.AsyncGroq", return_value=mock_client):
        adapter = GroqAdapter(api_key="test", filter_model="m1", summarize_model="m2")
        result = await adapter.analyze_job("We need a Python/FastAPI engineer.")

    assert result["required_skills"] == ["Python", "FastAPI"]
    assert "key_themes" in result


async def test_groq_analyze_job_returns_empty_dict_on_parse_error():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not valid json"
    mock_response.usage = MagicMock(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("backend.llm.groq_adapter.AsyncGroq", return_value=mock_client):
        adapter = GroqAdapter(api_key="test", filter_model="m1", summarize_model="m2")
        result = await adapter.analyze_job("bad response job")

    assert result == {"required_skills": [], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []}


async def test_groq_select_activities_returns_string():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "1. Python experience\n2. FastAPI projects"
    mock_response.usage = MagicMock(prompt_tokens=200, completion_tokens=30, total_tokens=230)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("backend.llm.groq_adapter.AsyncGroq", return_value=mock_client):
        adapter = GroqAdapter(api_key="test", filter_model="m1", summarize_model="m2")
        result = await adapter.select_activities(
            requirements={"required_skills": ["Python"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []},
            tex_content=r"\documentclass{article}\begin{document}Python dev\end{document}",
            activities_content="## Projects\n- Built a REST API",
        )

    assert "Python experience" in result
    assert "FastAPI projects" in result


async def test_groq_tailor_resume_uses_selected_items():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = r"\documentclass{article}\begin{document}Tailored\end{document}"
    mock_response.usage = MagicMock(prompt_tokens=500, completion_tokens=400, total_tokens=900)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("backend.llm.groq_adapter.AsyncGroq", return_value=mock_client):
        adapter = GroqAdapter(api_key="test", filter_model="m1", summarize_model="m2")
        result = await adapter.tailor_resume(
            tex_content=r"\documentclass{article}\begin{document}Original\end{document}",
            selected_items="1. Python\n2. FastAPI",
        )

    assert "Tailored" in result
    call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "1. Python" in user_content
    assert "2. FastAPI" in user_content
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_llm.py::test_groq_analyze_job_returns_dict tests/test_llm.py::test_groq_analyze_job_returns_empty_dict_on_parse_error tests/test_llm.py::test_groq_select_activities_returns_string tests/test_llm.py::test_groq_tailor_resume_uses_selected_items -v
```

Expected: All FAIL with `AttributeError` because the protocol and adapter don't have these methods yet.

- [ ] **Step 3: Update `backend/llm/protocol.py`**

Replace the entire file:

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

    async def extract_skills(self, title: str, description: str) -> list[str]: ...

    async def analyze_job(self, job_description: str) -> dict: ...

    async def select_activities(
        self,
        requirements: dict,
        tex_content: str,
        activities_content: str | None,
    ) -> str: ...

    async def tailor_resume(self, tex_content: str, selected_items: str) -> str: ...
```

- [ ] **Step 4: Update `backend/llm/groq_adapter.py`**

Replace the entire file:

```python
import json
from groq import AsyncGroq

from backend.llm.protocol import CriteriaConfig, FeedbackExample, FilterResult
from backend.llm.prompts import (
    build_filter_prompt,
    build_summarize_prompt,
    build_skills_prompt,
    build_job_analysis_prompt,
    build_activity_selection_prompt,
    build_tailor_prompt,
)


class GroqAdapter:
    def __init__(self, api_key: str, filter_model: str = "llama-3.1-8b-instant", summarize_model: str = "llama-3.1-8b-instant"):
        self._client = AsyncGroq(api_key=api_key)
        self._filter_model = filter_model
        self._summarize_model = summarize_model
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
            model=self._filter_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
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
            model=self._summarize_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        self._record_usage(response.usage)
        return response.choices[0].message.content or ""

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

    async def analyze_job(self, job_description: str) -> dict:
        system, user = build_job_analysis_prompt(job_description)
        response = await self._client.chat.completions.create(
            model=self._summarize_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
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
            model=self._summarize_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.3,
            max_tokens=1024,
        )
        self._record_usage(response.usage)
        return response.choices[0].message.content or ""

    async def tailor_resume(self, tex_content: str, selected_items: str) -> str:
        system, user = build_tailor_prompt(tex_content, selected_items)
        response = await self._client.chat.completions.create(
            model=self._summarize_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        self._record_usage(response.usage)
        raw = response.choices[0].message.content or ""
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
        return raw.strip()
```

- [ ] **Step 5: Update `backend/llm/cerebras_adapter.py`**

Replace the entire file:

```python
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
```

- [ ] **Step 6: Update `backend/llm/gemini_adapter.py`**

Replace the entire file:

```python
import json
from google import genai

from backend.llm.protocol import CriteriaConfig, FeedbackExample, FilterResult
from backend.llm.prompts import (
    build_filter_prompt,
    build_summarize_prompt,
    build_skills_prompt,
    build_job_analysis_prompt,
    build_activity_selection_prompt,
    build_tailor_prompt,
)


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

    async def analyze_job(self, job_description: str) -> dict:
        system, user = build_job_analysis_prompt(job_description)
        prompt = f"{system}\n\n{user}"
        response = await self._client.aio.models.generate_content(
            model=self._summarize_model,
            contents=prompt,
        )
        self._record_usage(response)
        raw = response.text or ""
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
        prompt = f"{system}\n\n{user}"
        response = await self._client.aio.models.generate_content(
            model=self._summarize_model,
            contents=prompt,
        )
        self._record_usage(response)
        return response.text or ""

    async def tailor_resume(self, tex_content: str, selected_items: str) -> str:
        system, user = build_tailor_prompt(tex_content, selected_items)
        prompt = f"{system}\n\n{user}"
        response = await self._client.aio.models.generate_content(
            model=self._summarize_model,
            contents=prompt,
        )
        self._record_usage(response)
        raw = response.text or ""
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
        return raw.strip()
```

- [ ] **Step 7: Run the new tests**

```
pytest tests/test_llm.py::test_groq_analyze_job_returns_dict tests/test_llm.py::test_groq_analyze_job_returns_empty_dict_on_parse_error tests/test_llm.py::test_groq_select_activities_returns_string tests/test_llm.py::test_groq_tailor_resume_uses_selected_items -v
```

Expected: All PASS.

- [ ] **Step 8: Run full test_llm suite**

```
pytest tests/test_llm.py -v
```

Expected: All pass (existing tests unaffected; `build_tailor_prompt` is not called directly in the old adapter tests so no breakage there).

- [ ] **Step 9: Commit**

```
git add backend/llm/protocol.py backend/llm/groq_adapter.py backend/llm/cerebras_adapter.py backend/llm/gemini_adapter.py tests/test_llm.py
git commit -m "feat: add analyze_job and select_activities to LLM protocol and all adapters"
```

---

## Task 5: Tailor endpoint SSE + 3-phase pipeline + tests

**Files:**
- Modify: `backend/routers/resume.py`
- Modify: `tests/test_resume.py`

**Interfaces:**
- Consumes: `provider.analyze_job`, `provider.select_activities`, `provider.tailor_resume` from Task 4; `Resume.activities_content` from Task 1.
- Produces: `POST /resume/tailor` now returns `StreamingResponse` with `media_type="text/event-stream"`, emitting `phase`, `done`, and `error` SSE events.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_resume.py` (also add `import json` at the top if not already present):

```python
import json


def _parse_sse(text: str) -> list[dict]:
    events = []
    for chunk in text.split("\n\n"):
        if not chunk.strip():
            continue
        parts: dict = {}
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                parts["event"] = line[7:].strip()
            elif line.startswith("data: "):
                parts["data"] = json.loads(line[6:].strip())
        if parts:
            events.append(parts)
    return events


async def test_tailor_resume_success_sse(client, seeded_job_id):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    tailored = r"\documentclass{article}\begin{document}Tailored resume\end{document}"
    await client.put("/api/resume", json={"tex_content": tex})

    mock_provider = MagicMock()
    mock_provider.analyze_job = AsyncMock(return_value={"required_skills": ["Python"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []})
    mock_provider.select_activities = AsyncMock(return_value="1. Python experience")
    mock_provider.tailor_resume = AsyncMock(return_value=tailored)

    with patch("backend.routers.resume.get_tailor_provider", return_value=mock_provider), \
         patch("backend.routers.resume.get_all_settings", return_value={}):
        response = await client.post("/api/resume/tailor", json={"job_id": seeded_job_id})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = _parse_sse(response.text)
    phase_events = [e for e in events if e.get("event") == "phase"]
    done_events = [e for e in events if e.get("event") == "done"]

    assert len(phase_events) == 3
    assert phase_events[0]["data"]["phase"] == 1
    assert phase_events[1]["data"]["phase"] == 2
    assert phase_events[2]["data"]["phase"] == 3
    assert len(done_events) == 1
    assert done_events[0]["data"]["tex_content"] == tailored

    mock_provider.analyze_job.assert_called_once_with(
        job_description="Python, distributed systems, REST APIs, PostgreSQL"
    )
    mock_provider.select_activities.assert_called_once_with(
        requirements={"required_skills": ["Python"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []},
        tex_content=tex,
        activities_content=None,
    )
    mock_provider.tailor_resume.assert_called_once_with(
        tex_content=tex,
        selected_items="1. Python experience",
    )


async def test_tailor_resume_sse_includes_activities_content(client, seeded_job_id):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    activities = "## Side Projects\n- Built a Go microservice"
    await client.put("/api/resume", json={"tex_content": tex})
    await client.put("/api/resume/activities", json={"activities_content": activities})

    mock_provider = MagicMock()
    mock_provider.analyze_job = AsyncMock(return_value={"required_skills": ["Go"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []})
    mock_provider.select_activities = AsyncMock(return_value="1. Go microservice")
    mock_provider.tailor_resume = AsyncMock(return_value=tex)

    with patch("backend.routers.resume.get_tailor_provider", return_value=mock_provider), \
         patch("backend.routers.resume.get_all_settings", return_value={}):
        await client.post("/api/resume/tailor", json={"job_id": seeded_job_id})

    mock_provider.select_activities.assert_called_once_with(
        requirements={"required_skills": ["Go"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []},
        tex_content=tex,
        activities_content=activities,
    )


async def test_tailor_resume_sse_error_event_on_provider_failure(client, seeded_job_id):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    await client.put("/api/resume", json={"tex_content": tex})

    mock_provider = MagicMock()
    mock_provider.analyze_job = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    with patch("backend.routers.resume.get_tailor_provider", return_value=mock_provider), \
         patch("backend.routers.resume.get_all_settings", return_value={}):
        response = await client.post("/api/resume/tailor", json={"job_id": seeded_job_id})

    assert response.status_code == 200
    events = _parse_sse(response.text)
    error_events = [e for e in events if e.get("event") == "error"]
    assert len(error_events) == 1
    assert "LLM unavailable" in error_events[0]["data"]["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_resume.py::test_tailor_resume_success_sse tests/test_resume.py::test_tailor_resume_sse_includes_activities_content tests/test_resume.py::test_tailor_resume_sse_error_event_on_provider_failure -v
```

Expected: All FAIL (the endpoint returns JSON, not SSE; `analyze_job` call not found).

- [ ] **Step 3: Update `backend/routers/resume.py`**

Replace the entire file:

```python
import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.llm.factory import get_tailor_provider
from backend.models.user_job import UserJob
from backend.models.raw_job import RawJob
from backend.models.resume import Resume

router = APIRouter(prefix="/resume", tags=["resume"])
Session = Annotated[AsyncSession, Depends(get_session)]


class ResumeSave(BaseModel):
    tex_content: str


class ActivitiesSave(BaseModel):
    activities_content: str


@router.get("")
async def get_resume(session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    if resume is None or not resume.tex_content:
        raise HTTPException(status_code=404, detail="No resume found")
    return {"tex_content": resume.tex_content, "updated_at": resume.updated_at.isoformat()}


@router.put("")
async def save_resume(body: ResumeSave, session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if resume is None:
        resume = Resume(user_id=current_user.id, tex_content=body.tex_content, updated_at=now)
        session.add(resume)
    else:
        resume.tex_content = body.tex_content
        resume.updated_at = now
    await session.commit()
    return {"tex_content": resume.tex_content, "updated_at": resume.updated_at.isoformat()}


@router.get("/activities")
async def get_activities(session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    if resume is None:
        return {"activities_content": None, "updated_at": None}
    return {
        "activities_content": resume.activities_content,
        "updated_at": resume.updated_at.isoformat() if resume.updated_at else None,
    }


@router.put("/activities")
async def save_activities(body: ActivitiesSave, session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if resume is None:
        resume = Resume(
            user_id=current_user.id,
            tex_content="",
            activities_content=body.activities_content,
            updated_at=now,
        )
        session.add(resume)
    else:
        resume.activities_content = body.activities_content
        resume.updated_at = now
    await session.commit()
    return {
        "activities_content": resume.activities_content,
        "updated_at": resume.updated_at.isoformat(),
    }


class CompileRequest(BaseModel):
    tex_content: str


@router.post("/compile")
async def compile_resume(body: CompileRequest):
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "resume.tex"
        tex_path.write_text(body.tex_content, encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            "tectonic", str(tex_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tmpdir,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            proc.kill()
            raise HTTPException(status_code=422, detail="Compilation timed out after 60 seconds")
        if proc.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=stderr.decode("utf-8", errors="replace"),
            )
        pdf_bytes = (Path(tmpdir) / "resume.pdf").read_bytes()
    return Response(content=pdf_bytes, media_type="application/pdf")


class TailorRequest(BaseModel):
    job_id: int


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/tailor")
async def tailor_resume_endpoint(body: TailorRequest, session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=404, detail="No reference resume found. Upload a .tex file first.")

    row = (await session.execute(
        select(UserJob, RawJob)
        .join(RawJob, UserJob.raw_job_id == RawJob.id)
        .where(UserJob.id == body.job_id, UserJob.user_id == current_user.id)
    )).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    uj, rj = row

    if not rj.raw_description:
        raise HTTPException(
            status_code=422,
            detail="This job has no description yet. Run a scan to fetch full job details first.",
        )

    settings = await get_all_settings(session, user_id=current_user.id)
    provider = get_tailor_provider(settings)
    tex_content = resume.tex_content
    activities_content = resume.activities_content
    job_description = rj.raw_description

    async def generate():
        try:
            yield _sse("phase", {"phase": 1, "label": "Analyzing job requirements..."})
            requirements = await provider.analyze_job(job_description=job_description)

            yield _sse("phase", {"phase": 2, "label": "Selecting relevant experiences..."})
            selected_items = await provider.select_activities(
                requirements=requirements,
                tex_content=tex_content,
                activities_content=activities_content,
            )

            yield _sse("phase", {"phase": 3, "label": "Tailoring resume..."})
            tailored_tex = await provider.tailor_resume(
                tex_content=tex_content,
                selected_items=selected_items,
            )

            yield _sse("done", {"tex_content": tailored_tex})
        except Exception as exc:
            yield _sse("error", {"detail": str(exc)})

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 4: Run the new tests**

```
pytest tests/test_resume.py::test_tailor_resume_success_sse tests/test_resume.py::test_tailor_resume_sse_includes_activities_content tests/test_resume.py::test_tailor_resume_sse_error_event_on_provider_failure -v
```

Expected: All PASS.

- [ ] **Step 5: Add regression test for get_resume with empty tex_content**

Add to `tests/test_resume.py`:

```python
async def test_get_resume_returns_404_when_only_activities_saved(client):
    await client.put("/api/resume/activities", json={"activities_content": "# Activities"})
    response = await client.get("/api/resume")
    assert response.status_code == 404
```

Run it:

```
pytest tests/test_resume.py::test_get_resume_returns_404_when_only_activities_saved -v
```

Expected: PASS (the updated `get_resume` checks `not resume.tex_content`).

- [ ] **Step 7: Update the old `test_tailor_resume_success` test**

The old test expects `response.json()["tex_content"]` which no longer works. Replace `test_tailor_resume_success` in `tests/test_resume.py` with:

```python
async def test_tailor_resume_success(client, seeded_job_id):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    tailored = r"\documentclass{article}\begin{document}Tailored resume\end{document}"
    await client.put("/api/resume", json={"tex_content": tex})

    mock_provider = MagicMock()
    mock_provider.analyze_job = AsyncMock(return_value={"required_skills": ["Python"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []})
    mock_provider.select_activities = AsyncMock(return_value="1. Python")
    mock_provider.tailor_resume = AsyncMock(return_value=tailored)

    with patch("backend.routers.resume.get_tailor_provider", return_value=mock_provider), \
         patch("backend.routers.resume.get_all_settings", return_value={}):
        response = await client.post("/api/resume/tailor", json={"job_id": seeded_job_id})

    assert response.status_code == 200
    events = _parse_sse(response.text)
    done = next(e for e in events if e.get("event") == "done")
    assert done["data"]["tex_content"] == tailored
```

- [ ] **Step 8: Run the full test suite**

```
pytest tests/test_resume.py -v
```

Expected: All pass, no failures.

- [ ] **Step 9: Commit**

```
git add backend/routers/resume.py tests/test_resume.py
git commit -m "feat: convert tailor endpoint to 3-phase SSE pipeline"
```

---

## Task 6: Frontend Activities page + routing + sidebar

**Files:**
- Create: `frontend/src/api/activities.ts`
- Create: `frontend/src/pages/Activities.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`

**Interfaces:**
- Consumes: `GET /resume/activities` and `PUT /resume/activities` from Task 2.
- Produces: `/activities` route rendering the Activities page.

- [ ] **Step 1: Install react-markdown**

```
cd C:\dev\joblin\frontend
npm install react-markdown
```

Expected: `added 1 package` (or similar). No peer dependency errors.

- [ ] **Step 2: Create `frontend/src/api/activities.ts`**

```typescript
import { api } from "./client";

export interface ActivitiesData {
  activities_content: string | null;
  updated_at: string | null;
}

export const activitiesApi = {
  get: () =>
    api.get<ActivitiesData>("/resume/activities").then((r) => r.data),
  save: (activities_content: string) =>
    api
      .put<ActivitiesData>("/resume/activities", { activities_content })
      .then((r) => r.data),
};
```

- [ ] **Step 3: Create `frontend/src/pages/Activities.tsx`**

```tsx
import { useState, useEffect } from "react";
import Editor from "@monaco-editor/react";
import ReactMarkdown from "react-markdown";
import { activitiesApi } from "@/api/activities";

const PLACEHOLDER = `# Career Activities

Use this document to keep a running record of everything you have done professionally.
The AI uses this alongside your resume when tailoring for a specific job.

## Work Experience
- 

## Projects
- 

## Skills & Certifications
- 
`;

export function Activities() {
  const [content, setContent] = useState("");
  const [savedContent, setSavedContent] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(true);

  useEffect(() => {
    activitiesApi
      .get()
      .then((data) => {
        if (data.activities_content !== null) {
          setContent(data.activities_content);
          setSavedContent(data.activities_content);
          setSavedAt(data.updated_at);
        }
      })
      .catch(() => {});
  }, []);

  async function handleSave() {
    setIsSaving(true);
    setSaveError(null);
    try {
      const data = await activitiesApi.save(content);
      setSavedContent(data.activities_content ?? "");
      setSavedAt(data.updated_at);
    } catch {
      setSaveError("Failed to save. Please try again.");
    } finally {
      setIsSaving(false);
    }
  }

  const isDirty = savedContent !== null && content !== savedContent;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-[#1e1e1e] bg-[#0d0d0d] shrink-0">
        <span className="text-xs font-medium text-[#ccc]">Activities</span>
        <div className="ml-auto flex items-center gap-3">
          {saveError && (
            <span className="text-[11px] text-red-400">{saveError}</span>
          )}
          {!saveError && savedAt && !isDirty && (
            <span className="text-[11px] text-[#555]">
              Saved {new Date(savedAt).toLocaleTimeString()}
            </span>
          )}
          {isDirty && (
            <span className="text-[11px] text-[#f59e0b]">Unsaved changes</span>
          )}
          <button
            onClick={handleSave}
            disabled={isSaving || !isDirty}
            className="text-xs border border-[#2a5c2a] rounded px-3 py-1 text-[#4ade80] hover:bg-[#1a3a1a] disabled:opacity-40"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {/* Two-panel layout */}
      <div className="flex flex-1 min-h-0">
        {/* Editor */}
        <div
          className={`min-w-0 border-r border-[#1e1e1e] ${previewOpen ? "flex-1" : "flex-1"}`}
        >
          <Editor
            height="100%"
            language="markdown"
            theme="vs-dark"
            value={content || ""}
            onChange={(v) => setContent(v ?? "")}
            options={{
              fontSize: 13,
              minimap: { enabled: false },
              wordWrap: "on",
              scrollBeyondLastLine: false,
              lineNumbers: "off",
              placeholder: PLACEHOLDER,
            }}
          />
        </div>

        {/* Preview panel */}
        {previewOpen && (
          <div className="w-[45%] shrink-0 flex flex-col min-h-0 bg-[#0a0a0a]">
            <div className="flex items-center justify-between px-3 py-1.5 border-b border-[#1e1e1e] shrink-0">
              <span className="text-[10px] text-[#444]">Preview</span>
              <button
                onClick={() => setPreviewOpen(false)}
                className="text-[10px] text-[#555] hover:text-[#888] border border-[#2a2a2a] rounded px-1.5 py-0.5"
                title="Close preview"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-auto px-5 py-4 prose-activities">
              {content ? (
                <div className="text-[#ccc] text-sm leading-relaxed [&_h1]:text-[#e5e5e5] [&_h1]:text-base [&_h1]:font-semibold [&_h1]:mt-0 [&_h1]:mb-3 [&_h2]:text-[#aaa] [&_h2]:text-sm [&_h2]:font-medium [&_h2]:mt-4 [&_h2]:mb-2 [&_h3]:text-[#999] [&_h3]:text-xs [&_h3]:font-medium [&_h3]:mt-3 [&_h3]:mb-1 [&_ul]:pl-4 [&_ul]:space-y-0.5 [&_li]:text-[#bbb] [&_li]:text-xs [&_p]:text-xs [&_p]:text-[#bbb] [&_strong]:text-[#ddd] [&_code]:bg-[#1a1a1a] [&_code]:text-[#a78bfa] [&_code]:px-1 [&_code]:rounded [&_code]:text-xs">
                  <ReactMarkdown>{content}</ReactMarkdown>
                </div>
              ) : (
                <div className="text-[#333] text-xs italic">
                  Start typing to see a preview...
                </div>
              )}
            </div>
          </div>
        )}

        {/* Expand button when preview is closed */}
        {!previewOpen && (
          <div className="flex items-start pt-2 pr-2 shrink-0">
            <button
              onClick={() => setPreviewOpen(true)}
              className="text-[10px] text-[#555] hover:text-[#888] border border-[#2a2a2a] rounded px-1.5 py-0.5"
              title="Open preview"
            >
              Preview
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add the route to `frontend/src/App.tsx`**

Add the import after the existing Resume import:

```typescript
import { Activities } from "./pages/Activities";
```

Add the route inside the `<Route element={<Layout />}>` block, after the resume route:

```typescript
<Route path="/activities" element={<Activities />} />
```

The routes block should look like:

```tsx
<Route element={<Layout />}>
  <Route path="/" element={<Dashboard />} />
  <Route path="/matches" element={<Matches />} />
  <Route path="/applications" element={<Applications />} />
  <Route path="/jobs" element={<Jobs />} />
  <Route path="/companies" element={<Companies />} />
  <Route path="/runs" element={<Runs />} />
  <Route path="/runs/:id" element={<RunDetail />} />
  <Route path="/usage" element={<Usage />} />
  <Route path="/insights" element={<Insights />} />
  <Route path="/resume" element={<Resume />} />
  <Route path="/activities" element={<Activities />} />
  <Route path="/settings" element={<Settings />} />
</Route>
```

- [ ] **Step 5: Add the Activities nav item to `frontend/src/components/Sidebar.tsx`**

Replace the `NAV` constant with:

```typescript
const NAV = [
  { label: "Dashboard", icon: "◼", path: "/" },
  { label: "Matches", icon: "★", path: "/matches" },
  { label: "Applications", icon: "⊙", path: "/applications" },
  { label: "All Jobs", icon: "≡", path: "/jobs" },
  { label: "Companies", icon: "⊞", path: "/companies", warn: true },
  { label: "Runs", icon: "▶", path: "/runs" },
  { label: "Usage", icon: "◈", path: "/usage" },
  { label: "Insights", icon: "◎", path: "/insights" },
  { label: "Resume", icon: "⊡", path: "/resume" },
  { label: "Activities", icon: "⊟", path: "/activities" },
  { label: "Settings", icon: "⚙", path: "/settings" },
] as const;
```

- [ ] **Step 6: Build the frontend to check for TypeScript errors**

```
cd C:\dev\joblin\frontend
npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 7: Commit**

```
git add frontend/src/api/activities.ts frontend/src/pages/Activities.tsx frontend/src/App.tsx frontend/src/components/Sidebar.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat: add Career Activities page with Monaco editor and markdown preview"
```

---

## Task 7: Frontend Resume page SSE tailor progress

**Files:**
- Modify: `frontend/src/api/resume.ts`
- Modify: `frontend/src/pages/Resume.tsx`

**Interfaces:**
- Consumes: SSE stream from `POST /resume/tailor` from Task 5.
- Produces: A 3-step progress indicator that replaces the "Tailoring..." spinner.

- [ ] **Step 1: Update `frontend/src/api/resume.ts`**

Replace the entire file:

```typescript
import { api } from "./client";

export interface ResumeData {
  tex_content: string;
  updated_at: string;
}

export const resumeApi = {
  get: () =>
    api.get<ResumeData>("/resume").then((r) => r.data),
  save: (tex_content: string) =>
    api.put<ResumeData>("/resume", { tex_content }).then((r) => r.data),
  compile: (tex_content: string) =>
    api
      .post<ArrayBuffer>("/resume/compile", { tex_content }, { responseType: "arraybuffer" })
      .then((r) => r.data),
};

export async function tailorWithProgress(
  job_id: number,
  onPhase: (phase: number, label: string) => void
): Promise<string> {
  const response = await fetch("/api/resume/tailor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Tailoring failed" }));
    throw new Error(err.detail || "Tailoring failed");
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      if (!chunk.trim()) continue;
      let eventType = "message";
      let dataStr = "";
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) dataStr = line.slice(6).trim();
      }
      if (!dataStr) continue;
      const data = JSON.parse(dataStr);
      if (eventType === "phase") onPhase(data.phase, data.label);
      else if (eventType === "done") return data.tex_content as string;
      else if (eventType === "error") throw new Error(data.detail || "Tailoring failed");
    }
  }

  throw new Error("Stream ended without completion");
}
```

- [ ] **Step 2: Update `handleTailor` and tailor UI state in `frontend/src/pages/Resume.tsx`**

Add `tailorWithProgress` to the import line at the top of `Resume.tsx`. Replace:

```typescript
import { resumeApi } from "@/api/resume";
```

with:

```typescript
import { resumeApi, tailorWithProgress } from "@/api/resume";
```

Replace the `isTailoring` state with two new states. Find and replace the block:

```typescript
  const [isTailoring, setIsTailoring] = useState(false);
```

with:

```typescript
  const [tailorPhase, setTailorPhase] = useState<number>(0);
  const [tailorPhaseLabel, setTailorPhaseLabel] = useState<string>("");
```

Replace the `handleTailor` function:

```typescript
  async function handleTailor() {
    if (!selectedJobId) return;
    setIsTailoring(true);
    setTailorError(null);
    try {
      const result = await resumeApi.tailor(Number(selectedJobId));
      setEditorContent(result.tex_content);
      const match = matches.find((m) => m.job_id === Number(selectedJobId));
      setTailoredFor({
        jobId: Number(selectedJobId),
        title: match?.job_title ?? "Unknown",
        company: match?.company_name ?? "Unknown",
      });
    } catch (err: any) {
      setTailorError(err?.response?.data?.detail || "Tailoring failed");
    } finally {
      setIsTailoring(false);
    }
  }
```

with:

```typescript
  async function handleTailor() {
    if (!selectedJobId) return;
    setTailorPhase(1);
    setTailorPhaseLabel("Analyzing job requirements...");
    setTailorError(null);
    try {
      const texContent = await tailorWithProgress(
        Number(selectedJobId),
        (phase, label) => {
          setTailorPhase(phase);
          setTailorPhaseLabel(label);
        }
      );
      setEditorContent(texContent);
      const match = matches.find((m) => m.job_id === Number(selectedJobId));
      setTailoredFor({
        jobId: Number(selectedJobId),
        title: match?.job_title ?? "Unknown",
        company: match?.company_name ?? "Unknown",
      });
    } catch (err: any) {
      setTailorError(err?.message || "Tailoring failed");
    } finally {
      setTailorPhase(0);
      setTailorPhaseLabel("");
    }
  }
```

Replace the tailor button in the toolbar JSX. Find:

```tsx
        <button
          onClick={handleTailor}
          disabled={!selectedJobId || !hasReference || isTailoring}
          className="text-xs border border-[#4e4e9f] rounded px-3 py-1 text-[#a78bfa] hover:bg-[#1a1a3a] disabled:opacity-40"
        >
          {isTailoring ? "Tailoring..." : "✦ Tailor"}
        </button>
```

Replace with:

```tsx
        <button
          onClick={handleTailor}
          disabled={!selectedJobId || !hasReference || tailorPhase > 0}
          className="text-xs border border-[#4e4e9f] rounded px-3 py-1 text-[#a78bfa] hover:bg-[#1a1a3a] disabled:opacity-40"
        >
          {tailorPhase > 0 ? "Tailoring..." : "✦ Tailor"}
        </button>
```

Add the progress indicator below the tailor error block. Find the closing `{/* Compile error */}` block and insert after it (before the two-panel editor div):

```tsx
      {/* Tailor progress */}
      {tailorPhase > 0 && (
        <div className="px-4 py-2 border-b border-[#1e1e1e] bg-[#0a0a0a] shrink-0">
          <div className="flex flex-col gap-1">
            {[
              { n: 1, label: "Analyzing job requirements..." },
              { n: 2, label: "Selecting relevant experiences..." },
              { n: 3, label: "Tailoring resume..." },
            ].map(({ n, label }) => (
              <div key={n} className="flex items-center gap-2 text-[11px]">
                <span
                  className={
                    tailorPhase > n
                      ? "text-[#4ade80]"
                      : tailorPhase === n
                      ? "text-[#a78bfa]"
                      : "text-[#333]"
                  }
                >
                  {tailorPhase > n ? "✓" : tailorPhase === n ? "◌" : "○"}
                </span>
                <span
                  className={
                    tailorPhase > n
                      ? "text-[#555]"
                      : tailorPhase === n
                      ? "text-[#a78bfa]"
                      : "text-[#333]"
                  }
                >
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
```

- [ ] **Step 3: Build to check for TypeScript errors**

```
cd C:\dev\joblin\frontend
npm run build
```

Expected: Build succeeds with no TypeScript errors. If there are errors about `isTailoring` still being referenced somewhere, remove those references.

- [ ] **Step 4: Commit**

```
git add frontend/src/api/resume.ts frontend/src/pages/Resume.tsx
git commit -m "feat: add 3-step SSE progress indicator to resume tailor flow"
```

---

## Verification

After all tasks are complete, run the full test suite:

```
cd C:\dev\joblin
pytest -v
```

Expected: All tests pass with no failures or errors.
