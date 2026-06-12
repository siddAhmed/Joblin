# Resume Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full LaTeX resume editor to Joblin with one-click tailoring to any matched job via LLM.

**Architecture:** A `resume` router on the backend stores a single reference `.tex` file, compiles it via Tectonic (lightweight Rust LaTeX engine installed in Docker), and tailors it via the existing LLM adapter chain. The frontend adds a two-panel Monaco + PDF preview page accessible from any match card.

**Tech Stack:** FastAPI + SQLAlchemy (backend), Tectonic (LaTeX compilation), `@monaco-editor/react` (editor), React + react-router-dom (frontend)

---

## File Map

**Create:**
- `backend/models/resume.py` - Resume SQLAlchemy model
- `backend/alembic/versions/a1b2c3d4e5f6_add_resume_table.py` - migration
- `backend/routers/resume.py` - GET, PUT, POST /compile, POST /tailor endpoints
- `tests/test_resume.py` - backend tests
- `frontend/src/api/resume.ts` - API client
- `frontend/src/pages/Resume.tsx` - two-panel editor page

**Modify:**
- `backend/llm/prompts.py` - add `build_tailor_prompt`
- `backend/llm/protocol.py` - add `tailor_resume` to `LLMProvider`
- `backend/llm/groq_adapter.py` - implement `tailor_resume`
- `backend/llm/cerebras_adapter.py` - implement `tailor_resume`
- `backend/llm/gemini_adapter.py` - implement `tailor_resume`
- `backend/llm/factory.py` - add `get_tailor_provider`
- `backend/main.py` - register resume router
- `frontend/src/App.tsx` - add `/resume` route
- `frontend/src/components/Sidebar.tsx` - add Resume nav item
- `frontend/src/pages/Matches.tsx` - add "Tailor Resume" button per match
- `Dockerfile` - install Tectonic binary
- `docker-compose.yml` - add `tectonic_cache` volume

---

## Task 1: Resume model and migration

**Files:**
- Create: `backend/models/resume.py`
- Create: `backend/alembic/versions/a1b2c3d4e5f6_add_resume_table.py`

- [ ] **Step 1: Create the Resume model**

