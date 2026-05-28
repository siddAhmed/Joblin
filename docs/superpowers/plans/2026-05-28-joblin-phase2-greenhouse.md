# Joblin Phase 2 -- Greenhouse Scraper End-to-End

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a company via the API, auto-detect Greenhouse ATS, scrape real jobs, apply heuristic pre-filter, persist new jobs to DB, and return run results. No LLM calls yet.

**Prerequisite:** Phase 1 complete and all tests passing.

**Tech Stack:** httpx (async HTTP), FastAPI routers, SQLAlchemy async, pytest-asyncio.

---

## File Map

| File | Responsibility |
|---|---|
| `backend/scrapers/base.py` | `ScrapedJob` dataclass |
| `backend/scrapers/job_id.py` | Job ID cascade (ATS ID > URL hash > composite hash) |
| `backend/scrapers/heuristics.py` | Heuristic pre-filter against criteria settings |
| `backend/scrapers/probe.py` | ATS probe: try each ATS pattern, return detected type + identifier |
| `backend/scrapers/greenhouse.py` | Greenhouse adapter: fetch + parse jobs JSON |
| `backend/pipeline.py` | Run orchestrator: create Run row, iterate companies, dedup, filter, persist |
| `backend/routers/companies.py` | GET/POST/PATCH/DELETE companies, POST probe, POST import |
| `backend/routers/runs.py` | POST /api/runs, GET /api/runs, GET /api/runs/{id} |
| `tests/test_scrapers.py` | Unit tests for probe, job_id, heuristics, greenhouse adapter |
| `tests/test_companies.py` | API tests for companies router |
| `tests/test_runs.py` | API test for POST /api/runs (no real network, uses mock adapter) |

---

## Task 8: ScrapedJob dataclass + ATS probe

**Files:**
- Create: `backend/scrapers/base.py`
- Create: `backend/scrapers/probe.py`

- [ ] **Step 1: Write failing test for probe**

```python
# tests/test_scrapers.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.scrapers.probe import probe_ats, ProbeResult


async def test_probe_detects_greenhouse():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"jobs": []}

    with patch("backend.scrapers.probe.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        result = await probe_ats("https://stripe.com/jobs", "stripe")

    assert result.ats_type == "greenhouse"
    assert result.identifier == "stripe"


async def test_probe_returns_crawl4ai_when_all_fail():
    mock_response = AsyncMock()
    mock_response.status_code = 404

    with patch("backend.scrapers.probe.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        result = await probe_ats("https://example.com/careers", "example")

    assert result.ats_type == "crawl4ai"
    assert len(result.probe_attempts) == 6
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
cd C:\dev\joblin
.venv/Scripts/pytest tests/test_scrapers.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` -- file does not exist yet.

- [ ] **Step 3: Write `backend/scrapers/base.py`**

```python
from dataclasses import dataclass, field


@dataclass
class ScrapedJob:
    ats_id: str | None
    title: str
    location: str | None
    url: str
    raw_description: str = ""
```

- [ ] **Step 4: Write `backend/scrapers/probe.py`**

```python
from dataclasses import dataclass, field
import httpx


@dataclass
class ProbeAttempt:
    url: str
    status_code: int | None
    error: str | None = None


@dataclass
class ProbeResult:
    ats_type: str
    identifier: str | None
    probe_attempts: list[ProbeAttempt] = field(default_factory=list)


def _slug_from_url(url: str) -> str:
    from urllib.parse import urlparse
    parts = urlparse(url).path.strip("/").split("/")
    return parts[-1] if parts else url.split("//")[-1].split(".")[0]


async def probe_ats(careers_url: str, name_hint: str) -> ProbeResult:
    slug = _slug_from_url(careers_url) or name_hint.lower().replace(" ", "-")
    attempts: list[ProbeAttempt] = []

    candidates = [
        ("greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"),
        ("lever", f"https://api.lever.co/v0/postings/{slug}"),
        ("ashby", f"https://api.ashbyhq.com/posting-api/job-board/{slug}"),
        ("workable", f"https://{slug}.workable.com/spi/v3/jobs"),
        ("smartrecruiters", f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"),
        ("workday", careers_url),
    ]

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for ats_type, url in candidates:
            try:
                resp = await client.get(url)
                attempts.append(ProbeAttempt(url=url, status_code=resp.status_code))
                if resp.status_code == 200:
                    if ats_type == "workday":
                        if "workday.com" in careers_url or "myworkdayjobs.com" in careers_url:
                            return ProbeResult(ats_type="workday", identifier=careers_url, probe_attempts=attempts)
                    else:
                        return ProbeResult(ats_type=ats_type, identifier=slug, probe_attempts=attempts)
            except Exception as exc:
                attempts.append(ProbeAttempt(url=url, status_code=None, error=str(exc)))

    return ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=attempts)
```

