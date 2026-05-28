# Joblin Phase 1 -- Scaffold + DB + Auth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a working FastAPI server with all SQLAlchemy models, Alembic migrations, config seeding from env vars, health + stats endpoints, and a Docker Compose stack that starts cleanly.

**Architecture:** Single FastAPI process, SQLite via aiosqlite, Alembic async migrations run at startup, APScheduler not yet wired, no scraping or LLM.

**Tech Stack:** Python 3.12, FastAPI 0.115+, SQLAlchemy 2.x async, aiosqlite, Alembic, uvicorn, Docker Compose, pytest, pytest-asyncio, httpx.

---

## File Map

| File | Responsibility |
|---|---|
| `backend/database.py` | Engine, session factory, Base, `get_session` dependency |
| `backend/models/company.py` | Company ORM model |
| `backend/models/job.py` | Job ORM model |
| `backend/models/match.py` | Match ORM model |
| `backend/models/run.py` | Run + RunCompanyResult ORM models |
| `backend/models/setting.py` | Setting ORM model |
| `backend/models/feedback.py` | FeedbackExample ORM model |
| `backend/config.py` | Read settings from DB; seed missing keys from env |
| `backend/routers/system.py` | GET /api/health, GET /api/stats |
| `backend/main.py` | App factory, lifespan, router mounts, StaticFiles |
| `backend/alembic/env.py` | Async Alembic env |
| `backend/alembic/versions/001_initial_schema.py` | First migration |
| `tests/conftest.py` | Async test client + in-memory DB fixture |
| `tests/test_health.py` | Health + stats endpoint tests |
| `backend/requirements.txt` | Python dependencies |
| `docker-compose.yml` | App service skeleton (Caddy added in Phase 7) |
| `.env.example` | Required env vars |
| `.gitignore` | Python + Node ignores |

---

## Task 1: Repo skeleton + Python environment

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `backend/__init__.py`
- Create: `backend/models/__init__.py`
- Create: `backend/routers/__init__.py`

- [ ] **Step 1: Create directory structure**

```powershell
cd C:\dev\joblin
New-Item -ItemType Directory -Force backend, backend/models, backend/routers, backend/scrapers, backend/llm, backend/alembic/versions, frontend, presets, tests | Out-Null
New-Item -ItemType File -Force backend/__init__.py, backend/models/__init__.py, backend/routers/__init__.py, backend/scrapers/__init__.py, backend/llm/__init__.py, tests/__init__.py | Out-Null
Write-Output "done"
```

Expected: `done`

- [ ] **Step 2: Write `backend/requirements.txt`**

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
sqlalchemy[asyncio]>=2.0.36
aiosqlite>=0.20.0
alembic>=1.14.0
apscheduler>=4.0.0a5
httpx>=0.28.0
groq>=0.12.0
cerebras-cloud-sdk>=1.19.0
google-genai>=1.0.0
crawl4ai>=0.4.0
playwright>=1.49.0
python-multipart>=0.0.20
pydantic>=2.10.0
```

- [ ] **Step 3: Write `backend/requirements-dev.txt`**

```
-r requirements.txt
pytest>=8.3.0
pytest-asyncio>=0.24.0
httpx>=0.28.0
```

- [ ] **Step 4: Write `.env.example`**

```
APP_PASSWORD=changeme
PUBLIC_HOSTNAME=jobs.example.com
GROQ_API_KEY=
CEREBRAS_API_KEY=
GEMINI_API_KEY=
DISCORD_WEBHOOK_URL=
```

- [ ] **Step 5: Write `.gitignore`**

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
*.db
*.db-shm
*.db-wal
.env
frontend/dist/
frontend/node_modules/
.superpowers/
```

- [ ] **Step 6: Create virtual env and install deps**

```powershell
cd C:\dev\joblin\backend
python -m venv ../.venv
../.venv/Scripts/pip install -r requirements-dev.txt
```

Expected: packages install without errors.

- [ ] **Step 7: Commit**

```powershell
cd C:\dev\joblin
git add .
git commit -m "chore: repo skeleton and Python dependencies"
```

---

## Task 2: SQLAlchemy models