```python
# backend/models/resume.py
from datetime import datetime
from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class Resume(Base):
    __tablename__ = "resume"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tex_content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

- [ ] **Step 2: Create the Alembic migration**

The current head is `c8f2a1b3d4e5` (add_job_skills). Create this file exactly:

```python
# backend/alembic/versions/a1b2c3d4e5f6_add_resume_table.py
"""add resume table

Revision ID: a1b2c3d4e5f6
Revises: c8f2a1b3d4e5
Create Date: 2026-06-12

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c8f2a1b3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tex_content", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("resume")
```

- [ ] **Step 3: Apply the migration**

Run: `alembic upgrade head`

Expected: `Running upgrade c8f2a1b3d4e5 -> a1b2c3d4e5f6, add resume table`

- [ ] **Step 4: Commit**

```bash
git add backend/models/resume.py backend/alembic/versions/a1b2c3d4e5f6_add_resume_table.py
git commit -m "feat: add resume model and migration"
```

---

## Task 2: GET and PUT resume endpoints

**Files:**
- Create: `backend/routers/resume.py`
- Modify: `backend/main.py`
- Create: `tests/test_resume.py`

- [ ] **Step 1: Create the router with GET and PUT**

```python
# backend/routers/resume.py
import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.models.resume import Resume

router = APIRouter(prefix="/resume", tags=["resume"])
Session = Annotated[AsyncSession, Depends(get_session)]


class ResumeSave(BaseModel):
    tex_content: str


@router.get("")
async def get_resume(session: Session):
    result = await session.execute(select(Resume).where(Resume.id == 1))
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume found")
    return {"tex_content": resume.tex_content, "updated_at": resume.updated_at.isoformat()}


@router.put("")
async def save_resume(body: ResumeSave, session: Session):
    result = await session.execute(select(Resume).where(Resume.id == 1))
    resume = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if resume is None:
        resume = Resume(id=1, tex_content=body.tex_content, updated_at=now)
        session.add(resume)
    else:
        resume.tex_content = body.tex_content
        resume.updated_at = now
    await session.commit()
    return {"tex_content": resume.tex_content, "updated_at": resume.updated_at.isoformat()}
```

- [ ] **Step 2: Register the router in main.py**

In `backend/main.py`, add the import at the top with the other router imports:

```python
from backend.routers.resume import router as resume_router
```

Then inside `create_app()`, add after the insights router line:

```python
app.include_router(resume_router, prefix="/api")
```

- [ ] **Step 3: Write the failing tests**

```python
# tests/test_resume.py
import pytest


async def test_get_resume_returns_404_when_none(client):
    response = await client.get("/api/resume")
    assert response.status_code == 404


async def test_save_resume_then_get(client):
    tex = r"\documentclass{article}\begin{document}Hello\end{document}"
    put = await client.put("/api/resume", json={"tex_content": tex})
    assert put.status_code == 200
    assert put.json()["tex_content"] == tex
    assert "updated_at" in put.json()

    get = await client.get("/api/resume")
    assert get.status_code == 200
    assert get.json()["tex_content"] == tex


async def test_save_resume_twice_overwrites(client):
    tex1 = r"\documentclass{article}\begin{document}v1\end{document}"
    tex2 = r"\documentclass{article}\begin{document}v2\end{document}"
    await client.put("/api/resume", json={"tex_content": tex1})
    await client.put("/api/resume", json={"tex_content": tex2})
    get = await client.get("/api/resume")
    assert get.json()["tex_content"] == tex2
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/test_resume.py -v`

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/routers/resume.py backend/main.py tests/test_resume.py
git commit -m "feat: resume GET and PUT endpoints"
```

---

## Task 3: Compile endpoint

**Files:**
- Modify: `backend/routers/resume.py`
- Modify: `tests/test_resume.py`

- [ ] **Step 1: Write failing tests for compile**

Add to `tests/test_resume.py`:

```python
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


async def test_compile_resume_success(client):
    fake_pdf = b"%PDF-1.4 fake content"

    async def fake_exec(*args, **kwargs):
        tex_path = Path(args[1])
        tex_path.with_suffix(".pdf").write_bytes(fake_pdf)
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"", b""))
        return proc

    with patch("backend.routers.resume.asyncio.create_subprocess_exec", side_effect=fake_exec):
        response = await client.post(
            "/api/resume/compile",
            json={"tex_content": r"\documentclass{article}\begin{document}Hi\end{document}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == fake_pdf


async def test_compile_resume_failure(client):
    async def fail_exec(*args, **kwargs):
        proc = MagicMock()
        proc.returncode = 1
        proc.communicate = AsyncMock(return_value=(b"", b"LaTeX Error: undefined control sequence"))
        return proc

    with patch("backend.routers.resume.asyncio.create_subprocess_exec", side_effect=fail_exec):
        response = await client.post("/api/resume/compile", json={"tex_content": r"\badcommand"})

    assert response.status_code == 422
    assert "undefined control sequence" in response.json()["detail"]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_resume.py::test_compile_resume_success tests/test_resume.py::test_compile_resume_failure -v`

Expected: 2 tests FAILED with "route not found" or similar

- [ ] **Step 3: Add the compile endpoint to the router**

In `backend/routers/resume.py`, add at the bottom (the imports at the top of the file already include `asyncio`, `tempfile`, `Path`, `Response` - these were included in Task 2's router file):

```python
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
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=stderr.decode("utf-8", errors="replace"),
            )
        pdf_bytes = (Path(tmpdir) / "resume.pdf").read_bytes()
    return Response(content=pdf_bytes, media_type="application/pdf")
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/test_resume.py::test_compile_resume_success tests/test_resume.py::test_compile_resume_failure -v`

Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/routers/resume.py tests/test_resume.py
git commit -m "feat: resume compile endpoint with Tectonic subprocess"
```

---

## Task 4: LLM tailor_resume - prompt, protocol, adapters, factory

**Files:**
- Modify: `backend/llm/prompts.py`
- Modify: `backend/llm/protocol.py`
- Modify: `backend/llm/groq_adapter.py`
- Modify: `backend/llm/cerebras_adapter.py`
- Modify: `backend/llm/gemini_adapter.py`
- Modify: `backend/llm/factory.py`

- [ ] **Step 1: Add build_tailor_prompt to prompts.py**

Append to `backend/llm/prompts.py`:

```python
def build_tailor_prompt(tex_content: str, job_description: str) -> tuple[str, str]:
    system = (
        "You are a resume tailoring expert. Given a LaTeX resume and a job description, "
        "return ONLY the modified LaTeX source code. No explanation, no markdown code fences, "
        "no commentary of any kind - just the raw .tex content."
    )
    user = (
        f"Here is my LaTeX resume:\n\n{tex_content}\n\n"
        f"Here is the job description:\n\n{job_description[:3000]}\n\n"
        "Please modify the resume to emphasize skills and experience most relevant to this role. "
        "Adjust bullet points to highlight matching technologies, and reorder content if beneficial. "
        "Preserve the original LaTeX template structure and commands exactly."
    )
    return system, user
```

- [ ] **Step 2: Add tailor_resume to the LLMProvider protocol**

In `backend/llm/protocol.py`, add after the `extract_skills` method:

```python
    async def tailor_resume(self, tex_content: str, job_description: str) -> str: ...
```

The updated protocol class body should look like:

```python
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

    async def tailor_resume(self, tex_content: str, job_description: str) -> str: ...
```

- [ ] **Step 3: Implement tailor_resume in GroqAdapter**

In `backend/llm/groq_adapter.py`:

First, update the import line to add `build_tailor_prompt`:

```python
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt, build_skills_prompt, build_tailor_prompt
```

Then append the method to the `GroqAdapter` class (after `extract_skills`):

```python
    async def tailor_resume(self, tex_content: str, job_description: str) -> str:
        system, user = build_tailor_prompt(tex_content, job_description)
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

- [ ] **Step 4: Implement tailor_resume in CerebrasAdapter**

In `backend/llm/cerebras_adapter.py`:

Update the import line to add `build_tailor_prompt`:

```python
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt, build_skills_prompt, build_tailor_prompt
```

Append to the `CerebrasAdapter` class:

```python
    async def tailor_resume(self, tex_content: str, job_description: str) -> str:
        system, user = build_tailor_prompt(tex_content, job_description)
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

- [ ] **Step 5: Implement tailor_resume in GeminiAdapter**

In `backend/llm/gemini_adapter.py`:

Update the import line to add `build_tailor_prompt`:

```python
from backend.llm.prompts import build_filter_prompt, build_summarize_prompt, build_skills_prompt, build_tailor_prompt
```

Append to the `GeminiAdapter` class:

```python
    async def tailor_resume(self, tex_content: str, job_description: str) -> str:
        system, user = build_tailor_prompt(tex_content, job_description)
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

- [ ] **Step 6: Add get_tailor_provider to factory.py**

In `backend/llm/factory.py`, append after `get_summarize_provider`:

```python
def get_tailor_provider(settings: dict) -> LLMProvider:
    return get_summarize_provider(settings)
```

- [ ] **Step 7: Commit**

```bash
git add backend/llm/prompts.py backend/llm/protocol.py backend/llm/groq_adapter.py backend/llm/cerebras_adapter.py backend/llm/gemini_adapter.py backend/llm/factory.py
git commit -m "feat: add tailor_resume to LLM adapters"
```

---

## Task 5: Tailor endpoint and tests

**Files:**
- Modify: `backend/routers/resume.py`
- Modify: `tests/test_resume.py`

- [ ] **Step 1: Write failing tests for tailor**

Add to `tests/test_resume.py` (new imports needed at top of file - add after existing imports):

```python
from backend.database import get_session
from backend.models.company import Company, AtsType
from backend.models.job import Job
```

Then add the fixtures and tests:

```python
@pytest.fixture
async def seeded_job_id(app):
    override = app.dependency_overrides[get_session]
    async for session in override():
        company = Company(
            name="Stripe",
            careers_url="https://stripe.com/jobs",
            ats_type=AtsType.greenhouse,
        )
        session.add(company)
        await session.flush()
        job = Job(
            company_id=company.id,
            job_id="swe-123",
            title="Software Engineer",
            url="https://stripe.com/jobs/swe-123",
            raw_description="Python, distributed systems, REST APIs, PostgreSQL",
            normalized_title="software engineer",
        )
        session.add(job)
        await session.commit()
        return job.id


async def test_tailor_resume_404_no_resume(client):
    response = await client.post("/api/resume/tailor", json={"job_id": 999})
    assert response.status_code == 404
    assert "reference resume" in response.json()["detail"].lower()


async def test_tailor_resume_404_no_job(client):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    await client.put("/api/resume", json={"tex_content": tex})
    response = await client.post("/api/resume/tailor", json={"job_id": 999})
    assert response.status_code == 404
    assert "job" in response.json()["detail"].lower()


async def test_tailor_resume_success(client, seeded_job_id):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    tailored = r"\documentclass{article}\begin{document}Tailored resume\end{document}"
    await client.put("/api/resume", json={"tex_content": tex})

    mock_provider = MagicMock()
    mock_provider.tailor_resume = AsyncMock(return_value=tailored)

    with patch("backend.routers.resume.get_tailor_provider", return_value=mock_provider), \
         patch("backend.routers.resume.get_all_settings", return_value={}):
        response = await client.post("/api/resume/tailor", json={"job_id": seeded_job_id})

    assert response.status_code == 200
    assert response.json()["tex_content"] == tailored
    mock_provider.tailor_resume.assert_called_once_with(
        tex_content=tex,
        job_description="Python, distributed systems, REST APIs, PostgreSQL",
    )
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_resume.py::test_tailor_resume_404_no_resume tests/test_resume.py::test_tailor_resume_404_no_job tests/test_resume.py::test_tailor_resume_success -v`

Expected: 3 tests FAILED with "route not found"

- [ ] **Step 3: Add the tailor endpoint to the router**

In `backend/routers/resume.py`, add near the top (after existing imports, before the router definition):

```python
from backend.config import get_all_settings
from backend.llm.factory import get_tailor_provider
from backend.models.job import Job
```

Then append to the router file:

```python
class TailorRequest(BaseModel):
    job_id: int


@router.post("/tailor")
async def tailor_resume_endpoint(body: TailorRequest, session: Session):
    resume_result = await session.execute(select(Resume).where(Resume.id == 1))
    resume = resume_result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=404, detail="No reference resume found. Upload a .tex file first.")

    job = await session.get(Job, body.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    settings = await get_all_settings(session)
    provider = get_tailor_provider(settings)
    tailored_tex = await provider.tailor_resume(
        tex_content=resume.tex_content,
        job_description=job.raw_description or job.title,
    )
    return {"tex_content": tailored_tex}
```

Note: `get_all_settings` and `get_tailor_provider` were already imported at the top of the router in Task 2 and the import added in Step 3 above. Remove any duplicate imports if they clash.

The final imports section of `backend/routers/resume.py` should be:

```python
import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.llm.factory import get_tailor_provider
from backend.models.job import Job
from backend.models.resume import Resume
```

- [ ] **Step 4: Run all resume tests**

Run: `pytest tests/test_resume.py -v`

Expected: All 8 tests PASSED

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest tests/ -v`

Expected: All existing tests still PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/routers/resume.py tests/test_resume.py
git commit -m "feat: resume tailor endpoint"
```

---

## Task 6: Docker and docker-compose

**Files:**
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add Tectonic to the Dockerfile**

In `Dockerfile`, find the existing `apt-get install` block in Stage 2 (the Python image stage):

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*
```

Replace it with (adds `libfontconfig1` and `libssl-dev` needed by Tectonic):

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    libfontconfig1 \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*
```

Then add a new `RUN` step after the `apt-get` block to download Tectonic. Insert this after the `apt-get` block and before the `COPY backend/requirements.txt` line:

```dockerfile
# Install Tectonic (lightweight LaTeX engine)
RUN curl -L "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-musl.tar.gz" \
    | tar xz -C /usr/local/bin \
    && tectonic --version
```

- [ ] **Step 2: Add tectonic_cache volume to docker-compose.yml**

In `docker-compose.yml`, add the volume mount to the `app` service. Change:

```yaml
services:
  app:
    build: .
    restart: unless-stopped
    volumes:
      - db_data:/app/data
```

To:

```yaml
services:
  app:
    build: .
    restart: unless-stopped
    volumes:
      - db_data:/app/data
      - tectonic_cache:/root/.cache/Tectonic
```

At the bottom of `docker-compose.yml`, in the `volumes:` block, add `tectonic_cache:`:

```yaml
volumes:
  db_data:
  caddy_data:
  caddy_config:
  tectonic_cache:
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: install Tectonic in Docker for LaTeX compilation"
```

---

## Task 7: Frontend API client and Monaco install

**Files:**
- Create: `frontend/src/api/resume.ts`

- [ ] **Step 1: Install @monaco-editor/react**

Run from the `frontend/` directory:

```bash
cd frontend && npm install @monaco-editor/react
```

Expected: Package added to `package.json` and `package-lock.json`

- [ ] **Step 2: Create the API client**

```typescript
// frontend/src/api/resume.ts
import { api } from "./client";

export interface ResumeData {
  tex_content: string;
  updated_at: string;
}

export interface TailorResult {
  tex_content: string;
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
  tailor: (job_id: number) =>
    api.post<TailorResult>("/resume/tailor", { job_id }).then((r) => r.data),
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/resume.ts frontend/package.json frontend/package-lock.json
git commit -m "feat: resume API client and install monaco-editor"
```

---

## Task 8: Frontend Resume page

**Files:**
- Create: `frontend/src/pages/Resume.tsx`

- [ ] **Step 1: Create the Resume page**

```typescript
// frontend/src/pages/Resume.tsx
import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Editor from "@monaco-editor/react";
import { resumeApi } from "@/api/resume";
import { matchesApi } from "@/api/matches";

interface TailoredFor {
  jobId: number;
  title: string;
  company: string;
}

export function Resume() {
  const [searchParams] = useSearchParams();
  const [editorContent, setEditorContent] = useState("");
  const [referenceContent, setReferenceContent] = useState<string | null>(null);
  const [referenceUpdatedAt, setReferenceUpdatedAt] = useState<string | null>(null);
  const [tailoredFor, setTailoredFor] = useState<TailoredFor | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<number | "">("");
  const [isCompiling, setIsCompiling] = useState(false);
  const [isTailoring, setIsTailoring] = useState(false);
  const [compileError, setCompileError] = useState<string | null>(null);

  const { data: matches = [] } = useQuery({
    queryKey: ["matches", ""],
    queryFn: () => matchesApi.list({}),
  });

  useEffect(() => {
    resumeApi
      .get()
      .then((data) => {
        setEditorContent(data.tex_content);
        setReferenceContent(data.tex_content);
        setReferenceUpdatedAt(data.updated_at);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const jobIdParam = searchParams.get("jobId");
    if (jobIdParam && matches.length > 0) {
      setSelectedJobId(Number(jobIdParam));
    }
  }, [searchParams, matches]);

  async function handleSave() {
    const data = await resumeApi.save(editorContent);
    setReferenceContent(data.tex_content);
    setReferenceUpdatedAt(data.updated_at);
    setTailoredFor(null);
  }

  async function handleCompile() {
    setIsCompiling(true);
    setCompileError(null);
    try {
      const pdfBuffer = await resumeApi.compile(editorContent);
      const blob = new Blob([pdfBuffer], { type: "application/pdf" });
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
      setPdfUrl(URL.createObjectURL(blob));
    } catch (err: any) {
      setCompileError(err?.response?.data?.detail || "Compilation failed");
    } finally {
      setIsCompiling(false);
    }
  }

  async function handleTailor() {
    if (!selectedJobId) return;
    setIsTailoring(true);
    try {
      const result = await resumeApi.tailor(Number(selectedJobId));
      setEditorContent(result.tex_content);
      const match = matches.find((m) => m.job_id === Number(selectedJobId));
      setTailoredFor({
        jobId: Number(selectedJobId),
        title: match?.job_title ?? "Unknown",
        company: match?.company_name ?? "Unknown",
      });
    } finally {
      setIsTailoring(false);
    }
  }

  function handleViewReference() {
    if (referenceContent !== null) {
      setEditorContent(referenceContent);
      setTailoredFor(null);
    }
  }

  function handleDownload() {
    if (!pdfUrl) return;
    const a = document.createElement("a");
    a.href = pdfUrl;
    a.download = "resume.pdf";
    a.click();
  }

  function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setEditorContent(ev.target?.result as string);
      setTailoredFor(null);
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  const isDirty = referenceContent !== null && editorContent !== referenceContent;
  const hasReference = referenceContent !== null;

  function renderStatusBar() {
    if (!hasReference && !editorContent) {
      return (
        <span className="text-[#555]">
          No resume yet - upload a .tex file to get started
        </span>
      );
    }
    if (tailoredFor) {
      return (
        <div className="flex items-center gap-2">
          <span className="text-[#a78bfa]">
            ✦ Tailored for {tailoredFor.title} @ {tailoredFor.company}
          </span>
          <button
            onClick={handleSave}
            className="text-[10px] border border-[#2a5c2a] rounded px-1.5 py-0.5 text-[#4ade80] hover:bg-[#1a3a1a]"
          >
            Save as Reference
          </button>
          <button
            onClick={handleViewReference}
            className="text-[10px] border border-[#2a2a2a] rounded px-1.5 py-0.5 text-[#888] hover:text-[#ccc]"
          >
            ↩ View Reference
          </button>
        </div>
      );
    }
    if (isDirty) {
      return (
        <div className="flex items-center gap-2">
          <span className="text-[#f59e0b]">Unsaved changes</span>
          <button
            onClick={handleSave}
            className="text-[10px] border border-[#2a5c2a] rounded px-1.5 py-0.5 text-[#4ade80] hover:bg-[#1a3a1a]"
          >
            Save as Reference
          </button>
          <button
            onClick={handleViewReference}
            disabled={!hasReference}
            className="text-[10px] border border-[#2a2a2a] rounded px-1.5 py-0.5 text-[#888] hover:text-[#ccc] disabled:opacity-40"
          >
            ↩ Reset
          </button>
        </div>
      );
    }
    return (
      <span className="text-[#555]">
        Reference saved
        {referenceUpdatedAt
          ? ` · ${new Date(referenceUpdatedAt).toLocaleString()}`
          : ""}
      </span>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[#1e1e1e] bg-[#0d0d0d] flex-wrap shrink-0">
        <span className="text-[11px] text-[#555]">Job:</span>
        <select
          value={selectedJobId}
          onChange={(e) =>
            setSelectedJobId(e.target.value ? Number(e.target.value) : "")
          }
          className="bg-[#111] border border-[#2a2a2a] rounded px-2 py-1 text-xs text-[#ccc] max-w-[220px]"
        >
          <option value="">Select a match...</option>
          {matches.map((m) => (
            <option key={m.id} value={m.job_id}>
              {m.job_title} @ {m.company_name}
            </option>
          ))}
        </select>
        <button
          onClick={handleTailor}
          disabled={!selectedJobId || !hasReference || isTailoring}
          className="text-xs border border-[#4e4e9f] rounded px-3 py-1 text-[#a78bfa] hover:bg-[#1a1a3a] disabled:opacity-40"
        >
          {isTailoring ? "Tailoring..." : "✦ Tailor"}
        </button>
        <button
          onClick={handleCompile}
          disabled={isCompiling || !editorContent}
          className="text-xs border border-[#2a2a2a] rounded px-3 py-1 text-[#ccc] hover:bg-[#1a1a1a] disabled:opacity-40"
        >
          {isCompiling ? "Compiling..." : "▶ Compile"}
        </button>
        <button
          onClick={handleDownload}
          disabled={!pdfUrl}
          className="text-xs border border-[#2a2a2a] rounded px-3 py-1 text-[#888] hover:text-[#ccc] disabled:opacity-40"
        >
          ↓ PDF
        </button>
        <label className="ml-auto cursor-pointer text-xs border border-[#2a2a2a] rounded px-3 py-1 text-[#888] hover:text-[#ccc]">
          Upload .tex
          <input
            type="file"
            accept=".tex"
            className="hidden"
            onChange={handleUpload}
          />
        </label>
      </div>

      {/* Status bar */}
      <div className="px-4 py-1.5 border-b border-[#1e1e1e] bg-[#0a0a0a] text-[11px] shrink-0">
        {renderStatusBar()}
      </div>

      {/* Compile error */}
      {compileError && (
        <div className="px-4 py-2 bg-red-950/30 border-b border-red-900/40 text-[11px] text-red-400 flex items-start justify-between shrink-0">
          <pre className="whitespace-pre-wrap font-mono text-[10px] max-h-24 overflow-auto flex-1">
            {compileError}
          </pre>
          <button
            onClick={() => setCompileError(null)}
            className="ml-2 text-red-600 hover:text-red-400 shrink-0"
          >
            ✕
          </button>
        </div>
      )}

      {/* Two-panel editor + preview */}
      <div className="flex flex-1 min-h-0">
        <div className="flex-1 min-w-0 border-r border-[#1e1e1e]">
          <Editor
            height="100%"
            language="plaintext"
            theme="vs-dark"
            value={editorContent}
            onChange={(v) => setEditorContent(v ?? "")}
            options={{
              fontSize: 13,
              minimap: { enabled: false },
              wordWrap: "on",
              scrollBeyondLastLine: false,
              lineNumbers: "on",
            }}
          />
        </div>
        <div className="flex-1 min-w-0 bg-[#0a0a0a] flex items-center justify-center">
          {pdfUrl ? (
            <iframe
              src={pdfUrl}
              className="w-full h-full border-0"
              title="Resume PDF preview"
            />
          ) : (
            <div className="text-center text-[#444]">
              <p className="text-sm">No preview yet</p>
              <p className="text-[11px] mt-1">
                Click ▶ Compile to generate PDF
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Resume.tsx
git commit -m "feat: Resume editor page with two-panel layout"
```

---

## Task 9: Frontend routing, sidebar, and Matches button

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/pages/Matches.tsx`

- [ ] **Step 1: Add the /resume route to App.tsx**

In `frontend/src/App.tsx`, add the import at the top with the other page imports:

```typescript
import { Resume } from "./pages/Resume";
```

Inside `AppInner`, add the route inside the `<Route element={<Layout />}>` block, after the Insights route:

```tsx
<Route path="/resume" element={<Resume />} />
```

- [ ] **Step 2: Add Resume to the Sidebar NAV array**

In `frontend/src/components/Sidebar.tsx`, find the `NAV` array and add the Resume entry between Insights and Settings:

```typescript
const NAV = [
  { label: "Dashboard", icon: "◼", path: "/" },
  { label: "Matches", icon: "★", path: "/matches" },
  { label: "All Jobs", icon: "≡", path: "/jobs" },
  { label: "Companies", icon: "⊞", path: "/companies", warn: true },
  { label: "Runs", icon: "▶", path: "/runs" },
  { label: "Usage", icon: "◈", path: "/usage" },
  { label: "Insights", icon: "◎", path: "/insights" },
  { label: "Resume", icon: "⊡", path: "/resume" },
  { label: "Settings", icon: "⚙", path: "/settings" },
] as const;
```

- [ ] **Step 3: Add "Tailor Resume" button to each match card**

In `frontend/src/pages/Matches.tsx`, the `MatchRow` component already imports `useNavigate` (check: it's imported in the parent `Matches` component). Add `useNavigate` import to the file-level imports - it is already there.

In the `MatchRow` component, add `useNavigate`:

Change the `MatchRow` function signature to include navigate. At the top of `MatchRow`:

```typescript
function MatchRow({ match, selected, onSelect }: { match: Match; selected: boolean; onSelect: () => void }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  // ... rest unchanged
```

Then in the expanded section, inside the `<div className="flex gap-2 mt-3">` block, add the Tailor button after the Apply link:

```tsx
<div className="flex gap-2 mt-3">
  <button onClick={() => dismiss.mutate()} className="text-[11px] border border-[#2a2a2a] rounded px-2 py-1 text-[#888] hover:text-[#ccc]">Not interested</button>
  {applyUrl && <a href={applyUrl} target="_blank" rel="noreferrer" className="text-[11px] border border-[#4e9eff] rounded px-2 py-1 text-[#4e9eff] hover:bg-[#0e2040]">Apply</a>}
  <button
    onClick={() => navigate(`/resume?jobId=${match.job_id}`)}
    className="text-[11px] border border-[#4e4e9f] rounded px-2 py-1 text-[#a78bfa] hover:bg-[#1a1a3a]"
  >
    ✦ Tailor Resume
  </button>
</div>
```

- [ ] **Step 4: Build the frontend to confirm no TypeScript errors**

Run from the `frontend/` directory:

```bash
cd frontend && npm run build
```

Expected: Build completes with no errors. Output in `frontend/dist/`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/Sidebar.tsx frontend/src/pages/Matches.tsx
git commit -m "feat: wire up Resume page to routing, sidebar, and Matches"
```

---

## Self-Review Checklist

- [x] Spec coverage: GET/PUT resume, compile, tailor, status bar states, "Tailor Resume" on Matches, sidebar nav, Docker/Tectonic - all present
- [x] No placeholders or TBDs
- [x] Types consistent: `ResumeData`, `TailorResult`, `TailoredFor`, `ResumeSave`, `CompileRequest`, `TailorRequest` all defined before use
- [x] `build_tailor_prompt` defined in Task 4 Step 1, used in Steps 3-5
- [x] `get_tailor_provider` defined in Task 4 Step 6, imported in Task 5 Step 3
- [x] `seeded_job_id` fixture uses correct model fields from `Company` and `Job` models