- [ ] **Step 5: Run tests**

```powershell
.venv/Scripts/pytest tests/test_scrapers.py::test_probe_detects_greenhouse tests/test_scrapers.py::test_probe_returns_crawl4ai_when_all_fail -v
```

Expected: both PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/scrapers/base.py backend/scrapers/probe.py tests/test_scrapers.py
git commit -m "feat: ScrapedJob dataclass and ATS probe logic"
```

---

## Task 9: Job ID cascade + heuristic pre-filter

**Files:**
- Create: `backend/scrapers/job_id.py`
- Create: `backend/scrapers/heuristics.py`

- [ ] **Step 1: Add tests**

Append to `tests/test_scrapers.py`:

```python
from backend.scrapers.job_id import compute_job_id
from backend.scrapers.base import ScrapedJob
from backend.scrapers.heuristics import passes_heuristic


def test_compute_job_id_uses_ats_id_first():
    job = ScrapedJob(ats_id="abc123", title="Backend Engineer", location="Remote", url="https://example.com/jobs/abc123")
    result = compute_job_id(job, company_id=1)
    assert result == "abc123"


def test_compute_job_id_falls_back_to_url_hash():
    job = ScrapedJob(ats_id=None, title="Backend Engineer", location="Remote", url="https://example.com/jobs/123?ref=x")
    result = compute_job_id(job, company_id=1)
    assert len(result) == 64  # SHA-256 hex


def test_heuristic_passes_matching_title():
    criteria = {
        "title_allowlist": "backend|platform",
        "title_denylist": "intern",
        "location_allowlist": "",
        "location_denylist": "",
        "seniority_allowlist": ["senior", "staff"],
        "exclusion_keywords": [],
    }
    job = ScrapedJob(ats_id="1", title="Senior Backend Engineer", location="Remote", url="https://x.com")
    assert passes_heuristic(job, criteria) is True


def test_heuristic_blocks_denylist_title():
    criteria = {
        "title_allowlist": "backend",
        "title_denylist": "intern",
        "location_allowlist": "",
        "location_denylist": "",
        "seniority_allowlist": ["senior"],
        "exclusion_keywords": [],
    }
    job = ScrapedJob(ats_id="2", title="Backend Intern", location="Remote", url="https://x.com")
    assert passes_heuristic(job, criteria) is False
```

- [ ] **Step 2: Run to verify they fail**

```powershell
.venv/Scripts/pytest tests/test_scrapers.py -k "job_id or heuristic" -v
```

Expected: ImportError.

- [ ] **Step 3: Write `backend/scrapers/job_id.py`**

```python
import hashlib
import re
from urllib.parse import urlparse, urlencode, parse_qs

from backend.scrapers.base import ScrapedJob


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def compute_job_id(job: ScrapedJob, company_id: int) -> str:
    if job.ats_id:
        return job.ats_id

    if job.url:
        canonical = _canonical_url(job.url)
        return hashlib.sha256(canonical.encode()).hexdigest()

    composite = f"{company_id}:{_normalize(job.title)}:{_normalize(job.location or '')}"
    return hashlib.sha256(composite.encode()).hexdigest()
```

- [ ] **Step 4: Write `backend/scrapers/heuristics.py`**

```python
import re
from backend.scrapers.base import ScrapedJob