**Files:**
- Create: `backend/database.py`
- Create: `backend/models/company.py`
- Create: `backend/models/job.py`
- Create: `backend/models/match.py`
- Create: `backend/models/run.py`
- Create: `backend/models/setting.py`
- Create: `backend/models/feedback.py`
- Modify: `backend/models/__init__.py`

- [ ] **Step 1: Write `backend/database.py`**

```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


DATABASE_URL = "sqlite+aiosqlite:///./joblin.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 2: Write `backend/models/company.py`**

```python
import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class AtsType(str, enum.Enum):
    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"
    workable = "workable"
    smartrecruiters = "smartrecruiters"
    workday = "workday"
    crawl4ai = "crawl4ai"
    custom = "custom"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    careers_url: Mapped[str] = mapped_column(String, nullable=False)
    ats_type: Mapped[AtsType] = mapped_column(Enum(AtsType), nullable=False)
    ats_identifier: Mapped[str | None] = mapped_column(String, nullable=True)
    custom_api_url: Mapped[str | None] = mapped_column(String, nullable=True)
    css_selector: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quarantine_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    quarantine_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 3: Write `backend/models/job.py`**

```python
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("company_id", "job_id", name="uq_company_job"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    raw_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    normalized_title: Mapped[str] = mapped_column(String, nullable=False)
    normalized_location: Mapped[str | None] = mapped_column(String, nullable=True)
    seniority: Mapped[str | None] = mapped_column(String, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

- [ ] **Step 4: Write `backend/models/match.py`**

```python
import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class MatchTier(str, enum.Enum):
    strong = "strong"
    borderline = "borderline"


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False, unique=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("runs.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    tier: Mapped[MatchTier] = mapped_column(Enum(MatchTier), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    filter_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    not_interested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 5: Write `backend/models/run.py`**

```python
import enum
from datetime import datetime
from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class RunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class CompanyResultStatus(str, enum.Enum):
    scraping = "scraping"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.running)
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    company_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    total_jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    total_passed_heuristic: Mapped[int] = mapped_column(Integer, default=0)
    total_confirmed: Mapped[int] = mapped_column(Integer, default=0)
    total_notified: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)


class RunCompanyResult(Base):
    __tablename__ = "run_company_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("runs.id"), nullable=False)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    status: Mapped[CompanyResultStatus] = mapped_column(
        Enum(CompanyResultStatus), default=CompanyResultStatus.scraping
    )
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    passed_heuristic: Mapped[int] = mapped_column(Integer, default=0)
    confirmed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 6: Write `backend/models/setting.py`**

```python
from datetime import datetime
from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 7: Write `backend/models/feedback.py`**

```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class FeedbackExample(Base):
    __tablename__ = "feedback_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_title: Mapped[str] = mapped_column(String, nullable=False)
    normalized_location: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 8: Update `backend/models/__init__.py`**

```python
from backend.models.company import Company, AtsType
from backend.models.job import Job
from backend.models.match import Match, MatchTier
from backend.models.run import Run, RunCompanyResult, RunStatus, CompanyResultStatus
from backend.models.setting import Setting
from backend.models.feedback import FeedbackExample

__all__ = [
    "Company", "AtsType",
    "Job",
    "Match", "MatchTier",
    "Run", "RunCompanyResult", "RunStatus", "CompanyResultStatus",
    "Setting",
    "FeedbackExample",
]
```

- [ ] **Step 9: Verify imports**

```powershell
cd C:\dev\joblin
.venv/Scripts/python -c "from backend.models import Company, Job, Match, Run, Setting, FeedbackExample; print('ok')"
```

Expected: `ok`

- [ ] **Step 10: Commit**

```powershell
git add backend/
git commit -m "feat: SQLAlchemy models for all six tables"
```

---

## Task 3: Alembic setup + async env.py + first migration

**Files:**
- Create: `alembic.ini`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_initial_schema.py`

- [ ] **Step 1: Initialize Alembic**

```powershell
cd C:\dev\joblin\backend
../.venv/Scripts/alembic init alembic
```

Expected: creates `alembic/` directory and `alembic.ini` (move ini to project root).

```powershell
Move-Item alembic.ini ../alembic.ini
```

- [ ] **Step 2: Edit `alembic.ini` -- set script location and DB URL**

In `alembic.ini`, find and replace:
```ini
script_location = alembic
```
with:
```ini
script_location = backend/alembic
sqlalchemy.url = sqlite+aiosqlite:///./joblin.db
```

- [ ] **Step 3: Overwrite `backend/alembic/env.py` with async version**

```python
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context

from backend.database import Base
import backend.models  # noqa: F401 -- register all models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


run_migrations_online()
```

- [ ] **Step 4: Generate the first migration**

```powershell
cd C:\dev\joblin
.venv/Scripts/alembic revision --autogenerate -m "initial schema"
```

Expected: creates a file under `backend/alembic/versions/` with all six tables.

- [ ] **Step 5: Run the migration**

```powershell
.venv/Scripts/alembic upgrade head
```

Expected: `Running upgrade  -> <hash>, initial schema`

- [ ] **Step 6: Verify DB has tables**

```powershell
.venv/Scripts/python -c "
import sqlite3, os
conn = sqlite3.connect('joblin.db')
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print([t[0] for t in tables])
"
```

Expected: list containing `companies`, `jobs`, `matches`, `runs`, `run_company_results`, `settings`, `feedback_examples`.

- [ ] **Step 7: Commit**

```powershell
git add alembic.ini backend/alembic/
git commit -m "feat: Alembic async migrations, initial schema"
```

---

## Task 4: FastAPI app factory + DB session dependency

**Files:**
- Create: `backend/main.py`

- [ ] **Step 1: Write `backend/main.py`**

```python
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.database import engine, Base
from backend.routers import system


FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Joblin", lifespan=lifespan)

    app.include_router(system.router, prefix="/api")

    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")

    return app


app = create_app()
```

- [ ] **Step 2: Write `backend/routers/system.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models import Company, Match, Run

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/stats")
async def stats(session: AsyncSession = Depends(get_session)):
    from datetime import date, datetime, timezone
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    total_companies = (await session.execute(select(func.count()).select_from(Company))).scalar_one()
    total_jobs_in_db = (await session.execute(
        select(func.count()).select_from(
            __import__("backend.models.job", fromlist=["Job"]).Job
        )
    )).scalar_one()
    todays_matches = (await session.execute(
        select(func.count()).select_from(Match).where(Match.created_at >= today_start)
    )).scalar_one()
    strong_today = (await session.execute(
        select(func.count()).select_from(Match).where(
            Match.created_at >= today_start,
            Match.tier == "strong",
        )
    )).scalar_one()
    quarantine_count = (await session.execute(
        select(func.count()).select_from(Company).where(Company.quarantined_at.isnot(None))
    )).scalar_one()
    last_run = (await session.execute(
        select(Run.completed_at).order_by(Run.completed_at.desc()).limit(1)
    )).scalar_one_or_none()

    return {
        "total_companies": total_companies,
        "total_jobs_in_db": total_jobs_in_db,
        "todays_matches": todays_matches,
        "strong_today": strong_today,
        "quarantine_count": quarantine_count,
        "last_run_completed_at": last_run,
    }
```

- [ ] **Step 3: Run the server to verify it starts**

```powershell
cd C:\dev\joblin
.venv/Scripts/uvicorn backend.main:app --reload --port 8000
```

Expected: `INFO: Application startup complete.` -- then open http://localhost:8000/api/health in browser and see `{"status":"ok"}`.

Stop with Ctrl+C.

- [ ] **Step 4: Commit**

```powershell
git add backend/main.py backend/routers/system.py
git commit -m "feat: FastAPI app factory, health and stats endpoints"
```

---

## Task 5: Config service (env seeding + settings CRUD)

**Files:**
- Create: `backend/config.py`

- [ ] **Step 1: Write `backend/config.py`**

```python
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.setting import Setting

DEFAULTS: dict[str, Any] = {
    "discord_webhook_url": os.getenv("DISCORD_WEBHOOK_URL", ""),
    "discord_mention_type": "none",
    "discord_mention_id": "",
    "criteria": {
        "title_allowlist": "",
        "title_denylist": "intern|junior",
        "location_allowlist": "",
        "location_denylist": "",
        "seniority_allowlist": ["senior", "staff", "principal", "lead", "mid"],
        "exclusion_keywords": [],
        "profile_description": "",
    },
    "schedule_cron": "0 */4 * * *",
    "staleness_threshold_hours": 4,
    "quarantine_threshold": 3,
    "groq_api_key": os.getenv("GROQ_API_KEY", ""),
    "cerebras_api_key": os.getenv("CEREBRAS_API_KEY", ""),
    "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
    "llm_filter_provider": "groq",
    "llm_summarize_provider": "cerebras",
    "scheduler_enabled": False,
}


async def seed_defaults(session: AsyncSession) -> None:
    for key, default_value in DEFAULTS.items():
        existing = await session.get(Setting, key)
        if existing is None:
            session.add(Setting(key=key, value=default_value))
    await session.commit()


async def get_setting(session: AsyncSession, key: str) -> Any:
    row = await session.get(Setting, key)
    if row is None:
        return DEFAULTS.get(key)
    return row.value


async def set_setting(session: AsyncSession, key: str, value: Any) -> None:
    row = await session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    await session.commit()


async def get_all_settings(session: AsyncSession) -> dict[str, Any]:
    rows = (await session.execute(select(Setting))).scalars().all()
    result = dict(DEFAULTS)
    for row in rows:
        result[row.key] = row.value
    return result
```

- [ ] **Step 2: Call `seed_defaults` in the lifespan**

In `backend/main.py`, update the lifespan:

```python
from backend.database import engine, AsyncSessionLocal
from backend.config import seed_defaults

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as session:
        await seed_defaults(session)
    yield
```

- [ ] **Step 3: Verify seeding runs on startup**

```powershell
cd C:\dev\joblin
.venv/Scripts/uvicorn backend.main:app --port 8000
```

Then in a second terminal:
```powershell
.venv/Scripts/python -c "
import sqlite3
conn = sqlite3.connect('joblin.db')
rows = conn.execute('SELECT key FROM settings').fetchall()
print([r[0] for r in rows])
"
```

Expected: list of all 14 default setting keys.

Stop server with Ctrl+C.

- [ ] **Step 4: Commit**

```powershell
git add backend/config.py backend/main.py
git commit -m "feat: config service with env seeding and settings CRUD helpers"
```

---

## Task 6: Tests for health, stats, and config

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_health.py`
- Create: `pytest.ini`

- [ ] **Step 1: Write `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 2: Write `tests/conftest.py`**

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.database import Base, get_session
from backend.main import create_app


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def app():
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    application = create_app()

    async def override_get_session():
        async with test_session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_get_session

    yield application

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

- [ ] **Step 3: Write `tests/test_health.py`**

```python
import pytest


async def test_health_returns_ok(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_stats_returns_zeros_on_empty_db(client):
    response = await client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_companies"] == 0
    assert data["todays_matches"] == 0
    assert data["quarantine_count"] == 0
```

- [ ] **Step 4: Run tests**

```powershell
cd C:\dev\joblin
.venv/Scripts/pytest tests/test_health.py -v
```

Expected:
```
tests/test_health.py::test_health_returns_ok PASSED
tests/test_health.py::test_stats_returns_zeros_on_empty_db PASSED
2 passed
```

- [ ] **Step 5: Commit**

```powershell
git add tests/ pytest.ini
git commit -m "test: conftest with in-memory DB fixture, health and stats tests"
```

---

## Task 7: Docker Compose skeleton

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Write `Dockerfile`**

```dockerfile
FROM python:3.12-slim AS backend

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY alembic.ini .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - db_data:/app/joblin.db
    env_file:
      - .env
    restart: unless-stopped

volumes:
  db_data:
```

- [ ] **Step 3: Verify Docker build (requires Docker Desktop running)**

```powershell
cd C:\dev\joblin
docker compose build
```

Expected: build completes without errors.

- [ ] **Step 4: Commit**

```powershell
git add Dockerfile docker-compose.yml
git commit -m "chore: Dockerfile and docker-compose skeleton"
```

---

**Phase 1 complete.** The repo has a working FastAPI server, all ORM models, Alembic async migrations, config seeding, health/stats endpoints, and a Docker Compose skeleton. Proceed to Phase 2.
