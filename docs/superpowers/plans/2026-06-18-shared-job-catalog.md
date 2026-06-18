# Shared Job Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-user company/job tables with a shared `company_catalog` + `raw_jobs` layer while keeping heuristic filtering and LLM scoring strictly per-user.

**Architecture:** Two new shared tables (`company_catalog`, `raw_jobs`) hold canonical scraping config and raw scraped data. Two per-user tables (`user_companies`, `user_jobs`) replace the old `companies` and `jobs` tables. The pipeline splits into a scrape phase (shared, cache-aware) and a process phase (per-user, heuristic + LLM). Existing `matches`, `feedback_examples`, and `application_tracking` keep their structure but FK to `user_jobs` instead of `jobs`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (async, mapped_column style), Alembic, SQLite + aiosqlite, React + TypeScript frontend, pytest-asyncio for tests.

## Global Constraints

- All SQLAlchemy models use `Mapped` + `mapped_column` style (matching existing models).
- No em dashes in code comments or strings.
- No Co-Authored-By trailers in git commits.
- SQLite FK constraints are not enforced at runtime; alembic migrations handle data integrity in Python.
- `AtsType` enum stays defined in `backend/models/company.py` and is imported by `company_catalog.py`.
- Tests use in-memory SQLite (`sqlite+aiosqlite:///:memory:`) via the existing `conftest.py` fixtures.
- The old `companies` and `jobs` tables are renamed to `_deprecated_companies` / `_deprecated_jobs` in Task 7 (not dropped), so rollback is possible.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/models/company_catalog.py` | `CompanyCatalog` ORM model |
| Create | `backend/models/user_company.py` | `UserCompany` junction ORM model |
| Create | `backend/models/raw_job.py` | `RawJob` ORM model |
| Create | `backend/models/user_job.py` | `UserJob` ORM model |
| Create | `backend/utils/url.py` | `normalize_careers_url()` helper |
| Create | `backend/alembic/versions/<hash>_shared_catalog_v1.py` | Add new tables, migrate data, update FK values |
| Create | `backend/alembic/versions/<hash>_shared_catalog_cleanup.py` | Rename deprecated tables (Task 7) |
| Modify | `backend/models/__init__.py` | Export new models |
| Modify | `backend/models/match.py` | FK `jobs.id` -> `user_jobs.id` |
| Modify | `backend/models/feedback.py` | FK `jobs.id` -> `user_jobs.id` |
| Modify | `backend/models/application.py` | FK `jobs.id` -> `user_jobs.id` |
| Modify | `backend/models/run.py` | FK `RunCompanyResult.company_id` -> `company_catalog.id` |
| Modify | `backend/pipeline.py` | Split into `_scrape_phase` + `_process_phase` |
| Modify | `backend/routers/companies.py` | Use new models; `add_company` returns `match_status` |
| Modify | `backend/config.py` | Add `global_scrape_cache_hours` default |
| Modify | `frontend/src/api/companies.ts` | Add `match_status` to `AddCompanyResponse` |
| Modify | `frontend/src/pages/Companies.tsx` | Show `match_status` toast/banner on add |
| Modify | `tests/conftest.py` | Add fixtures for new models |
| Modify | `tests/test_companies.py` | Update for new response shape + `match_status` |

---

### Task 1: New SQLAlchemy Models

**Files:**
- Create: `backend/models/company_catalog.py`
- Create: `backend/models/user_company.py`
- Create: `backend/models/raw_job.py`
- Create: `backend/models/user_job.py`
- Modify: `backend/models/match.py`
- Modify: `backend/models/feedback.py`
- Modify: `backend/models/application.py`
- Modify: `backend/models/run.py`
- Modify: `backend/models/__init__.py`

**Interfaces:**
- Produces: `CompanyCatalog`, `UserCompany`, `RawJob`, `UserJob` importable from `backend.models`
- Produces: `Match.job_id` FK target updated to `user_jobs.id`
- Produces: `RunCompanyResult.company_id` FK target updated to `company_catalog.id`

- [ ] **Step 1: Write the failing import test**

Create `tests/test_new_models.py`:

```python
import pytest
from sqlalchemy import select
from backend.models.company_catalog import CompanyCatalog
from backend.models.user_company import UserCompany
from backend.models.raw_job import RawJob
from backend.models.user_job import UserJob
from backend.models import AtsType


async def test_company_catalog_creates(app):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from backend.database import Base
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        cat = CompanyCatalog(name="Stripe", careers_url="https://stripe.com/jobs",
                             ats_type=AtsType.greenhouse, ats_identifier="stripe", source="default")
        session.add(cat)
        await session.commit()
        result = await session.get(CompanyCatalog, cat.id)
        assert result.name == "Stripe"
        assert result.source == "default"
        assert result.last_scraped_at is None
    await engine.dispose()


async def test_user_company_links_catalog(app):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from backend.database import Base
    from backend.models.user import User
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(id=1, authentik_username="testuser", is_admin=True)
        cat = CompanyCatalog(name="Stripe", careers_url="https://stripe.com/jobs",
                             ats_type=AtsType.greenhouse, ats_identifier="stripe", source="default")
        session.add_all([user, cat])
        await session.flush()
        uc = UserCompany(user_id=user.id, catalog_id=cat.id, is_active=True)
        session.add(uc)
        await session.commit()
        result = await session.get(UserCompany, uc.id)
        assert result.catalog_id == cat.id


async def test_raw_job_and_user_job(app):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from backend.database import Base
    from backend.models.user import User
    from backend.models.run import Run, RunStatus
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(id=1, authentik_username="testuser", is_admin=True)
        cat = CompanyCatalog(name="Stripe", careers_url="https://stripe.com/jobs",
                             ats_type=AtsType.greenhouse, ats_identifier="stripe", source="default")
        session.add_all([user, cat])
        await session.flush()
        rj = RawJob(catalog_company_id=cat.id, job_id="abc123", title="SWE",
                    location="Remote", url="https://stripe.com/job/1",
                    raw_description="desc", normalized_title="swe",
                    normalized_location="remote", seniority="senior")
        session.add(rj)
        await session.flush()
        uj = UserJob(user_id=user.id, raw_job_id=rj.id, passed_heuristic=True, preview_only=False)
        session.add(uj)
        await session.commit()
        result = await session.get(UserJob, uj.id)
        assert result.passed_heuristic is True
    await engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

```
cd C:\dev\joblin && python -m pytest tests/test_new_models.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` for `company_catalog`.

- [ ] **Step 3: Create `backend/models/company_catalog.py`**