SENIORITY_PATTERNS = {
    "junior": r"\bjunior\b|\bjr\.?\b|\bentry.level\b",
    "mid": r"\bmid\b|\bintermediate\b",
    "senior": r"\bsenior\b|\bsr\.?\b",
    "staff": r"\bstaff\b",
    "principal": r"\bprincipal\b",
    "lead": r"\blead\b",
    "manager": r"\bmanager\b|\bem\b|\beng\.?\s?mgr\b",
}


def _infer_seniority(title: str) -> str | None:
    lower = title.lower()
    for level, pattern in SENIORITY_PATTERNS.items():
        if re.search(pattern, lower):
            return level
    return None


def passes_heuristic(job: ScrapedJob, criteria: dict) -> bool:
    title_lower = job.title.lower()

    # Title allowlist -- if set, title must match
    if criteria.get("title_allowlist"):
        if not re.search(criteria["title_allowlist"], title_lower):
            return False

    # Title denylist -- if set, title must NOT match
    if criteria.get("title_denylist"):
        if re.search(criteria["title_denylist"], title_lower):
            return False

    # Location filters
    loc = (job.location or "").lower()
    if criteria.get("location_allowlist") and loc:
        if not re.search(criteria["location_allowlist"], loc):
            return False
    if criteria.get("location_denylist") and loc:
        if re.search(criteria["location_denylist"], loc):
            return False

    # Seniority filter
    allowed_seniority: list = criteria.get("seniority_allowlist", [])
    if allowed_seniority:
        inferred = _infer_seniority(job.title)
        if inferred and inferred not in allowed_seniority:
            return False

    # Exclusion keywords in description
    desc_lower = (job.raw_description or "").lower()
    for kw in criteria.get("exclusion_keywords", []):
        if kw.lower() in desc_lower:
            return False

    return True
```

- [ ] **Step 5: Run tests**

```powershell
.venv/Scripts/pytest tests/test_scrapers.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/scrapers/job_id.py backend/scrapers/heuristics.py
git commit -m "feat: job ID cascade and heuristic pre-filter"
```

---

## Task 10: Greenhouse adapter

**Files:**
- Create: `backend/scrapers/greenhouse.py`

- [ ] **Step 1: Add test**

Append to `tests/test_scrapers.py`:

```python
from unittest.mock import AsyncMock, patch
from backend.scrapers.greenhouse import fetch_greenhouse_jobs