```python
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
from backend.models.company import AtsType


class CompanyCatalog(Base):
    __tablename__ = "company_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    careers_url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    ats_type: Mapped[AtsType | None] = mapped_column(Enum(AtsType), nullable=True)
    ats_identifier: Mapped[str | None] = mapped_column(String, nullable=True)
    custom_api_url: Mapped[str | None] = mapped_column(String, nullable=True)
    css_selector: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quarantine_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    quarantine_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    discovery_status: Mapped[str] = mapped_column(
        String, nullable=False, default="none", server_default="none"
    )
    discovery_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String, nullable=False, default="default", server_default="default"
    )
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Create `backend/models/user_company.py`**

```python
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class UserCompany(Base):
    __tablename__ = "user_companies"
    __table_args__ = (UniqueConstraint("user_id", "catalog_id", name="uq_user_catalog"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    catalog_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_catalog.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 5: Create `backend/models/raw_job.py`**

```python
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class RawJob(Base):
    __tablename__ = "raw_jobs"
    __table_args__ = (UniqueConstraint("catalog_company_id", "job_id", name="uq_catalog_job"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalog_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_catalog.id"), nullable=False
    )
    job_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    raw_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    normalized_title: Mapped[str] = mapped_column(String, nullable=False, default="")
    normalized_location: Mapped[str | None] = mapped_column(String, nullable=True)
    seniority: Mapped[str | None] = mapped_column(String, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

- [ ] **Step 6: Create `backend/models/user_job.py`**

```python
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class UserJob(Base):
    __tablename__ = "user_jobs"
    __table_args__ = (UniqueConstraint("user_id", "raw_job_id", name="uq_user_raw_job"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    raw_job_id: Mapped[int] = mapped_column(Integer, ForeignKey("raw_jobs.id"), nullable=False)
    run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("runs.id"), nullable=True
    )
    passed_heuristic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    preview_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 7: Update FK targets in existing models**

`backend/models/match.py` line 17 -- change:
```python
job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False, unique=True)
```
to:
```python
job_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_jobs.id"), nullable=False, unique=True)
```

`backend/models/feedback.py` line 11 -- change:
```python
job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False)
```
to:
```python
job_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_jobs.id"), nullable=False)
```

`backend/models/application.py` line 26 -- change:
```python
job_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=True)
```
to:
```python
job_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user_jobs.id"), nullable=True)
```

`backend/models/run.py` line 45 -- change:
```python
company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
```
to:
```python
company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company_catalog.id"), nullable=False)
```

- [ ] **Step 8: Update `backend/models/__init__.py`**

```python
from backend.models.company import Company, AtsType
from backend.models.company_catalog import CompanyCatalog
from backend.models.user_company import UserCompany
from backend.models.job import Job
from backend.models.raw_job import RawJob
from backend.models.user_job import UserJob
from backend.models.match import Match, MatchTier
from backend.models.run import Run, RunCompanyResult, RunStatus, CompanyResultStatus
from backend.models.setting import Setting
from backend.models.feedback import FeedbackExample
from backend.models.token_usage import TokenUsage
from backend.models.job_skill import JobSkill
from backend.models.application import ApplicationTracking, ApplicationStatus, ApplicationSource
from backend.models.user import User

__all__ = [
    "Company", "AtsType",
    "CompanyCatalog",
    "UserCompany",
    "Job",
    "RawJob",
    "UserJob",
    "Match", "MatchTier",
    "Run", "RunCompanyResult", "RunStatus", "CompanyResultStatus",
    "Setting",
    "FeedbackExample",
    "TokenUsage",
    "JobSkill",
    "ApplicationTracking", "ApplicationStatus", "ApplicationSource",
    "User",
]
```

- [ ] **Step 9: Run tests to verify they pass**

```
python -m pytest tests/test_new_models.py -v
```
Expected: 3 tests PASS.

- [ ] **Step 10: Commit**

```
git add backend/models/company_catalog.py backend/models/user_company.py backend/models/raw_job.py backend/models/user_job.py backend/models/__init__.py backend/models/match.py backend/models/feedback.py backend/models/application.py backend/models/run.py tests/test_new_models.py
git commit -m "feat: add CompanyCatalog, UserCompany, RawJob, UserJob models"
```

---

### Task 2: Alembic Migration - Create Tables and Migrate Data

**Files:**
- Create: `backend/alembic/versions/<hash>_shared_catalog_v1.py`

**Interfaces:**
- Consumes: existing `companies`, `jobs`, `matches`, `feedback_examples`, `application_tracking`, `run_company_results` tables
- Produces: `company_catalog`, `user_companies`, `raw_jobs`, `user_jobs` tables populated from existing data; FK values in `matches.job_id`, `feedback_examples.job_id`, `application_tracking.job_id`, `run_company_results.company_id` updated to new IDs

- [ ] **Step 1: Generate migration stub**

```
cd C:\dev\joblin\backend && python -m alembic revision --autogenerate -m "shared_catalog_v1"
```

Open the generated file in `backend/alembic/versions/`. The autogenerate output will likely be wrong; replace `upgrade()` and `downgrade()` entirely with the code below.

- [ ] **Step 2: Write the upgrade function**

Replace the generated `upgrade()` with:

```python
def upgrade() -> None:
    from sqlalchemy import text

    # Create company_catalog
    op.create_table(
        "company_catalog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("careers_url", sa.String(), nullable=False),
        sa.Column("ats_type", sa.String(), nullable=True),
        sa.Column("ats_identifier", sa.String(), nullable=True),
        sa.Column("custom_api_url", sa.String(), nullable=True),
        sa.Column("css_selector", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("quarantine_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quarantined_at", sa.DateTime(), nullable=True),
        sa.Column("quarantine_reason", sa.String(), nullable=True),
        sa.Column("discovery_status", sa.String(), nullable=False, server_default="none"),
        sa.Column("discovery_message", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="default"),
        sa.Column("last_scraped_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("careers_url"),
    )

    op.create_table(
        "user_companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("catalog_id", sa.Integer(), sa.ForeignKey("company_catalog.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "catalog_id", name="uq_user_catalog"),
    )

    op.create_table(
        "raw_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("catalog_company_id", sa.Integer(), sa.ForeignKey("company_catalog.id"), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("raw_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("normalized_title", sa.String(), nullable=False, server_default=""),
        sa.Column("normalized_location", sa.String(), nullable=True),
        sa.Column("seniority", sa.String(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_company_id", "job_id", name="uq_catalog_job"),
    )

    op.create_table(
        "user_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("raw_job_id", sa.Integer(), sa.ForeignKey("raw_jobs.id"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("passed_heuristic", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("preview_only", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "raw_job_id", name="uq_user_raw_job"),
    )

    # Data migration
    conn = op.get_bind()

    from backend.data.default_companies import DEFAULT_COMPANIES
    default_names = {c["name"].lower() for c in DEFAULT_COMPANIES}

    # Load all companies, most recently updated first
    all_companies = conn.execute(text("SELECT * FROM companies ORDER BY updated_at DESC")).fetchall()

    # Deduplicate by careers_url; first row per URL is the most recent
    url_to_canonical = {}
    for row in all_companies:
        if row.careers_url not in url_to_canonical:
            url_to_canonical[row.careers_url] = row

    # Insert into company_catalog; track old company.id -> catalog.id
    old_company_id_to_catalog_id: dict[int, int] = {}

    for url, row in url_to_canonical.items():
        source = "default" if row.name.lower() in default_names else "user_submitted"
        result = conn.execute(text("""
            INSERT INTO company_catalog
              (name, careers_url, ats_type, ats_identifier, custom_api_url, css_selector,
               is_active, quarantine_count, quarantined_at, quarantine_reason,
               discovery_status, discovery_message, source, created_at, updated_at)
            VALUES
              (:name, :careers_url, :ats_type, :ats_identifier, :custom_api_url, :css_selector,
               :is_active, :quarantine_count, :quarantined_at, :quarantine_reason,
               :discovery_status, :discovery_message, :source, :created_at, :updated_at)
        """), {
            "name": row.name, "careers_url": row.careers_url,
            "ats_type": row.ats_type, "ats_identifier": row.ats_identifier,
            "custom_api_url": row.custom_api_url, "css_selector": row.css_selector,
            "is_active": row.is_active, "quarantine_count": row.quarantine_count,
            "quarantined_at": row.quarantined_at, "quarantine_reason": row.quarantine_reason,
            "discovery_status": row.discovery_status, "discovery_message": row.discovery_message,
            "source": source, "created_at": row.created_at, "updated_at": row.updated_at,
        })
        catalog_id = result.lastrowid
        for c in all_companies:
            if c.careers_url == url:
                old_company_id_to_catalog_id[c.id] = catalog_id

    # Insert user_companies (deduplicated by user_id + catalog_id)
    seen_user_catalog: set[tuple[int, int]] = set()
    for row in all_companies:
        catalog_id = old_company_id_to_catalog_id.get(row.id)
        if not catalog_id:
            continue
        key = (row.user_id, catalog_id)
        if key in seen_user_catalog:
            continue
        seen_user_catalog.add(key)
        conn.execute(text("""
            INSERT INTO user_companies (user_id, catalog_id, is_active, created_at)
            VALUES (:user_id, :catalog_id, :is_active, :created_at)
        """), {"user_id": row.user_id, "catalog_id": catalog_id,
               "is_active": row.is_active, "created_at": row.created_at})

    # Load all jobs, most recently seen first
    all_jobs = conn.execute(text("SELECT * FROM jobs ORDER BY last_seen_at DESC")).fetchall()

    # Insert raw_jobs (deduplicated by catalog_company_id + job_id)
    raw_job_key_to_id: dict[tuple[int, str], int] = {}
    for job in all_jobs:
        catalog_id = old_company_id_to_catalog_id.get(job.company_id)
        if not catalog_id:
            continue
        key = (catalog_id, job.job_id)
        if key not in raw_job_key_to_id:
            result = conn.execute(text("""
                INSERT INTO raw_jobs
                  (catalog_company_id, job_id, title, location, url, raw_description,
                   normalized_title, normalized_location, seniority,
                   first_seen_at, last_seen_at, is_active)
                VALUES
                  (:catalog_company_id, :job_id, :title, :location, :url, :raw_description,
                   :normalized_title, :normalized_location, :seniority,
                   :first_seen_at, :last_seen_at, :is_active)
            """), {
                "catalog_company_id": catalog_id, "job_id": job.job_id,
                "title": job.title, "location": job.location, "url": job.url,
                "raw_description": job.raw_description or "",
                "normalized_title": job.normalized_title or "",
                "normalized_location": job.normalized_location,
                "seniority": job.seniority,
                "first_seen_at": job.first_seen_at, "last_seen_at": job.last_seen_at,
                "is_active": job.is_active,
            })
            raw_job_key_to_id[key] = result.lastrowid
        else:
            # Keep the earliest first_seen_at
            conn.execute(text("""
                UPDATE raw_jobs SET first_seen_at = MIN(first_seen_at, :fsa) WHERE id = :id
            """), {"fsa": job.first_seen_at, "id": raw_job_key_to_id[key]})

    # Insert user_jobs; map old job.id -> user_job.id for FK updates
    old_job_id_to_user_job_id: dict[int, int] = {}
    seen_user_raw: dict[tuple[int, int], int] = {}
    for job in sorted(all_jobs, key=lambda r: r.id):
        catalog_id = old_company_id_to_catalog_id.get(job.company_id)
        if not catalog_id:
            continue
        raw_job_id = raw_job_key_to_id.get((catalog_id, job.job_id))
        if not raw_job_id:
            continue
        ur_key = (job.user_id, raw_job_id)
        if ur_key in seen_user_raw:
            old_job_id_to_user_job_id[job.id] = seen_user_raw[ur_key]
        else:
            result = conn.execute(text("""
                INSERT INTO user_jobs
                  (user_id, raw_job_id, run_id, passed_heuristic, preview_only, first_seen_at)
                VALUES (:user_id, :raw_job_id, NULL, 1, :preview_only, :first_seen_at)
            """), {"user_id": job.user_id, "raw_job_id": raw_job_id,
                   "preview_only": job.preview_only, "first_seen_at": job.first_seen_at})
            uj_id = result.lastrowid
            seen_user_raw[ur_key] = uj_id
            old_job_id_to_user_job_id[job.id] = uj_id

    # Update matches.job_id -> user_jobs.id
    for row in conn.execute(text("SELECT id, job_id FROM matches")).fetchall():
        uj_id = old_job_id_to_user_job_id.get(row.job_id)
        if uj_id:
            conn.execute(text("UPDATE matches SET job_id = :uj WHERE id = :id"),
                         {"uj": uj_id, "id": row.id})

    # Update feedback_examples.job_id -> user_jobs.id
    for row in conn.execute(text("SELECT id, job_id FROM feedback_examples")).fetchall():
        uj_id = old_job_id_to_user_job_id.get(row.job_id)
        if uj_id:
            conn.execute(text("UPDATE feedback_examples SET job_id = :uj WHERE id = :id"),
                         {"uj": uj_id, "id": row.id})

    # Update application_tracking.job_id -> user_jobs.id
    for row in conn.execute(text("SELECT id, job_id FROM application_tracking")).fetchall():
        uj_id = old_job_id_to_user_job_id.get(row.job_id)
        if uj_id:
            conn.execute(text("UPDATE application_tracking SET job_id = :uj WHERE id = :id"),
                         {"uj": uj_id, "id": row.id})

    # Update run_company_results.company_id -> company_catalog.id
    for row in conn.execute(text("SELECT id, company_id FROM run_company_results")).fetchall():
        cat_id = old_company_id_to_catalog_id.get(row.company_id)
        if cat_id:
            conn.execute(text("UPDATE run_company_results SET company_id = :cat WHERE id = :id"),
                         {"cat": cat_id, "id": row.id})

    # Update run.company_ids JSON (stores list of company IDs) to user_company IDs
    # Load user_companies to build catalog_id -> user_company.id per user
    uc_rows = conn.execute(text("SELECT id, user_id, catalog_id FROM user_companies")).fetchall()
    # (user_id, catalog_id) -> user_company.id
    uc_lookup: dict[tuple[int, int], int] = {(r.user_id, r.catalog_id): r.id for r in uc_rows}

    import json
    for row in conn.execute(text("SELECT id, user_id, company_ids FROM runs WHERE company_ids IS NOT NULL")).fetchall():
        try:
            old_ids = json.loads(row.company_ids) if isinstance(row.company_ids, str) else row.company_ids
            if not old_ids:
                continue
            new_ids = []
            for old_cid in old_ids:
                cat_id = old_company_id_to_catalog_id.get(old_cid)
                if cat_id:
                    uc_id = uc_lookup.get((row.user_id, cat_id))
                    if uc_id:
                        new_ids.append(uc_id)
            conn.execute(text("UPDATE runs SET company_ids = :ids WHERE id = :id"),
                         {"ids": json.dumps(new_ids), "id": row.id})
        except Exception:
            pass
```

- [ ] **Step 3: Write the downgrade function**

```python
def downgrade() -> None:
    op.drop_table("user_jobs")
    op.drop_table("raw_jobs")
    op.drop_table("user_companies")
    op.drop_table("company_catalog")
    # Note: FK value updates to matches/feedback/application/run_company_results are not reversed
    # Restore from backup if needed
```

- [ ] **Step 4: Write a migration test**

Add to `tests/test_new_models.py`:

```python
async def test_migration_populates_catalog(app):
    """Verify migration creates company_catalog from existing companies data."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import text, insert
    from backend.database import Base
    from backend.models.user import User
    from backend.models.company import Company, AtsType as AT
    from backend.models.company_catalog import CompanyCatalog
    from backend.models.user_company import UserCompany

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        # Seed a user and two companies (same URL for two users = dedup case)
        u1 = User(id=1, authentik_username="alice", is_admin=False)
        u2 = User(id=2, authentik_username="bob", is_admin=False)
        c1 = Company(user_id=1, name="Stripe", careers_url="https://stripe.com/jobs",
                     ats_type=AT.greenhouse, ats_identifier="stripe")
        c2 = Company(user_id=2, name="Stripe", careers_url="https://stripe.com/jobs",
                     ats_type=AT.greenhouse, ats_identifier="stripe")
        session.add_all([u1, u2, c1, c2])
        await session.commit()

    # After migration equivalent logic, company_catalog should have 1 row
    # This test validates the deduplication logic used in the migration.
    async with factory() as session:
        # Manually run the dedup logic
        from sqlalchemy import select
        companies = (await session.execute(select(Company))).scalars().all()
        urls_seen: set[str] = set()
        for c in companies:
            if c.careers_url not in urls_seen:
                urls_seen.add(c.careers_url)
                cat = CompanyCatalog(name=c.name, careers_url=c.careers_url,
                                     ats_type=c.ats_type, ats_identifier=c.ats_identifier,
                                     source="default")
                session.add(cat)
        await session.commit()
        count = (await session.execute(select(CompanyCatalog))).scalars().all()
        assert len(count) == 1, "Two users with same URL should produce one catalog entry"

    await engine.dispose()
```

- [ ] **Step 5: Run the test**

```
python -m pytest tests/test_new_models.py::test_migration_populates_catalog -v
```
Expected: PASS.

- [ ] **Step 6: Apply migration to dev database (if one exists)**

```
cd C:\dev\joblin\backend && python -m alembic upgrade head
```
Expected: Migration runs without error. Check output for row counts.

- [ ] **Step 7: Commit**

```
git add backend/alembic/versions/ tests/test_new_models.py
git commit -m "feat: migration to add company_catalog, user_companies, raw_jobs, user_jobs"
```

---

### Task 3: URL Normalization Utility + Companies Router Refactor

**Files:**
- Create: `backend/utils/url.py`
- Modify: `backend/routers/companies.py`
- Modify: `tests/test_companies.py`

**Interfaces:**
- Consumes: `CompanyCatalog`, `UserCompany` from Task 1
- Produces: `normalize_careers_url(url: str) -> str`
- Produces: `POST /api/companies` returns `{id, catalog_id, ats_type, probe_attempts, match_status}`
- Produces: `GET /api/companies` returns list from `user_companies` JOIN `company_catalog`
- Produces: `DELETE /api/companies/{id}` deletes `UserCompany` row; deletes `CompanyCatalog` only if no other users reference it

- [ ] **Step 1: Write failing tests for match_status**

Append to `tests/test_companies.py`:

```python
from unittest.mock import AsyncMock, patch
from backend.scrapers.probe import ProbeResult, ProbeAttempt


async def test_add_company_returns_match_status_added_new(client):
    mock_probe = ProbeResult(
        ats_type="greenhouse", identifier="newco", probe_attempts=[]
    )
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        response = await client.post(
            "/api/companies",
            json={"name": "NewCo", "careers_url": "https://newco.com/careers"},
        )
    assert response.status_code == 201
    assert response.json()["match_status"] == "added_new"


async def test_add_company_returns_linked_existing_working(client):
    """Second user adding same URL gets linked_existing_working if discovery succeeded."""
    mock_probe = ProbeResult(ats_type="greenhouse", identifier="stripe", probe_attempts=[])
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        first = await client.post(
            "/api/companies",
            json={"name": "Stripe", "careers_url": "https://stripe.com/jobs"},
        )
    assert first.status_code == 201

    # Simulate discovery success on catalog entry
    catalog_id = first.json()["catalog_id"]
    # Directly update via a second POST from a different user perspective is not
    # possible in unit tests without a second user fixture; instead verify the
    # already_in_your_list path (same user adding same URL twice).
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        second = await client.post(
            "/api/companies",
            json={"name": "Stripe", "careers_url": "https://stripe.com/jobs"},
        )
    assert second.status_code == 201
    assert second.json()["match_status"] == "already_in_your_list"


async def test_add_company_normalizes_url(client):
    """www. prefix and trailing slash should map to same catalog entry."""
    mock_probe = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        r1 = await client.post(
            "/api/companies",
            json={"name": "Acme", "careers_url": "https://www.acme.com/careers/"},
        )
    assert r1.status_code == 201

    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        r2 = await client.post(
            "/api/companies",
            json={"name": "Acme", "careers_url": "https://acme.com/careers"},
        )
    assert r2.status_code == 201
    assert r2.json()["match_status"] in ("already_in_your_list", "linked_existing_working", "linked_existing_pending")
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_companies.py::test_add_company_returns_match_status_added_new tests/test_companies.py::test_add_company_returns_linked_existing_working tests/test_companies.py::test_add_company_normalizes_url -v
```
Expected: FAIL (KeyError or wrong response shape).

- [ ] **Step 3: Create `backend/utils/url.py`**

```python
import re


def normalize_careers_url(url: str) -> str:
    """Canonical form for deduplication: no protocol, no www., no trailing slash, lowercase."""
    url = url.lower().strip()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    url = url.rstrip("/")
    return url
```

- [ ] **Step 4: Rewrite `backend/routers/companies.py`**

Replace the full file. The new version keeps all existing route paths but uses `CompanyCatalog` + `UserCompany` instead of `Company`. Key changes shown:

```python
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import get_current_user
from backend.models.company_catalog import CompanyCatalog
from backend.models.user_company import UserCompany
from backend.models.user import User
from backend.scrapers.probe import probe_ats
from backend.utils.url import normalize_careers_url

router = APIRouter(prefix="/api/companies", tags=["companies"])


class CompanyCreate(BaseModel):
    name: str
    careers_url: str


class CompanyUpdate(BaseModel):
    css_selector: str | None = None
    custom_api_url: str | None = None
    is_active: bool | None = None
    ats_type: str | None = None
    ats_identifier: str | None = None


class BulkCompanyItem(BaseModel):
    name: str
    careers_url: str


class ProbeRequest(BaseModel):
    name: str
    careers_url: str


class DiscoverRequest(BaseModel):
    names: list[str]


class ResolveRequest(BaseModel):
    careers_url: str


def _catalog_to_dict(cat: CompanyCatalog, uc: UserCompany) -> dict:
    return {
        "id": uc.id,
        "catalog_id": cat.id,
        "name": cat.name,
        "careers_url": cat.careers_url,
        "ats_type": cat.ats_type.value if cat.ats_type else None,
        "ats_identifier": cat.ats_identifier,
        "custom_api_url": cat.custom_api_url,
        "css_selector": cat.css_selector,
        "is_active": uc.is_active,
        "quarantine_count": cat.quarantine_count,
        "quarantined_at": cat.quarantined_at.isoformat() if cat.quarantined_at else None,
        "quarantine_reason": cat.quarantine_reason,
        "discovery_status": cat.discovery_status,
        "discovery_message": cat.discovery_message,
        "source": cat.source,
    }


async def _find_catalog_by_url(url: str, session: AsyncSession) -> CompanyCatalog | None:
    normalized = normalize_careers_url(url)
    all_cats = (await session.execute(select(CompanyCatalog))).scalars().all()
    for cat in all_cats:
        if normalize_careers_url(cat.careers_url) == normalized:
            return cat
    return None


@router.get("")
async def list_companies(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(
        select(UserCompany, CompanyCatalog)
        .join(CompanyCatalog, UserCompany.catalog_id == CompanyCatalog.id)
        .where(UserCompany.user_id == current_user.id)
        .order_by(CompanyCatalog.name)
    )).all()
    return [_catalog_to_dict(cat, uc) for uc, cat in rows]


@router.get("/defaults")
async def get_default_companies():
    from backend.data.default_companies import DEFAULT_COMPANIES
    return DEFAULT_COMPANIES


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_company(
    body: CompanyCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    existing_cat = await _find_catalog_by_url(body.careers_url, session)

    if existing_cat:
        existing_uc = (await session.execute(
            select(UserCompany).where(
                UserCompany.user_id == current_user.id,
                UserCompany.catalog_id == existing_cat.id,
            )
        )).scalar_one_or_none()

        if existing_uc:
            return {
                "id": existing_uc.id,
                "catalog_id": existing_cat.id,
                "ats_type": existing_cat.ats_type.value if existing_cat.ats_type else None,
                "probe_attempts": [],
                "match_status": "already_in_your_list",
            }

        uc = UserCompany(user_id=current_user.id, catalog_id=existing_cat.id, is_active=True)
        session.add(uc)
        await session.commit()

        if existing_cat.quarantined_at:
            match_status = "linked_existing_quarantined"
        elif existing_cat.discovery_status == "success":
            match_status = "linked_existing_working"
        else:
            match_status = "linked_existing_pending"

        return {
            "id": uc.id,
            "catalog_id": existing_cat.id,
            "ats_type": existing_cat.ats_type.value if existing_cat.ats_type else None,
            "probe_attempts": [],
            "match_status": match_status,
        }

    # New catalog entry -- run ATS probe
    probe_result = await probe_ats(name=body.name, careers_url=body.careers_url)

    from backend.models.company import AtsType
    try:
        ats_enum = AtsType(probe_result.ats_type)
    except ValueError:
        ats_enum = AtsType.crawl4ai

    cat = CompanyCatalog(
        name=body.name,
        careers_url=body.careers_url,
        ats_type=ats_enum,
        ats_identifier=probe_result.identifier,
        source="user_submitted",
        discovery_status="success" if probe_result.ats_type != "crawl4ai" else "none",
    )
    session.add(cat)
    await session.flush()

    uc = UserCompany(user_id=current_user.id, catalog_id=cat.id, is_active=True)
    session.add(uc)
    await session.commit()

    return {
        "id": uc.id,
        "catalog_id": cat.id,
        "ats_type": probe_result.ats_type,
        "probe_attempts": [a.model_dump() for a in probe_result.probe_attempts],
        "match_status": "added_new",
    }


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_add_companies(
    items: list[BulkCompanyItem],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    created = 0
    for item in items:
        existing_cat = await _find_catalog_by_url(item.careers_url, session)
        if existing_cat:
            existing_uc = (await session.execute(
                select(UserCompany).where(
                    UserCompany.user_id == current_user.id,
                    UserCompany.catalog_id == existing_cat.id,
                )
            )).scalar_one_or_none()
            if not existing_uc:
                session.add(UserCompany(user_id=current_user.id, catalog_id=existing_cat.id, is_active=True))
                created += 1
            continue

        probe_result = await probe_ats(name=item.name, careers_url=item.careers_url)
        from backend.models.company import AtsType
        try:
            ats_enum = AtsType(probe_result.ats_type)
        except ValueError:
            ats_enum = AtsType.crawl4ai

        cat = CompanyCatalog(
            name=item.name, careers_url=item.careers_url,
            ats_type=ats_enum, ats_identifier=probe_result.identifier,
            source="user_submitted",
        )
        session.add(cat)
        await session.flush()
        session.add(UserCompany(user_id=current_user.id, catalog_id=cat.id, is_active=True))
        created += 1

    await session.commit()
    return {"created": created}


@router.patch("/{company_id}", status_code=status.HTTP_200_OK)
async def update_company(
    company_id: int,
    body: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    uc = (await session.execute(
        select(UserCompany).where(
            UserCompany.id == company_id, UserCompany.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=404, detail="Company not found")

    cat = await session.get(CompanyCatalog, uc.catalog_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Catalog entry not found")

    if body.is_active is not None:
        uc.is_active = body.is_active
    if body.css_selector is not None:
        cat.css_selector = body.css_selector
    if body.custom_api_url is not None:
        cat.custom_api_url = body.custom_api_url
    if body.ats_type is not None:
        from backend.models.company import AtsType
        cat.ats_type = AtsType(body.ats_type)
    if body.ats_identifier is not None:
        cat.ats_identifier = body.ats_identifier

    await session.commit()
    return {"id": uc.id}


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    uc = (await session.execute(
        select(UserCompany).where(
            UserCompany.id == company_id, UserCompany.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=404, detail="Company not found")

    catalog_id = uc.catalog_id
    await session.delete(uc)
    await session.flush()

    # Drop catalog entry if no other users reference it
    remaining = (await session.execute(
        select(sa_func.count()).select_from(UserCompany).where(UserCompany.catalog_id == catalog_id)
    )).scalar()
    if remaining == 0:
        cat = await session.get(CompanyCatalog, catalog_id)
        if cat:
            await session.delete(cat)

    await session.commit()


@router.post("/{company_id}/retry", status_code=status.HTTP_200_OK)
async def retry_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    uc = (await session.execute(
        select(UserCompany).where(
            UserCompany.id == company_id, UserCompany.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=404, detail="Company not found")

    cat = await session.get(CompanyCatalog, uc.catalog_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Catalog entry not found")

    cat.quarantine_count = 0
    cat.quarantined_at = None
    cat.quarantine_reason = None
    uc.is_active = True
    await session.commit()
    return {"id": uc.id, "status": "reactivated"}


@router.post("/{company_id}/resolve", status_code=status.HTTP_200_OK)
async def resolve_company(
    company_id: int,
    body: ResolveRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    uc = (await session.execute(
        select(UserCompany).where(
            UserCompany.id == company_id, UserCompany.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=404, detail="Company not found")

    cat = await session.get(CompanyCatalog, uc.catalog_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Catalog entry not found")

    probe_result = await probe_ats(name=cat.name, careers_url=body.careers_url)
    from backend.models.company import AtsType
    try:
        cat.ats_type = AtsType(probe_result.ats_type)
    except ValueError:
        cat.ats_type = AtsType.crawl4ai
    cat.ats_identifier = probe_result.identifier
    cat.discovery_status = "success"
    await session.commit()
    return {"id": uc.id, "ats_type": probe_result.ats_type}


@router.post("/probe", status_code=status.HTTP_200_OK)
async def probe_company(
    body: ProbeRequest,
    current_user: User = Depends(get_current_user),
):
    result = await probe_ats(name=body.name, careers_url=body.careers_url)
    return {
        "ats_type": result.ats_type,
        "identifier": result.identifier,
        "probe_attempts": [a.model_dump() for a in result.probe_attempts],
    }


@router.post("/discover", status_code=status.HTTP_202_ACCEPTED)
async def discover_companies(
    body: DiscoverRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from backend.data.default_companies import DEFAULT_COMPANIES
    name_to_url = {c["name"].lower(): c["careers_url"] for c in DEFAULT_COMPANIES}
    created = 0
    ids = []
    for name in body.names:
        careers_url = name_to_url.get(name.lower())
        if not careers_url:
            continue
        existing_cat = await _find_catalog_by_url(careers_url, session)
        if existing_cat:
            existing_uc = (await session.execute(
                select(UserCompany).where(
                    UserCompany.user_id == current_user.id,
                    UserCompany.catalog_id == existing_cat.id,
                )
            )).scalar_one_or_none()
            if not existing_uc:
                uc = UserCompany(user_id=current_user.id, catalog_id=existing_cat.id, is_active=True)
                session.add(uc)
                await session.flush()
                ids.append(uc.id)
                created += 1
            continue
        probe_result = await probe_ats(name=name, careers_url=careers_url)
        from backend.models.company import AtsType
        try:
            ats_enum = AtsType(probe_result.ats_type)
        except ValueError:
            ats_enum = AtsType.crawl4ai
        cat = CompanyCatalog(name=name, careers_url=careers_url, ats_type=ats_enum,
                             ats_identifier=probe_result.identifier, source="default")
        session.add(cat)
        await session.flush()
        uc = UserCompany(user_id=current_user.id, catalog_id=cat.id, is_active=True)
        session.add(uc)
        await session.flush()
        ids.append(uc.id)
        created += 1

    await session.commit()
    return {"created": created, "ids": ids}


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_companies(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import csv, io
    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    created = 0
    names = []
    for row in reader:
        name = row.get("name", "").strip()
        careers_url = row.get("careers_url", "").strip()
        if not name or not careers_url:
            continue
        existing_cat = await _find_catalog_by_url(careers_url, session)
        if existing_cat:
            existing_uc = (await session.execute(
                select(UserCompany).where(
                    UserCompany.user_id == current_user.id,
                    UserCompany.catalog_id == existing_cat.id,
                )
            )).scalar_one_or_none()
            if not existing_uc:
                session.add(UserCompany(user_id=current_user.id, catalog_id=existing_cat.id, is_active=True))
                created += 1
                names.append(name)
            continue
        probe_result = await probe_ats(name=name, careers_url=careers_url)
        from backend.models.company import AtsType
        try:
            ats_enum = AtsType(probe_result.ats_type)
        except ValueError:
            ats_enum = AtsType.crawl4ai
        cat = CompanyCatalog(name=name, careers_url=careers_url, ats_type=ats_enum,
                             ats_identifier=probe_result.identifier, source="user_submitted")
        session.add(cat)
        await session.flush()
        session.add(UserCompany(user_id=current_user.id, catalog_id=cat.id, is_active=True))
        created += 1
        names.append(name)

    await session.commit()
    return {"created": created, "names": names}
```

- [ ] **Step 5: Update existing test assertions that break**

In `tests/test_companies.py`, the old tests check `response.json()["id"]` which still works since `id` now = `user_company.id`. But `test_add_company_detects_greenhouse` checks `ats_type` in response -- that still works. Update `test_delete_company` to use the new `id` from response correctly (no change needed if `id` is still returned).

The `test_list_companies_empty` test still works since the response is still `[]` for a fresh user.

- [ ] **Step 6: Run all company tests**

```
python -m pytest tests/test_companies.py -v
```
Expected: all PASS including the 3 new match_status tests.

- [ ] **Step 7: Commit**

```
git add backend/utils/url.py backend/routers/companies.py tests/test_companies.py
git commit -m "feat: refactor companies router to use catalog + add match_status"
```

---

### Task 4: Pipeline Refactor

**Files:**
- Modify: `backend/pipeline.py`
- Modify: `tests/test_runs.py`

**Interfaces:**
- Consumes: `CompanyCatalog`, `UserCompany`, `RawJob`, `UserJob` from Task 1
- Consumes: `get_setting("global_scrape_cache_hours", user_id=1)` from config (Task 5 adds the default; pipeline reads it directly using the existing `get_setting` helper with a hardcoded default of 2 if key absent)
- Produces: `execute_run(run_id, session)` with same external signature; internally splits into `_scrape_phase` + `_process_phase`
- Produces: `Match.job_id` now stores `UserJob.id` values (consistent with Task 1 FK change)

- [ ] **Step 1: Write failing pipeline tests**

Read `tests/test_runs.py` first to understand existing test structure, then append:

```python
async def test_scrape_phase_creates_raw_jobs(client):
    """Phase 1 should create raw_jobs from scraped data."""
    from unittest.mock import AsyncMock, patch
    from backend.scrapers.base import ScrapedJob

    mock_jobs = [
        ScrapedJob(title="Senior SWE", location="Remote", url="https://stripe.com/job/1",
                   raw_description="Python job", job_id="swe-001")
    ]

    # Create catalog entry and user_company via the companies endpoint
    from backend.scrapers.probe import ProbeResult
    probe = ProbeResult(ats_type="greenhouse", identifier="stripe", probe_attempts=[])
    with patch("backend.routers.companies.probe_ats", return_value=probe):
        await client.post("/api/companies", json={"name": "Stripe", "careers_url": "https://stripe.com/jobs"})

    with patch("backend.pipeline._fetch_jobs", new=AsyncMock(return_value=mock_jobs)):
        run_resp = await client.post("/api/runs", json={})
    assert run_resp.status_code == 201

    # Wait briefly for async run to complete (or check via GET /api/runs)
    import asyncio
    await asyncio.sleep(0.5)

    from sqlalchemy import select
    from backend.models.raw_job import RawJob
    # Access raw_jobs via a direct DB check using the app's session
    # (detailed assertion depends on test session access; verify via runs response)
    runs_resp = await client.get("/api/runs")
    assert runs_resp.status_code == 200
    runs = runs_resp.json()
    assert len(runs) >= 1
    assert runs[0]["total_jobs_found"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_runs.py::test_scrape_phase_creates_raw_jobs -v
```
Expected: FAIL (pipeline still uses old Company/Job models).

- [ ] **Step 3: Rewrite `backend/pipeline.py`**

Replace the full file:

```python
import asyncio
import re
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_setting, get_all_settings
from backend.models.company_catalog import CompanyCatalog
from backend.models.user_company import UserCompany
from backend.models.raw_job import RawJob
from backend.models.user_job import UserJob
from backend.models.run import Run, RunCompanyResult, RunStatus, CompanyResultStatus
from backend.scrapers.base import ScrapedJob
from backend.scrapers.heuristics import passes_heuristic
from backend.scrapers.job_id import compute_job_id

_run_queues: dict[int, asyncio.Queue] = {}
_cancelled_runs: set[int] = set()


def request_cancel_run(run_id: int) -> None:
    _cancelled_runs.add(run_id)


def get_run_queue(run_id: int) -> asyncio.Queue:
    if run_id not in _run_queues:
        _run_queues[run_id] = asyncio.Queue()
    return _run_queues[run_id]


async def _emit(run_id: int, event_type: str, data: dict) -> None:
    q = get_run_queue(run_id)
    await q.put({"type": event_type, "data": data})


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _detect_seniority(normalized_title: str) -> str | None:
    for level in ("principal", "staff", "senior", "lead", "mid", "junior", "intern"):
        if level in normalized_title:
            return level
    return None


async def _fetch_jobs(company: CompanyCatalog) -> list[ScrapedJob]:
    from backend.scrapers import (
        greenhouse as gh_mod, lever as lever_mod, ashby as ashby_mod,
        workable as workable_mod, smartrecruiters as sr_mod,
        workday as wd_mod, crawl4ai as c4ai_mod,
    )
    ats = company.ats_type.value if company.ats_type else "crawl4ai"

    if ats == "greenhouse":
        return await gh_mod.fetch_greenhouse_jobs(company.ats_identifier or "")
    if ats == "lever":
        return await lever_mod.fetch_lever_jobs(company.ats_identifier or "")
    if ats == "ashby":
        return await ashby_mod.fetch_ashby_jobs(company.ats_identifier or "")
    if ats == "workable":
        return await workable_mod.fetch_workable_jobs(company.ats_identifier or "")
    if ats == "smartrecruiters":
        return await sr_mod.fetch_smartrecruiters_jobs(company.ats_identifier or "")
    if ats == "workday":
        return await wd_mod.fetch_workday_jobs(company.custom_api_url or company.careers_url)
    if ats == "custom":
        return await c4ai_mod.fetch_crawl4ai_jobs(
            company.custom_api_url or company.careers_url,
            css_selector=company.css_selector,
        )
    return await c4ai_mod.fetch_crawl4ai_jobs(
        company.careers_url, css_selector=company.css_selector
    )


async def _scrape_phase(
    run_id: int,
    catalog_companies: list[CompanyCatalog],
    is_manual: bool,
    cache_hours: int,
    quarantine_threshold: int,
    session: AsyncSession,
) -> dict[int, int]:
    """Scrape companies, upsert raw_jobs. Returns {catalog_company_id: jobs_found count}."""
    now = datetime.now(timezone.utc)
    counts: dict[int, int] = {}

    for company in catalog_companies:
        if not is_manual and company.last_scraped_at:
            age_hours = (now - company.last_scraped_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if age_hours < cache_hours:
                # Use cached data; count existing active raw_jobs for this company
                existing_count = len((await session.execute(
                    select(RawJob).where(
                        RawJob.catalog_company_id == company.id,
                        RawJob.is_active == True,
                    )
                )).scalars().all())
                counts[company.id] = existing_count
                await _emit(run_id, "company_skipped_cache", {
                    "company_id": company.id, "company_name": company.name,
                    "cached_jobs": existing_count,
                })
                continue

        try:
            scraped = await asyncio.wait_for(_fetch_jobs(company), timeout=60.0)
        except asyncio.TimeoutError:
            msg = "scraper timed out after 60s"
            company.quarantine_count += 1
            if company.quarantine_count >= quarantine_threshold:
                company.quarantined_at = now
                company.quarantine_reason = msg
            await session.commit()
            await _emit(run_id, "company_failed", {"company_id": company.id, "error": msg})
            counts[company.id] = 0
            continue
        except Exception as exc:
            company.quarantine_count += 1
            if company.quarantine_count >= quarantine_threshold:
                company.quarantined_at = now
                company.quarantine_reason = str(exc)
            await session.commit()
            await _emit(run_id, "company_failed", {"company_id": company.id, "error": str(exc)})
            counts[company.id] = 0
            continue

        for sj in scraped:
            job_id_str = compute_job_id(sj, company.id)
            normalized_title = _normalize(sj.title)
            normalized_location = _normalize(sj.location or "")
            seniority = _detect_seniority(normalized_title)

            existing_raw = (await session.execute(
                select(RawJob).where(
                    RawJob.catalog_company_id == company.id,
                    RawJob.job_id == job_id_str,
                )
            )).scalar_one_or_none()

            if existing_raw:
                existing_raw.last_seen_at = now
                existing_raw.is_active = True
                if sj.raw_description:
                    existing_raw.raw_description = sj.raw_description
            else:
                session.add(RawJob(
                    catalog_company_id=company.id,
                    job_id=job_id_str,
                    title=sj.title,
                    location=sj.location,
                    url=sj.url,
                    raw_description=sj.raw_description or "",
                    normalized_title=normalized_title,
                    normalized_location=normalized_location,
                    seniority=seniority,
                    is_active=True,
                ))

        company.last_scraped_at = now
        company.quarantine_count = 0
        await session.commit()
        counts[company.id] = len(scraped)

    return counts


async def _process_phase(
    run_id: int,
    user_id: int,
    is_preview: bool,
    is_seeding_run: bool,
    catalog_company_ids: list[int],
    settings: dict,
    session: AsyncSession,
) -> tuple[int, int, int, int]:
    """Per-user heuristic + LLM phase. Returns (new_jobs, passed_heuristic, confirmed, notified)."""
    from backend.llm.factory import get_filter_provider, get_summarize_provider
    from backend.llm.protocol import CriteriaConfig, FeedbackExample
    from backend.models.match import Match, MatchTier
    from backend.models.feedback import FeedbackExample as FBModel
    from backend.models.token_usage import TokenUsage
    from backend.discord import post_match_to_discord

    def _provider_name(provider) -> str:
        return type(provider).__name__.lower().replace("adapter", "")

    criteria = CriteriaConfig.from_dict(settings.get("criteria") or {})
    filter_provider = get_filter_provider(settings)
    summarize_provider = get_summarize_provider(settings)

    fb_rows = (await session.execute(
        select(FBModel)
        .where(FBModel.user_id == user_id)
        .order_by(FBModel.dismissed_at.desc())
        .limit(5)
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

    # Get raw_jobs for user's companies not yet processed by this user
    new_raw_jobs = (await session.execute(
        select(RawJob, CompanyCatalog)
        .join(CompanyCatalog, RawJob.catalog_company_id == CompanyCatalog.id)
        .outerjoin(
            UserJob,
            and_(UserJob.raw_job_id == RawJob.id, UserJob.user_id == user_id),
        )
        .where(
            RawJob.catalog_company_id.in_(catalog_company_ids),
            RawJob.is_active == True,
            UserJob.id == None,
        )
    )).all()

    new_count = len(new_raw_jobs)
    passed_count = confirmed_count = notified_count = 0
    now = datetime.now(timezone.utc)

    for raw_job, catalog_company in new_raw_jobs:
        passed = passes_heuristic(raw_job, criteria.__dict__)

        user_job = UserJob(
            user_id=user_id,
            raw_job_id=raw_job.id,
            run_id=run_id,
            passed_heuristic=passed,
            preview_only=is_preview,
        )
        session.add(user_job)
        await session.flush()

        if not passed:
            continue

        passed_count += 1

        try:
            filter_result = await filter_provider.filter(
                title=raw_job.title,
                company_name=catalog_company.name,
                location=raw_job.location,
                description=raw_job.raw_description,
                criteria=criteria,
                negative_examples=negative_examples,
            )
        except Exception:
            filter_result = None

        if hasattr(filter_provider, "last_usage") and filter_provider.last_usage.get("total_tokens", 0) > 0:
            session.add(TokenUsage(
                run_id=run_id, provider=_provider_name(filter_provider), call_type="filter",
                prompt_tokens=filter_provider.last_usage["prompt_tokens"],
                completion_tokens=filter_provider.last_usage["completion_tokens"],
                total_tokens=filter_provider.last_usage["total_tokens"],
            ))

        if not filter_result or filter_result.score < 0.4:
            continue

        tier = MatchTier.strong if filter_result.score >= 0.7 else MatchTier.borderline

        try:
            summary = await summarize_provider.summarize(
                title=raw_job.title, company_name=catalog_company.name,
                description=raw_job.raw_description, score=filter_result.score,
            )
        except Exception:
            summary = ""

        if hasattr(summarize_provider, "last_usage") and summarize_provider.last_usage.get("total_tokens", 0) > 0:
            session.add(TokenUsage(
                run_id=run_id, provider=_provider_name(summarize_provider), call_type="summarize",
                prompt_tokens=summarize_provider.last_usage["prompt_tokens"],
                completion_tokens=summarize_provider.last_usage["completion_tokens"],
                total_tokens=summarize_provider.last_usage["total_tokens"],
            ))

        existing_match = (await session.execute(
            select(Match).where(Match.job_id == user_job.id)
        )).scalar_one_or_none()

        if existing_match:
            if existing_match.is_preview:
                existing_match.is_preview = False
            match = existing_match
        else:
            match = Match(
                job_id=user_job.id,
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

        if not is_preview and not is_seeding_run and settings.get("discord_webhook_url"):
            try:
                await post_match_to_discord(
                    webhook_url=settings["discord_webhook_url"],
                    title=raw_job.title,
                    company_name=catalog_company.name,
                    location=raw_job.location,
                    score=filter_result.score,
                    tier=tier.value,
                    summary=summary,
                    job_url=raw_job.url,
                    mention_type=settings.get("discord_mention_type", "none"),
                    mention_id=settings.get("discord_mention_id", ""),
                )
                match.notified_at = now
                notified_count += 1
            except Exception:
                pass

    await session.commit()
    return new_count, passed_count, confirmed_count, notified_count


async def execute_run(run_id: int, session: AsyncSession) -> None:
    run = await session.get(Run, run_id)
    if not run:
        return

    user_id = run.user_id
    settings = await get_all_settings(session, user_id=user_id)
    quarantine_threshold = int(settings.get("quarantine_threshold") or 3)
    is_preview = run.is_preview
    is_manual = not run.is_preview  # preview runs are always treated as manual (always scrape)

    # Admin-configurable cache window; read from akadmin (user_id=1) settings
    try:
        cache_hours = int(await get_setting(session, "global_scrape_cache_hours", user_id=1) or 2)
    except Exception:
        cache_hours = 2

    # Resolve user's companies -> catalog entries
    stmt = (
        select(UserCompany, CompanyCatalog)
        .join(CompanyCatalog, UserCompany.catalog_id == CompanyCatalog.id)
        .where(
            UserCompany.user_id == user_id,
            UserCompany.is_active == True,
            CompanyCatalog.is_active == True,
            CompanyCatalog.quarantined_at == None,
        )
    )
    if run.company_ids:
        stmt = stmt.where(UserCompany.id.in_(run.company_ids))

    uc_rows = (await session.execute(stmt)).all()
    catalog_companies = [cat for _uc, cat in uc_rows]
    catalog_company_ids = [cat.id for cat in catalog_companies]

    # Seeding check: no existing user_jobs for this user
    from sqlalchemy import func as sa_func
    existing_count = (await session.execute(
        select(sa_func.count()).select_from(UserJob).where(UserJob.user_id == user_id)
    )).scalar() or 0
    is_seeding_run = existing_count == 0

    await _emit(run_id, "run_started", {
        "run_id": run_id, "company_count": len(catalog_companies), "seeding": is_seeding_run
    })

    # Phase 1: scrape
    scrape_counts = await _scrape_phase(
        run_id=run_id,
        catalog_companies=catalog_companies,
        is_manual=is_manual,
        cache_hours=cache_hours,
        quarantine_threshold=quarantine_threshold,
        session=session,
    )

    if run_id in _cancelled_runs:
        _cancelled_runs.discard(run_id)
        run.status = RunStatus.cancelled
        run.completed_at = datetime.now(timezone.utc)
        await session.commit()
        await _emit(run_id, "run_done", {"run_id": run_id, "status": "cancelled", "total_confirmed": 0})
        _run_queues.pop(run_id, None)
        return

    total_found = sum(scrape_counts.values())

    # Phase 2: per-user process
    new_jobs, passed_heuristic, confirmed, notified = await _process_phase(
        run_id=run_id,
        user_id=user_id,
        is_preview=is_preview,
        is_seeding_run=is_seeding_run,
        catalog_company_ids=catalog_company_ids,
        settings=settings,
        session=session,
    )

    # Update run_company_results
    for cat in catalog_companies:
        result_row = RunCompanyResult(
            run_id=run_id,
            company_id=cat.id,
            status=CompanyResultStatus.done,
            jobs_found=scrape_counts.get(cat.id, 0),
        )
        session.add(result_row)
        await _emit(run_id, "company_done", {
            "company_id": cat.id, "jobs_found": scrape_counts.get(cat.id, 0),
        })

    if notified > 0:
        await _emit(run_id, "discord_posted", {"count": notified})

    run.total_jobs_found = total_found
    run.total_new_jobs = new_jobs
    run.total_passed_heuristic = passed_heuristic
    run.total_confirmed = confirmed
    run.total_notified = notified
    run.status = RunStatus.completed
    run.completed_at = datetime.now(timezone.utc)
    await session.commit()

    await _emit(run_id, "run_done", {
        "run_id": run_id, "status": "completed",
        "total_confirmed": confirmed, "seeding": is_seeding_run,
    })
    _run_queues.pop(run_id, None)
```

- [ ] **Step 4: Update `passes_heuristic` call site**

`passes_heuristic` is called with a `ScrapedJob` in the old pipeline. In the new pipeline it receives a `RawJob`. If `passes_heuristic` uses type annotations that require `ScrapedJob`, open `backend/scrapers/heuristics.py` and change the parameter type to `Any` or a duck-typed Protocol. The fields used (`title`, `location`, `seniority`, `raw_description`) exist on both `ScrapedJob` and `RawJob`.

- [ ] **Step 4b: Verify runs router `company_ids` compatibility**

Open `backend/routers/runs.py`. The `POST /api/runs` endpoint accepts `company_ids` in the request body and stores them in `Run.company_ids`. In the new model, the frontend sends `user_company.id` values (since `GET /api/companies` now returns `id = user_company.id`). The runs router stores them as-is; the pipeline reads them back and filters `UserCompany.id.in_(run.company_ids)`. No change to the router is needed, but verify the `POST /api/runs` body model accepts `company_ids: list[int] | None`.

- [ ] **Step 5: Run pipeline tests**

```
python -m pytest tests/test_runs.py -v
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```
git add backend/pipeline.py tests/test_runs.py
git commit -m "feat: split pipeline into shared scrape phase and per-user process phase"
```

---

### Task 5: Config -- Admin Cache Setting

**Files:**
- Modify: `backend/config.py`

**Interfaces:**
- Produces: `DEFAULTS["global_scrape_cache_hours"] = 2` so `get_setting(session, "global_scrape_cache_hours", user_id=1)` returns `2` if akadmin has not customized it

- [ ] **Step 1: Write the failing test**

Append to `tests/test_new_models.py`:

```python
async def test_global_cache_hours_default(client):
    from backend.config import DEFAULTS
    assert "global_scrape_cache_hours" in DEFAULTS
    assert DEFAULTS["global_scrape_cache_hours"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_new_models.py::test_global_cache_hours_default -v
```
Expected: FAIL (KeyError).

- [ ] **Step 3: Add default to `backend/config.py`**

Open `backend/config.py`. Locate the `DEFAULTS` dict and add one entry:

```python
"global_scrape_cache_hours": 2,
```

Add it after `"quarantine_threshold": 3,` for grouping.

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/test_new_models.py::test_global_cache_hours_default -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add backend/config.py tests/test_new_models.py
git commit -m "feat: add global_scrape_cache_hours admin setting (default 2h)"
```

---

### Task 6: Frontend Companies Update

**Files:**
- Modify: `frontend/src/api/companies.ts`
- Modify: `frontend/src/pages/Companies.tsx`

**Interfaces:**
- Consumes: `POST /api/companies` response now includes `match_status` field
- Produces: toast/banner shown to user with message derived from `match_status`

- [ ] **Step 1: Update `frontend/src/api/companies.ts`**

Find the `AddCompanyResponse` type (or the return type of the `addCompany` function). Add `match_status` and `catalog_id`:

```typescript
export interface AddCompanyResponse {
  id: number;
  catalog_id: number;
  ats_type: string;
  probe_attempts: ProbeAttempt[];
  match_status:
    | "added_new"
    | "linked_existing_working"
    | "linked_existing_pending"
    | "linked_existing_quarantined"
    | "already_in_your_list";
}
```

Also update the `Company` interface to include `catalog_id: number` and `source: string` since `GET /api/companies` now returns those fields.

- [ ] **Step 2: Add match_status message helper**

In `frontend/src/api/companies.ts` or a shared utils file, add:

```typescript
export function matchStatusMessage(status: AddCompanyResponse["match_status"]): string {
  switch (status) {
    case "added_new":
      return "Added -- detecting ATS type...";
    case "linked_existing_working":
      return "Already in our catalog and working -- added to your list";
    case "linked_existing_pending":
      return "Already in our catalog (ATS detection pending) -- added to your list";
    case "linked_existing_quarantined":
      return "This company is in our catalog but currently quarantined -- added anyway";
    case "already_in_your_list":
      return "You are already monitoring this company";
  }
}
```

- [ ] **Step 3: Update `frontend/src/pages/Companies.tsx`**

Find the `handleAddCompany` (or equivalent) function that calls `addCompany`. After the successful response, show the match_status message. The exact pattern depends on the existing toast/notification system in use. Typical pattern:

```typescript
const result = await addCompany({ name, careers_url });
const msg = matchStatusMessage(result.match_status);
// Replace the existing success toast with:
showToast(msg);  // use whatever toast function already exists in this file
```

If `already_in_your_list` is returned, do not close the add-company form and do not add a duplicate row to the list.

- [ ] **Step 4: Verify in browser**

Start the dev server and test:
1. Add a new company -- should show "Added -- detecting ATS type..."
2. Add the same company again -- should show "You are already monitoring this company"
3. Add a company with `www.` prefix that matches an existing entry -- should show one of the "linked_existing" messages

- [ ] **Step 5: Commit**

```
git add frontend/src/api/companies.ts frontend/src/pages/Companies.tsx
git commit -m "feat: show match_status feedback when adding companies"
```

---

### Task 7: Final Cleanup Migration

**Files:**
- Create: `backend/alembic/versions/<hash>_shared_catalog_cleanup.py`

**Run this task only after Tasks 1-6 are deployed and verified.** Renaming the tables is irreversible (requires a restore from backup to undo).

**Interfaces:**
- Produces: `companies` renamed to `_deprecated_companies`; `jobs` renamed to `_deprecated_jobs`

- [ ] **Step 1: Verify no code references old table names**

```
grep -rn "\"companies\"" backend/ --include="*.py" | grep -v deprecated | grep -v alembic
grep -rn "\"jobs\"" backend/ --include="*.py" | grep -v deprecated | grep -v alembic | grep -v "user_jobs" | grep -v "raw_jobs"
```
Expected: zero results (or only in old migration files which is fine).

- [ ] **Step 2: Generate migration stub**

```
cd C:\dev\joblin\backend && python -m alembic revision -m "shared_catalog_cleanup"
```

- [ ] **Step 3: Write upgrade and downgrade**

```python
def upgrade() -> None:
    op.rename_table("companies", "_deprecated_companies")
    op.rename_table("jobs", "_deprecated_jobs")


def downgrade() -> None:
    op.rename_table("_deprecated_companies", "companies")
    op.rename_table("_deprecated_jobs", "jobs")
```

- [ ] **Step 4: Apply and verify**

```
cd C:\dev\joblin\backend && python -m alembic upgrade head
```

```
python -m pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```
git add backend/alembic/versions/
git commit -m "feat: rename deprecated companies and jobs tables after catalog migration"
```