async def test_greenhouse_returns_scraped_jobs():
    mock_data = {
        "jobs": [
            {
                "id": 9001,
                "title": "Senior Backend Engineer",
                "location": {"name": "Remote"},
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/9001",
                "content": "<p>We are hiring a backend engineer.</p>",
            }
        ]
    }
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data

    with patch("backend.scrapers.greenhouse.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        jobs = await fetch_greenhouse_jobs("stripe")

    assert len(jobs) == 1
    assert jobs[0].ats_id == "9001"
    assert jobs[0].title == "Senior Backend Engineer"
    assert "backend engineer" in jobs[0].raw_description.lower()
```

- [ ] **Step 2: Run to verify it fails**

```powershell
.venv/Scripts/pytest tests/test_scrapers.py::test_greenhouse_returns_scraped_jobs -v
```

Expected: ImportError.

- [ ] **Step 3: Write `backend/scrapers/greenhouse.py`**

```python
import re
import httpx
from backend.scrapers.base import ScrapedJob


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


async def fetch_greenhouse_jobs(identifier: str) -> list[ScrapedJob]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{identifier}/jobs?content=true"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    jobs = []
    for raw in data.get("jobs", []):
        jobs.append(
            ScrapedJob(
                ats_id=str(raw["id"]),
                title=raw.get("title", ""),
                location=raw.get("location", {}).get("name"),
                url=raw.get("absolute_url", ""),
                raw_description=_strip_html(raw.get("content", "")),
            )
        )
    return jobs
```

- [ ] **Step 4: Run test**

```powershell
.venv/Scripts/pytest tests/test_scrapers.py::test_greenhouse_returns_scraped_jobs -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/scrapers/greenhouse.py
git commit -m "feat: Greenhouse ATS adapter"
```

---

## Task 11: Companies router

**Files:**
- Create: `backend/routers/companies.py`
- Create: `tests/test_companies.py`

- [ ] **Step 1: Write `backend/routers/companies.py`**

```python
import csv
import io
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models.company import Company, AtsType
from backend.scrapers.probe import probe_ats

router = APIRouter(prefix="/companies", tags=["companies"])
Session = Annotated[AsyncSession, Depends(get_session)]


class CompanyCreate(BaseModel):
    name: str
    careers_url: str


class CompanyUpdate(BaseModel):
    css_selector: str | None = None
    custom_api_url: str | None = None
    is_active: bool | None = None
    ats_type: AtsType | None = None
    ats_identifier: str | None = None


class ProbeRequest(BaseModel):
    name: str
    careers_url: str


@router.get("")
async def list_companies(session: Session):
    rows = (await session.execute(select(Company).order_by(Company.name))).scalars().all()
    return [
        {
            "id": c.id, "name": c.name, "careers_url": c.careers_url,
            "ats_type": c.ats_type, "is_active": c.is_active,
            "quarantine_count": c.quarantine_count, "quarantined_at": c.quarantined_at,
            "quarantine_reason": c.quarantine_reason,
        }
        for c in rows
    ]


@router.post("/probe")
async def probe_company(req: ProbeRequest):
    result = await probe_ats(req.careers_url, req.name)
    return {
        "ats_type": result.ats_type,
        "identifier": result.identifier,
        "probe_attempts": [
            {"url": a.url, "status_code": a.status_code, "error": a.error}
            for a in result.probe_attempts
        ],
    }


@router.post("", status_code=201)
async def add_company(req: CompanyCreate, session: Session):
    probe = await probe_ats(req.careers_url, req.name)
    company = Company(
        name=req.name,
        careers_url=req.careers_url,
        ats_type=AtsType(probe.ats_type),
        ats_identifier=probe.identifier,
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return {"id": company.id, "ats_type": company.ats_type, "probe_attempts": [
        {"url": a.url, "status_code": a.status_code} for a in probe.probe_attempts
    ]}


@router.patch("/{company_id}")
async def update_company(company_id: int, req: CompanyUpdate, session: Session):
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(company, field, value)
    await session.commit()
    return {"id": company.id}


@router.delete("/{company_id}", status_code=204)
async def delete_company(company_id: int, session: Session):
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    await session.delete(company)
    await session.commit()


@router.post("/{company_id}/retry")
async def retry_company(company_id: int, session: Session):
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.quarantine_count = 0
    company.quarantined_at = None
    company.quarantine_reason = None
    company.is_active = True
    await session.commit()
    return {"id": company.id, "status": "reactivated"}


@router.post("/import", status_code=201)
async def import_companies(file: UploadFile, session: Session):
    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    created = []
    for row in reader:
        name = row.get("name", "").strip()
        url = row.get("careers_url", "").strip()
        if not name or not url:
            continue
        probe = await probe_ats(url, name)
        company = Company(
            name=name, careers_url=url,
            ats_type=AtsType(probe.ats_type), ats_identifier=probe.identifier,
        )
        session.add(company)
        created.append(name)
    await session.commit()
    return {"created": len(created), "names": created}
```

- [ ] **Step 2: Register router in `backend/main.py`**

```python
from backend.routers import system, companies

def create_app() -> FastAPI:
    app = FastAPI(title="Joblin", lifespan=lifespan)
    app.include_router(system.router, prefix="/api")
    app.include_router(companies.router, prefix="/api")
    ...
    return app
```

- [ ] **Step 3: Write `tests/test_companies.py`**

```python
import pytest
from unittest.mock import AsyncMock, patch
from backend.scrapers.probe import ProbeResult, ProbeAttempt


async def test_list_companies_empty(client):
    response = await client.get("/api/companies")
    assert response.status_code == 200
    assert response.json() == []


async def test_add_company_detects_greenhouse(client):
    mock_probe = ProbeResult(
        ats_type="greenhouse",
        identifier="stripe",
        probe_attempts=[ProbeAttempt(url="https://boards-api.greenhouse.io/v1/boards/stripe/jobs", status_code=200)],
    )
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        response = await client.post("/api/companies", json={"name": "Stripe", "careers_url": "https://stripe.com/jobs"})

    assert response.status_code == 201
    assert response.json()["ats_type"] == "greenhouse"


async def test_delete_company(client):
    mock_probe = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        create_resp = await client.post("/api/companies", json={"name": "Acme", "careers_url": "https://acme.com/jobs"})
    company_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/companies/{company_id}")
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/companies")
    assert list_resp.json() == []
```

- [ ] **Step 4: Run tests**

```powershell
.venv/Scripts/pytest tests/test_companies.py -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/routers/companies.py tests/test_companies.py backend/main.py
git commit -m "feat: companies router (CRUD, probe, CSV import)"
```

---

## Task 12: Run pipeline + runs router

**Files:**
- Create: `backend/pipeline.py`
- Create: `backend/routers/runs.py`
- Create: `tests/test_runs.py`

- [ ] **Step 1: Write `backend/pipeline.py`**

```python
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_setting
from backend.models.company import Company
from backend.models.job import Job
from backend.models.run import Run, RunCompanyResult, RunStatus, CompanyResultStatus
from backend.models.setting import Setting
from backend.scrapers.base import ScrapedJob
from backend.scrapers.heuristics import passes_heuristic
from backend.scrapers.job_id import compute_job_id

import re

# In-memory SSE queues keyed by run_id
_run_queues: dict[int, asyncio.Queue] = {}


def get_run_queue(run_id: int) -> asyncio.Queue:
    if run_id not in _run_queues:
        _run_queues[run_id] = asyncio.Queue()
    return _run_queues[run_id]


async def _emit(run_id: int, event_type: str, data: dict) -> None:
    q = get_run_queue(run_id)
    await q.put({"type": event_type, "data": data})


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


async def _fetch_jobs(company: Company) -> list[ScrapedJob]:
    from backend.scrapers import greenhouse as gh_mod

    if company.ats_type.value == "greenhouse":
        return await gh_mod.fetch_greenhouse_jobs(company.ats_identifier or "")
    return []


async def execute_run(run_id: int, session: AsyncSession) -> None:
    run = await session.get(Run, run_id)
    if not run:
        return

    criteria_setting = await get_setting(session, "criteria")
    quarantine_threshold = int(await get_setting(session, "quarantine_threshold") or 3)

    stmt = select(Company).where(Company.is_active == True)
    if run.company_ids:
        stmt = stmt.where(Company.id.in_(run.company_ids))
    companies = (await session.execute(stmt)).scalars().all()

    await _emit(run_id, "run_started", {"run_id": run_id, "company_count": len(companies)})

    total_found = total_heuristic = total_confirmed = 0

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

        found_count = len(scraped)
        total_found += found_count

        new_jobs: list[tuple[Job, ScrapedJob]] = []
        for sj in scraped:
            job_id_str = compute_job_id(sj, company.id)
            existing = (
                await session.execute(
                    select(Job).where(Job.company_id == company.id, Job.job_id == job_id_str)
                )
            ).scalar_one_or_none()

            if existing:
                existing.last_seen_at = datetime.now(timezone.utc)
                continue

            normalized_title = _normalize(sj.title)
            job = Job(
                company_id=company.id,
                job_id=job_id_str,
                title=sj.title,
                location=sj.location,
                url=sj.url,
                raw_description=sj.raw_description,
                normalized_title=normalized_title,
                normalized_location=_normalize(sj.location or ""),
                is_active=True,
            )
            session.add(job)
            await session.flush()
            new_jobs.append((job, sj))

        passed = [(job, sj) for job, sj in new_jobs if passes_heuristic(sj, criteria_setting or {})]
        total_heuristic += len(passed)

        await _emit(run_id, "company_done", {
            "company_id": company.id,
            "jobs_found": found_count,
            "passed_heuristic": len(passed),
            "confirmed": 0,
        })

        result_row.status = CompanyResultStatus.done
        result_row.jobs_found = found_count
        result_row.passed_heuristic = len(passed)
        company.quarantine_count = 0

    run.total_jobs_found = total_found
    run.total_passed_heuristic = total_heuristic
    run.total_confirmed = total_confirmed
    run.status = RunStatus.completed
    run.completed_at = datetime.now(timezone.utc)
    await session.commit()

    await _emit(run_id, "run_done", {"run_id": run_id, "status": "completed", "total_confirmed": total_confirmed})
    _run_queues.pop(run_id, None)
```

- [ ] **Step 2: Write `backend/routers/runs.py`**

```python
import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session, AsyncSessionLocal
from backend.models.run import Run, RunCompanyResult, RunStatus
from backend.pipeline import execute_run, get_run_queue

router = APIRouter(prefix="/runs", tags=["runs"])
Session = Annotated[AsyncSession, Depends(get_session)]


class RunCreate(BaseModel):
    company_ids: list[int] | None = None
    preview: bool = False


@router.post("", status_code=201)
async def start_run(req: RunCreate, background_tasks: BackgroundTasks, session: Session):
    run = Run(is_preview=req.preview, company_ids=req.company_ids)
    session.add(run)
    await session.commit()
    await session.refresh(run)

    async def run_in_background(run_id: int):
        async with AsyncSessionLocal() as bg_session:
            await execute_run(run_id, bg_session)

    background_tasks.add_task(run_in_background, run.id)
    return {"id": run.id, "status": run.status}


@router.get("")
async def list_runs(session: Session):
    rows = (await session.execute(select(Run).order_by(Run.started_at.desc()).limit(50))).scalars().all()
    return [
        {
            "id": r.id, "status": r.status, "is_preview": r.is_preview,
            "started_at": r.started_at, "completed_at": r.completed_at,
            "total_jobs_found": r.total_jobs_found,
            "total_confirmed": r.total_confirmed,
            "total_notified": r.total_notified,
        }
        for r in rows
    ]


@router.get("/{run_id}")
async def get_run(run_id: int, session: Session):
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    results = (await session.execute(
        select(RunCompanyResult).where(RunCompanyResult.run_id == run_id)
    )).scalars().all()
    return {
        "id": run.id, "status": run.status, "started_at": run.started_at,
        "company_results": [
            {"company_id": r.company_id, "status": r.status,
             "jobs_found": r.jobs_found, "confirmed": r.confirmed}
            for r in results
        ],
    }


@router.get("/{run_id}/stream")
async def stream_run(run_id: int):
    async def generator():
        q = get_run_queue(run_id)
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield "event: ping\ndata: {}\n\n"
                continue
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
            if event["type"] == "run_done":
                break

    return StreamingResponse(generator(), media_type="text/event-stream")
```

- [ ] **Step 3: Register runs router in `backend/main.py`**

```python
from backend.routers import system, companies, runs as runs_router

def create_app() -> FastAPI:
    app = FastAPI(title="Joblin", lifespan=lifespan)
    app.include_router(system.router, prefix="/api")
    app.include_router(companies.router, prefix="/api")
    app.include_router(runs_router.router, prefix="/api")
    ...
```

- [ ] **Step 4: Write `tests/test_runs.py`**

```python
import pytest
from unittest.mock import AsyncMock, patch


async def test_start_run_returns_run_id(client):
    with patch("backend.pipeline.execute_run", new_callable=AsyncMock):
        response = await client.post("/api/runs", json={})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] == "running"


async def test_list_runs_empty(client):
    response = await client.get("/api/runs")
    assert response.status_code == 200
    assert response.json() == []
```

- [ ] **Step 5: Run tests**

```powershell
.venv/Scripts/pytest tests/ -v
```

Expected: all tests PASS (health, stats, scrapers, companies, runs).

- [ ] **Step 6: Commit**

```powershell
git add backend/pipeline.py backend/routers/runs.py tests/test_runs.py backend/main.py
git commit -m "feat: run pipeline core and runs router with SSE stream"
```

---

**Phase 2 complete.** Companies can be added with ATS auto-detection. Greenhouse jobs are scraped, deduplicated, and heuristic-filtered. Runs are created via API and execute in the background. Proceed to Phase 3.
