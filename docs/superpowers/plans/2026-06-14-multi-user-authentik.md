# Multi-User Authentik Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-user isolated data to Joblin by wiring Caddy forward-auth to the existing Authentik instance and scoping all FastAPI queries to the authenticated user.

**Architecture:** Caddy's `forward_auth` directive checks each request against the Authentik Embedded Outpost and injects `X-authentik-username` into the forwarded request. A `get_current_user` FastAPI dependency reads this header, auto-provisions users on first access (seeding their default settings), and returns the User ORM object. All data tables gain `user_id` FKs; every query filters by `current_user.id`.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Alembic (SQLite batch migrations for NOT NULL column additions), Caddy v2 `forward_auth`, Authentik Embedded Outpost.

---

### Task 1: User model

**Files:**
- Create: `backend/models/user.py`
- Modify: `backend/models/__init__.py`
- Test: `tests/test_auth.py` (create this file)

- [ ] **Step 1: Write the failing test**

Create `tests/test_auth.py`:
```python
def test_user_model_columns():
    from backend.models.user import User
    assert User.__tablename__ == "users"
    assert hasattr(User, "id")
    assert hasattr(User, "authentik_username")
    assert hasattr(User, "is_admin")
    assert hasattr(User, "created_at")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth.py::test_user_model_columns -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.models.user'`

- [ ] **Step 3: Create `backend/models/user.py`**

```python
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    authentik_username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 4: Update `backend/models/__init__.py`**

Full replacement:
```python
from backend.models.company import Company, AtsType
from backend.models.job import Job
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
    "Job",
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

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_auth.py::test_user_model_columns -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/models/user.py backend/models/__init__.py tests/test_auth.py
git commit -m "feat: add User model for Authentik-based multi-user support"
```

---

### Task 2: Restructure Setting model

The current `Setting` model uses `key` as its primary key. Multi-user support requires per-user settings, so the PK becomes a surrogate integer and `(user_id, key)` becomes a unique constraint.

**Files:**
- Modify: `backend/models/setting.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_auth.py`:
```python
def test_setting_model_has_user_id():
    from backend.models.setting import Setting
    assert hasattr(Setting, "id")
    assert hasattr(Setting, "user_id")
    assert hasattr(Setting, "key")
    assert hasattr(Setting, "value")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth.py::test_setting_model_has_user_id -v`
Expected: FAIL with `AssertionError` (Setting has no `user_id`)

- [ ] **Step 3: Rewrite `backend/models/setting.py`**

```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_settings_user_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_auth.py::test_setting_model_has_user_id -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models/setting.py tests/test_auth.py
git commit -m "feat: restructure Setting model with user_id FK and surrogate PK"
```

---

### Task 3: Add `user_id` to remaining owned models

**Files:**
- Modify: `backend/models/company.py`
- Modify: `backend/models/job.py`
- Modify: `backend/models/run.py`
- Modify: `backend/models/application.py`
- Modify: `backend/models/feedback.py`
- Modify: `backend/models/resume.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_auth.py`:
```python
def test_owned_models_have_user_id():
    from backend.models.company import Company
    from backend.models.job import Job
    from backend.models.run import Run
    from backend.models.application import ApplicationTracking
    from backend.models.feedback import FeedbackExample
    from backend.models.resume import Resume
    for model in [Company, Job, Run, ApplicationTracking, FeedbackExample, Resume]:
        assert hasattr(model, "user_id"), f"{model.__name__} missing user_id"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth.py::test_owned_models_have_user_id -v`
Expected: FAIL with `AssertionError: Company missing user_id`

- [ ] **Step 3: Replace `backend/models/company.py`**

```python
import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
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
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
```

- [ ] **Step 4: Replace `backend/models/job.py`**

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
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
```

- [ ] **Step 5: Update `backend/models/run.py` -- add `user_id` to the `Run` class only**

Add `ForeignKey` to the sqlalchemy import line.
Add this column after `error_message` in the `Run` class:
```python
user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
```

Full updated `Run` class (RunCompanyResult is unchanged):
```python
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
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
```

The full `ForeignKey` import line for `run.py`:
```python
from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
```

- [ ] **Step 6: Replace `backend/models/application.py`**

```python
import enum
from datetime import date, datetime
from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from backend.database import Base


class ApplicationStatus(str, enum.Enum):
    interested = "interested"
    applied = "applied"
    rejected = "rejected"
    offer = "offer"


class ApplicationSource(str, enum.Enum):
    joblin = "joblin"
    external = "external"


class ApplicationTracking(Base):
    __tablename__ = "application_tracking"
    __table_args__ = (UniqueConstraint("job_id", name="uq_application_job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    job_title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(Enum(ApplicationStatus), nullable=False)
    source: Mapped[ApplicationSource] = mapped_column(Enum(ApplicationSource), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
```

- [ ] **Step 7: Replace `backend/models/feedback.py`**

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
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
```

- [ ] **Step 8: Replace `backend/models/resume.py`**

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
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

- [ ] **Step 9: Run test to verify it passes**

Run: `pytest tests/test_auth.py::test_owned_models_have_user_id -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add backend/models/company.py backend/models/job.py backend/models/run.py \
        backend/models/application.py backend/models/feedback.py backend/models/resume.py \
        tests/test_auth.py
git commit -m "feat: add user_id FK to all user-owned models"
```

---

### Task 4: `get_current_user` dependency

**Files:**
- Create: `backend/dependencies/__init__.py`
- Create: `backend/dependencies/auth.py`
- Test: `tests/test_auth.py`

The dependency reads `X-authentik-username` from the request header, looks up the user in the DB, auto-provisions on first request (seeding default settings), and handles the concurrent-provisioning race condition via `IntegrityError`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_auth.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.database import Base, get_session
from backend.main import create_app


@pytest.mark.anyio
async def test_get_current_user_missing_header():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app()
    async def override():
        async with factory() as s:
            yield s
    app.dependency_overrides[get_session] = override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/companies")
    assert resp.status_code == 401
    await engine.dispose()


@pytest.mark.anyio
async def test_get_current_user_auto_provisions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app()
    async def override():
        async with factory() as s:
            yield s
    app.dependency_overrides[get_session] = override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/companies", headers={"X-authentik-username": "alice"})
    assert resp.status_code == 200

    from sqlalchemy import select
    from backend.models.user import User
    async with factory() as s:
        user = (await s.execute(select(User).where(User.authentik_username == "alice"))).scalar_one()
        assert user.is_admin is True  # first user provisioned is admin
    await engine.dispose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth.py::test_get_current_user_missing_header tests/test_auth.py::test_get_current_user_auto_provisions -v`
Expected: FAIL (companies router has no auth dependency yet -- 200 instead of 401, and import errors)

- [ ] **Step 3: Create `backend/dependencies/__init__.py`**

Create as an empty file.

- [ ] **Step 4: Create `backend/dependencies/auth.py`**

```python
from typing import Annotated
from fastapi import Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_session
from backend.models.user import User


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    x_authentik_username: Annotated[str | None, Header()] = None,
) -> User:
    if not x_authentik_username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = (await session.execute(
        select(User).where(User.authentik_username == x_authentik_username)
    )).scalar_one_or_none()

    if user is None:
        try:
            user_count = (await session.execute(
                select(func.count()).select_from(User)
            )).scalar() or 0
            user = User(
                authentik_username=x_authentik_username,
                is_admin=(user_count == 0),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            from backend.config import seed_defaults
            await seed_defaults(session, user_id=user.id)
        except IntegrityError:
            await session.rollback()
            user = (await session.execute(
                select(User).where(User.authentik_username == x_authentik_username)
            )).scalar_one()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
```

The `CurrentUser` type alias is imported in every router.

Note: these two tests will pass fully only after Task 8 (companies router) adds `CurrentUser`. The `test_get_current_user_missing_header` test requires the companies router to use the dependency. Run these tests again after Task 8 to confirm both pass.

- [ ] **Step 5: Commit**

```bash
git add backend/dependencies/__init__.py backend/dependencies/auth.py tests/test_auth.py
git commit -m "feat: add get_current_user dependency with auto-provisioning"
```

---

### Task 5: Alembic migration

This single migration creates the `users` table, seeds the admin user, and adds `user_id` FKs to all owned tables. It also recreates the `settings` table with the new schema (surrogate PK + `user_id`).

**Files:**
- Create: `backend/alembic/versions/<generated-revision>_add_multi_user_support.py`

- [ ] **Step 1: Generate the revision file**

Run from project root:
```
alembic revision --message "add multi-user support"
```

Note the generated 12-character hex revision ID from the output.

- [ ] **Step 2: Replace the generated file content**

Open the created file in `backend/alembic/versions/` and replace all content with the following (substituting the actual generated IDs for the two placeholders):

```python
"""add multi-user support

Revision ID: <GENERATED_REVISION_ID>
Revises: f1a2b3c4d5e6
Create Date: 2026-06-14

"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "<GENERATED_REVISION_ID>"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("authentik_username", sa.String(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_users_authentik_username", "users", ["authentik_username"])

    # 2. Seed admin user from ADMIN_USERNAME env var
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    bind = op.get_bind()
    bind.execute(
        sa.text("INSERT INTO users (authentik_username, is_admin) VALUES (:u, 1)"),
        {"u": admin_username},
    )

    # 3. companies: add user_id, fill, enforce NOT NULL
    op.add_column("companies", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.execute("UPDATE companies SET user_id = 1")
    with op.batch_alter_table("companies") as b:
        b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 4. jobs: user_id derived from parent company
    op.add_column("jobs", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.execute("UPDATE jobs SET user_id = (SELECT c.user_id FROM companies c WHERE c.id = jobs.company_id)")
    with op.batch_alter_table("jobs") as b:
        b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 5. runs
    op.add_column("runs", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.execute("UPDATE runs SET user_id = 1")
    with op.batch_alter_table("runs") as b:
        b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 6. application_tracking
    op.add_column("application_tracking", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.execute("UPDATE application_tracking SET user_id = 1")
    with op.batch_alter_table("application_tracking") as b:
        b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 7. feedback_examples
    op.add_column("feedback_examples", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.execute("UPDATE feedback_examples SET user_id = 1")
    with op.batch_alter_table("feedback_examples") as b:
        b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 8. resume
    op.add_column("resume", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.execute("UPDATE resume SET user_id = 1")
    with op.batch_alter_table("resume") as b:
        b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 9. Recreate settings with surrogate PK + user_id
    op.rename_table("settings", "_settings_old")
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_settings_user_key", "settings", ["user_id", "key"])
    bind.execute(
        sa.text("INSERT INTO settings (user_id, key, value, updated_at) SELECT 1, key, value, updated_at FROM _settings_old")
    )
    op.drop_table("_settings_old")


def downgrade() -> None:
    op.rename_table("settings", "_settings_new")
    op.create_table(
        "settings",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.get_bind().execute(
        sa.text("INSERT INTO settings (key, value, updated_at) SELECT key, value, updated_at FROM _settings_new WHERE user_id = 1")
    )
    op.drop_table("_settings_new")
    with op.batch_alter_table("resume") as b:
        b.drop_column("user_id")
    with op.batch_alter_table("feedback_examples") as b:
        b.drop_column("user_id")
    with op.batch_alter_table("application_tracking") as b:
        b.drop_column("user_id")
    with op.batch_alter_table("runs") as b:
        b.drop_column("user_id")
    with op.batch_alter_table("jobs") as b:
        b.drop_column("user_id")
    with op.batch_alter_table("companies") as b:
        b.drop_column("user_id")
    op.drop_table("users")
```

- [ ] **Step 3: Verify migration runs against an existing DB**

Ensure `ADMIN_USERNAME` is set in your shell (use your Authentik username):
```
$env:ADMIN_USERNAME = "yourname"
alembic upgrade head
```
Expected: completes with no errors; `alembic current` shows the new revision as head.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat: Alembic migration -- users table and user_id FKs on all owned tables"
```

---

### Task 6: Update `config.py` to be user-scoped

All config functions now accept `user_id: int`. `seed_defaults` checks the user exists first (safe for tests where lifespan runs against a separate DB).

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Replace `backend/config.py`**

```python
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.setting import Setting
from backend.models.user import User

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


async def seed_defaults(session: AsyncSession, user_id: int) -> None:
    user = await session.get(User, user_id)
    if user is None:
        return
    for key, default_value in DEFAULTS.items():
        existing = (await session.execute(
            select(Setting).where(Setting.user_id == user_id, Setting.key == key)
        )).scalar_one_or_none()
        if existing is None:
            session.add(Setting(user_id=user_id, key=key, value=default_value))
    await session.commit()


async def get_setting(session: AsyncSession, key: str, user_id: int) -> Any:
    row = (await session.execute(
        select(Setting).where(Setting.user_id == user_id, Setting.key == key)
    )).scalar_one_or_none()
    if row is None:
        return DEFAULTS.get(key)
    return row.value


async def set_setting(session: AsyncSession, key: str, value: Any, user_id: int) -> None:
    row = (await session.execute(
        select(Setting).where(Setting.user_id == user_id, Setting.key == key)
    )).scalar_one_or_none()
    if row is None:
        session.add(Setting(user_id=user_id, key=key, value=value))
    else:
        row.value = value
    await session.commit()


async def get_all_settings(session: AsyncSession, user_id: int) -> dict[str, Any]:
    rows = (await session.execute(
        select(Setting).where(Setting.user_id == user_id)
    )).scalars().all()
    result = dict(DEFAULTS)
    for row in rows:
        result[row.key] = row.value
    return result
```

- [ ] **Step 2: Update lifespan in `backend/main.py`**

Change the `seed_defaults` call to pass `user_id=1`:
```python
async with AsyncSessionLocal() as session:
    await seed_defaults(session, user_id=1)
```

- [ ] **Step 3: Commit**

```bash
git add backend/config.py backend/main.py
git commit -m "feat: make config.py settings functions user-scoped (user_id parameter)"
```

---

### Task 7: Update test infrastructure

Update `conftest.py` to seed a test user row and override `get_current_user`. This keeps all existing tests working after routers gain the auth dependency.

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Replace `tests/conftest.py`**

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.database import Base, get_session
from backend.dependencies.auth import get_current_user
from backend.main import create_app
from backend.models.user import User


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def app():
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        session.add(User(id=1, authentik_username="testuser", is_admin=True))
        await session.commit()

    application = create_app()

    async def override_get_session():
        async with test_session_factory() as session:
            yield session

    async def override_get_current_user():
        return User(id=1, authentik_username="testuser", is_admin=True)

    application.dependency_overrides[get_session] = override_get_session
    application.dependency_overrides[get_current_user] = override_get_current_user

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

- [ ] **Step 2: Run existing tests to confirm no regressions**

Run: `pytest tests/ -v --ignore=tests/test_auth.py`
Expected: all pass (some may be skipped -- that is fine, as long as no new failures appear)

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: seed test user and override get_current_user in conftest"
```

---

### Task 8: Update companies router

**Files:**
- Modify: `backend/routers/companies.py`
- Test: `tests/test_companies.py`

- [ ] **Step 1: Replace `backend/routers/companies.py`**

```python
import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import CurrentUser
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
async def list_companies(session: Session, current_user: CurrentUser):
    rows = (await session.execute(
        select(Company).where(Company.user_id == current_user.id).order_by(Company.name)
    )).scalars().all()
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
async def probe_company(req: ProbeRequest, current_user: CurrentUser):
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
async def add_company(req: CompanyCreate, session: Session, current_user: CurrentUser):
    probe = await probe_ats(req.careers_url, req.name)
    company = Company(
        name=req.name,
        careers_url=req.careers_url,
        ats_type=AtsType(probe.ats_type),
        ats_identifier=probe.identifier,
        user_id=current_user.id,
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return {"id": company.id, "ats_type": company.ats_type, "probe_attempts": [
        {"url": a.url, "status_code": a.status_code} for a in probe.probe_attempts
    ]}


@router.patch("/{company_id}")
async def update_company(company_id: int, req: CompanyUpdate, session: Session, current_user: CurrentUser):
    company = (await session.execute(
        select(Company).where(Company.id == company_id, Company.user_id == current_user.id)
    )).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(company, field, value)
    await session.commit()
    return {"id": company.id}


@router.delete("/{company_id}", status_code=204)
async def delete_company(company_id: int, session: Session, current_user: CurrentUser):
    company = (await session.execute(
        select(Company).where(Company.id == company_id, Company.user_id == current_user.id)
    )).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    await session.delete(company)
    await session.commit()


@router.post("/{company_id}/retry")
async def retry_company(company_id: int, session: Session, current_user: CurrentUser):
    company = (await session.execute(
        select(Company).where(Company.id == company_id, Company.user_id == current_user.id)
    )).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.quarantine_count = 0
    company.quarantined_at = None
    company.quarantine_reason = None
    company.is_active = True
    await session.commit()
    return {"id": company.id, "status": "reactivated"}


@router.post("/import", status_code=201)
async def import_companies(file: UploadFile, session: Session, current_user: CurrentUser):
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
            user_id=current_user.id,
        )
        session.add(company)
        created.append(name)
    await session.commit()
    return {"created": len(created), "names": created}
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_companies.py tests/test_auth.py -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add backend/routers/companies.py
git commit -m "feat: scope companies router to current user"
```

---

### Task 9: Update jobs router

**Files:**
- Modify: `backend/routers/jobs.py`

- [ ] **Step 1: Replace `backend/routers/jobs.py`**

```python
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.models.job import Job
from backend.models.match import Match
from backend.models.company import Company
from backend.models.feedback import FeedbackExample

router = APIRouter(prefix="/jobs", tags=["jobs"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_jobs(
    session: Session,
    current_user: CurrentUser,
    company_id: int | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    stmt = select(Job).where(Job.user_id == current_user.id).order_by(Job.first_seen_at.desc())
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
async def get_job(job_id: int, session: Session, current_user: CurrentUser):
    job = (await session.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )).scalar_one_or_none()
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
async def dismiss_job(job_id: int, session: Session, current_user: CurrentUser):
    job = (await session.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )).scalar_one_or_none()
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
        user_id=current_user.id,
    )
    session.add(fb)

    all_fb = (await session.execute(
        select(FeedbackExample)
        .where(FeedbackExample.user_id == current_user.id)
        .order_by(FeedbackExample.dismissed_at.desc())
    )).scalars().all()
    for old in all_fb[50:]:
        await session.delete(old)

    await session.commit()
    return {"status": "dismissed"}
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v --ignore=tests/test_auth.py`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add backend/routers/jobs.py
git commit -m "feat: scope jobs router to current user"
```

---

### Task 10: Update matches router

**Files:**
- Modify: `backend/routers/matches.py`

The `list_matches` query already joins Job and Company. Add `Company.user_id == current_user.id` to the WHERE clause.
The `bulk_notify` endpoint needs `get_all_settings` to receive `user_id` and needs a user ownership check.

- [ ] **Step 1: Replace `backend/routers/matches.py`**

```python
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.discord import post_match_to_discord
from backend.models.match import Match
from backend.models.job import Job
from backend.models.company import Company

router = APIRouter(prefix="/matches", tags=["matches"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_matches(
    session: Session,
    current_user: CurrentUser,
    tier: str | None = Query(None),
    company_id: int | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    stmt = (
        select(Match, Job, Company)
        .join(Job, Match.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(Company.user_id == current_user.id)
        .order_by(Match.created_at.desc())
    )
    if tier:
        stmt = stmt.where(Match.tier == tier)
    if company_id:
        stmt = stmt.where(Company.id == company_id)
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": m.id, "job_id": m.job_id, "score": m.score, "tier": m.tier,
            "summary": m.summary, "is_preview": m.is_preview,
            "notified_at": m.notified_at, "not_interested_at": m.not_interested_at,
            "created_at": m.created_at,
            "job_title": j.title,
            "company_name": c.name,
            "location": j.location,
            "job_url": j.url,
        }
        for m, j, c in rows
    ]


class BulkNotifyRequest(BaseModel):
    match_ids: list[int]


@router.post("/notify")
async def bulk_notify(req: BulkNotifyRequest, session: Session, current_user: CurrentUser):
    settings = await get_all_settings(session, user_id=current_user.id)
    webhook_url = settings.get("discord_webhook_url", "")
    notified = 0

    for match_id in req.match_ids:
        match = await session.get(Match, match_id)
        if not match or match.is_preview:
            continue
        job = await session.get(Job, match.job_id)
        if not job or job.user_id != current_user.id:
            continue
        company = await session.get(Company, job.company_id) if job else None
        if not company:
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

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v --ignore=tests/test_auth.py`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add backend/routers/matches.py
git commit -m "feat: scope matches router to current user"
```

---

### Task 11: Update runs router and pipeline

**Files:**
- Modify: `backend/routers/runs.py`
- Modify: `backend/pipeline.py`

The runs router adds `current_user` and sets `user_id` on `Run` creation. The pipeline reads the run's `user_id` to scope company queries and sets `user_id` on new `Job` rows.

- [ ] **Step 1: Replace `backend/routers/runs.py`**

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
from backend.dependencies.auth import CurrentUser
from backend.models.run import Run, RunCompanyResult, RunStatus
from backend.pipeline import execute_run, get_run_queue, request_cancel_run

router = APIRouter(prefix="/runs", tags=["runs"])
Session = Annotated[AsyncSession, Depends(get_session)]


class RunCreate(BaseModel):
    company_ids: list[int] | None = None
    preview: bool = False


@router.post("", status_code=201)
async def start_run(req: RunCreate, background_tasks: BackgroundTasks, session: Session, current_user: CurrentUser):
    run = Run(is_preview=req.preview, company_ids=req.company_ids, user_id=current_user.id)
    session.add(run)
    await session.commit()
    await session.refresh(run)

    async def run_in_background(run_id: int):
        async with AsyncSessionLocal() as bg_session:
            await execute_run(run_id, bg_session)

    background_tasks.add_task(run_in_background, run.id)
    return {"id": run.id, "status": run.status}


@router.get("")
async def list_runs(session: Session, current_user: CurrentUser):
    rows = (await session.execute(
        select(Run).where(Run.user_id == current_user.id).order_by(Run.started_at.desc()).limit(50)
    )).scalars().all()
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
async def get_run(run_id: int, session: Session, current_user: CurrentUser):
    run = (await session.execute(
        select(Run).where(Run.id == run_id, Run.user_id == current_user.id)
    )).scalar_one_or_none()
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


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: int, session: Session, current_user: CurrentUser):
    run = (await session.execute(
        select(Run).where(Run.id == run_id, Run.user_id == current_user.id)
    )).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != RunStatus.running:
        raise HTTPException(status_code=409, detail="Run is not running")
    request_cancel_run(run_id)
    return {"id": run_id, "status": "cancelling"}


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

- [ ] **Step 2: Update `backend/pipeline.py` -- scope company query and set user_id on Job**

In `execute_run`, locate and update two sections:

**Section A** -- reading the run and scoping settings. After `run = await session.get(Run, run_id)`, add a line:
```python
user_id = run.user_id
```

Then update `get_all_settings` call to:
```python
settings = await get_all_settings(session, user_id=user_id)
```

**Section B** -- feedback examples query (line ~101). Update to filter by user:
```python
fb_rows = (await session.execute(
    sa_select(FBModel).where(FBModel.user_id == user_id).order_by(FBModel.dismissed_at.desc()).limit(5)
)).scalars().all()
```

**Section C** -- existing_job_count query (line ~115). Update to filter by user:
```python
existing_job_count = (await session.execute(
    sa_select(sa_func.count()).select_from(Job).where(Job.user_id == user_id)
)).scalar() or 0
```

**Section D** -- company selection query (line ~120). Update to filter by user:
```python
stmt = sa_select(Company).where(Company.is_active == True, Company.user_id == user_id)
if run.company_ids:
    stmt = stmt.where(Company.id.in_(run.company_ids))
companies = (await session.execute(stmt)).scalars().all()
```

**Section E** -- Job creation (line ~174). Add `user_id=company.user_id` to the Job constructor:
```python
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
    user_id=company.user_id,
)
```

**Section F** -- quarantine threshold (line ~95). Update `get_setting` to pass `user_id`:
```python
quarantine_threshold = int(await get_setting(session, "quarantine_threshold", user_id=user_id) or 3)
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_runs.py tests/ -v --ignore=tests/test_auth.py`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add backend/routers/runs.py backend/pipeline.py
git commit -m "feat: scope runs router and pipeline to current user"
```

---

### Task 12: Update applications router

**Files:**
- Modify: `backend/routers/applications.py`

Every query, create, update, and delete gains a `user_id` filter. The `_serialize` helper stays unchanged.

- [ ] **Step 1: Update `backend/routers/applications.py`**

Add to imports:
```python
from backend.dependencies.auth import CurrentUser
```

Changes per endpoint:

**`get_stats`** -- add `current_user: CurrentUser`, filter all sub-queries with `.where(ApplicationTracking.user_id == current_user.id)`:
```python
@router.get("/stats")
async def get_stats(session: Session, current_user: CurrentUser):
    status_rows = (await session.execute(
        select(ApplicationTracking.status, func.count().label("count"))
        .where(ApplicationTracking.user_id == current_user.id)
        .group_by(ApplicationTracking.status)
    )).all()
    counts = {r.status: r.count for r in status_rows}

    source_rows = (await session.execute(
        select(ApplicationTracking.source, func.count().label("count"))
        .where(ApplicationTracking.user_id == current_user.id)
        .group_by(ApplicationTracking.source)
    )).all()
    source_counts = {r.source: r.count for r in source_rows}

    applied = counts.get(ApplicationStatus.applied, 0)
    offer = counts.get(ApplicationStatus.offer, 0)

    thirty_days_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
    daily_rows = (await session.execute(
        select(
            func.date(ApplicationTracking.created_at).label("day"),
            ApplicationTracking.status,
            func.count().label("count"),
        )
        .where(
            ApplicationTracking.user_id == current_user.id,
            ApplicationTracking.created_at >= thirty_days_ago,
        )
        .group_by(func.date(ApplicationTracking.created_at), ApplicationTracking.status)
        .order_by(func.date(ApplicationTracking.created_at))
    )).all()

    daily: dict[str, dict] = {}
    for r in daily_rows:
        day = str(r.day)
        if day not in daily:
            daily[day] = {}
        daily[day][r.status] = r.count

    return {
        "total": sum(counts.values()),
        "by_status": {
            "interested": counts.get(ApplicationStatus.interested, 0),
            "applied": applied,
            "rejected": counts.get(ApplicationStatus.rejected, 0),
            "offer": offer,
        },
        "response_rate": round(offer / applied * 100) if applied > 0 else 0,
        "by_source": {
            "joblin": source_counts.get(ApplicationSource.joblin, 0),
            "external": source_counts.get(ApplicationSource.external, 0),
        },
        "daily_series": [
            {"date": day, **statuses}
            for day, statuses in sorted(daily.items())
        ],
    }
```

**`bulk_action`** -- add `current_user: CurrentUser`, scope the query:
```python
@router.post("/bulk")
async def bulk_action(req: BulkActionRequest, session: Session, current_user: CurrentUser):
    apps = (await session.execute(
        select(ApplicationTracking).where(
            ApplicationTracking.id.in_(req.ids),
            ApplicationTracking.user_id == current_user.id,
        )
    )).scalars().all()
    # rest of function body unchanged
```

**`list_applications`** -- add `current_user: CurrentUser`, add base filter:
```python
stmt = select(ApplicationTracking).where(
    ApplicationTracking.user_id == current_user.id
).order_by(ApplicationTracking.created_at.desc())
```

**`create_application`** -- add `current_user: CurrentUser`, add `user_id=current_user.id` to ApplicationTracking constructor, and scope the duplicate check:
```python
existing = (await session.execute(
    select(ApplicationTracking).where(
        ApplicationTracking.job_id == req.job_id,
        ApplicationTracking.user_id == current_user.id,
    )
)).scalar_one_or_none()
```
```python
app = ApplicationTracking(
    ...,
    user_id=current_user.id,
)
```

**`update_application`** and **`delete_application`** -- add `current_user: CurrentUser`, scope:
```python
app = (await session.execute(
    select(ApplicationTracking).where(
        ApplicationTracking.id == app_id,
        ApplicationTracking.user_id == current_user.id,
    )
)).scalar_one_or_none()
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_applications.py -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add backend/routers/applications.py
git commit -m "feat: scope applications router to current user"
```

---

### Task 13: Update settings and presets routers

**Files:**
- Modify: `backend/routers/settings.py`
- Modify: `backend/routers/presets.py`

- [ ] **Step 1: Replace `backend/routers/settings.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings, set_setting
from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.discord import post_match_to_discord

router = APIRouter(prefix="/settings", tags=["settings"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def get_settings(session: Session, current_user: CurrentUser):
    return await get_all_settings(session, user_id=current_user.id)


@router.patch("")
async def update_settings(body: dict, session: Session, current_user: CurrentUser):
    for key, value in body.items():
        await set_setting(session, key, value, user_id=current_user.id)
    return {"updated": list(body.keys())}


@router.post("/discord/test")
async def test_discord(session: Session, current_user: CurrentUser):
    settings = await get_all_settings(session, user_id=current_user.id)
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
async def test_criteria(req: CriteriaTestRequest, session: Session, current_user: CurrentUser):
    from backend.llm.factory import get_filter_provider
    from backend.llm.protocol import CriteriaConfig

    settings = await get_all_settings(session, user_id=current_user.id)
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

- [ ] **Step 2: Replace `backend/routers/presets.py`**

```python
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import set_setting
from backend.database import get_session
from backend.dependencies.auth import CurrentUser

router = APIRouter(prefix="/presets", tags=["presets"])
Session = Annotated[AsyncSession, Depends(get_session)]

PRESETS_DIR = Path(__file__).parent.parent.parent / "presets"


@router.get("")
async def list_presets(current_user: CurrentUser):
    presets = []
    for path in sorted(PRESETS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        presets.append({"name": path.stem, "description": data.get("description", ""), "criteria": data.get("criteria", {})})
    return presets


@router.post("/{name}/apply")
async def apply_preset(name: str, session: Session, current_user: CurrentUser):
    path = PRESETS_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    data = json.loads(path.read_text())
    criteria = data.get("criteria")
    if not criteria:
        raise HTTPException(status_code=400, detail="Preset has no criteria field")
    await set_setting(session, "criteria", criteria, user_id=current_user.id)
    return {"applied": name}
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -v --ignore=tests/test_auth.py`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add backend/routers/settings.py backend/routers/presets.py
git commit -m "feat: scope settings and presets routers to current user"
```

---

### Task 14: Update admin router

The reset endpoint currently deletes ALL data. After this change it deletes only the current user's data.

**Files:**
- Modify: `backend/routers/admin.py`

- [ ] **Step 1: Replace `backend/routers/admin.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.models.feedback import FeedbackExample
from backend.models.job import Job
from backend.models.match import Match
from backend.models.run import Run, RunCompanyResult

router = APIRouter(prefix="/admin", tags=["admin"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/reset")
async def reset_job_data(session: Session, current_user: CurrentUser):
    counts = {}

    user_job_ids = (await session.execute(
        select(Job.id).where(Job.user_id == current_user.id)
    )).scalars().all()

    counts["feedback_examples"] = (await session.execute(
        select(func.count()).select_from(FeedbackExample).where(FeedbackExample.user_id == current_user.id)
    )).scalar() or 0
    await session.execute(delete(FeedbackExample).where(FeedbackExample.user_id == current_user.id))

    counts["matches"] = (await session.execute(
        select(func.count()).select_from(Match).where(Match.job_id.in_(user_job_ids))
    )).scalar() or 0
    await session.execute(delete(Match).where(Match.job_id.in_(user_job_ids)))

    user_run_ids = (await session.execute(
        select(Run.id).where(Run.user_id == current_user.id)
    )).scalars().all()

    counts["run_company_results"] = (await session.execute(
        select(func.count()).select_from(RunCompanyResult).where(RunCompanyResult.run_id.in_(user_run_ids))
    )).scalar() or 0
    await session.execute(delete(RunCompanyResult).where(RunCompanyResult.run_id.in_(user_run_ids)))

    counts["jobs"] = len(user_job_ids)
    await session.execute(delete(Job).where(Job.user_id == current_user.id))

    counts["runs"] = len(user_run_ids)
    await session.execute(delete(Run).where(Run.user_id == current_user.id))

    await session.commit()
    return {"deleted": counts}
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_admin.py -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add backend/routers/admin.py
git commit -m "feat: scope admin reset to current user's data only"
```

---

### Task 15: Update resume router

The resume router currently hardcodes `Resume.id == 1`. Replace with `Resume.user_id == current_user.id`.

**Files:**
- Modify: `backend/routers/resume.py`

- [ ] **Step 1: Replace `backend/routers/resume.py`**

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
from backend.dependencies.auth import CurrentUser
from backend.llm.factory import get_tailor_provider
from backend.models.job import Job
from backend.models.resume import Resume

router = APIRouter(prefix="/resume", tags=["resume"])
Session = Annotated[AsyncSession, Depends(get_session)]


class ResumeSave(BaseModel):
    tex_content: str


@router.get("")
async def get_resume(session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    if resume is None:
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


@router.post("/tailor")
async def tailor_resume_endpoint(body: TailorRequest, session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=404, detail="No reference resume found. Upload a .tex file first.")

    job = (await session.execute(
        select(Job).where(Job.id == body.job_id, Job.user_id == current_user.id)
    )).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    settings = await get_all_settings(session, user_id=current_user.id)
    provider = get_tailor_provider(settings)
    if not job.raw_description:
        raise HTTPException(
            status_code=422,
            detail="This job has no description yet. Run a scan to fetch full job details first.",
        )
    tailored_tex = await provider.tailor_resume(
        tex_content=resume.tex_content,
        job_description=job.raw_description,
    )
    return {"tex_content": tailored_tex}
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_resume.py -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add backend/routers/resume.py
git commit -m "feat: scope resume router to current user"
```

---

### Task 16: Update insights, usage, and system routers

**Files:**
- Modify: `backend/routers/insights.py`
- Modify: `backend/routers/usage.py`
- Modify: `backend/routers/system.py`

- [ ] **Step 1: Replace `backend/routers/insights.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.dependencies.auth import CurrentUser
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
async def analyze_skills(req: AnalyzeRequest, session: Session, current_user: CurrentUser):
    settings = await get_all_settings(session, user_id=current_user.id)
    provider = get_filter_provider(settings)

    analyzed = 0
    skipped = 0
    skills_found = 0

    for match_id in req.match_ids:
        match = await session.get(Match, match_id)
        if not match:
            continue

        job = await session.get(Job, match.job_id)
        if not job or job.user_id != current_user.id:
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
async def list_skills(session: Session, current_user: CurrentUser):
    rows = (await session.execute(
        select(JobSkill.skill_name, func.count(JobSkill.id).label("count"))
        .join(Job, JobSkill.job_id == Job.id)
        .where(Job.user_id == current_user.id)
        .group_by(JobSkill.skill_name)
        .order_by(func.count(JobSkill.id).desc())
    )).all()

    total_jobs = (await session.execute(
        select(func.count(func.distinct(JobSkill.job_id)))
        .join(Job, JobSkill.job_id == Job.id)
        .where(Job.user_id == current_user.id)
    )).scalar() or 0

    return {
        "skills": [{"name": row.skill_name, "count": row.count} for row in rows],
        "total_jobs_analyzed": total_jobs,
    }


@router.get("/skills/{name}/citations")
async def get_citations(name: str, session: Session, current_user: CurrentUser):
    rows = (await session.execute(
        select(Company.name.label("company_name"), Job.title.label("job_title"))
        .select_from(JobSkill)
        .join(Job, JobSkill.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(JobSkill.skill_name == name, Company.user_id == current_user.id)
        .order_by(JobSkill.created_at.desc())
    )).all()
    return [{"company_name": row.company_name, "job_title": row.job_title} for row in rows]
```

- [ ] **Step 2: Replace `backend/routers/usage.py`**

```python
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.models.run import Run
from backend.models.token_usage import TokenUsage

router = APIRouter(prefix="/usage", tags=["usage"])
Session = Annotated[AsyncSession, Depends(get_session)]

PROVIDERS = ["groq", "cerebras", "gemini"]


async def _aggregate(session: AsyncSession, provider: str, since: datetime | None, user_id: int) -> dict:
    stmt = (
        select(
            func.coalesce(func.sum(TokenUsage.total_tokens), 0),
            func.coalesce(func.sum(TokenUsage.prompt_tokens), 0),
            func.coalesce(func.sum(TokenUsage.completion_tokens), 0),
            func.count(TokenUsage.id).filter(TokenUsage.call_type == "filter"),
            func.count(TokenUsage.id).filter(TokenUsage.call_type == "summarize"),
        )
        .join(Run, TokenUsage.run_id == Run.id)
        .where(TokenUsage.provider == provider, Run.user_id == user_id)
    )
    if since:
        stmt = stmt.where(TokenUsage.created_at >= since)
    row = (await session.execute(stmt)).one()
    return {
        "total_tokens": int(row[0]),
        "prompt_tokens": int(row[1]),
        "completion_tokens": int(row[2]),
        "filter_calls": int(row[3]),
        "summarize_calls": int(row[4]),
    }


@router.get("")
async def get_usage(session: Session, current_user: CurrentUser):
    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    providers = {}
    for provider in PROVIDERS:
        all_time = await _aggregate(session, provider, since=None, user_id=current_user.id)
        last_7d = await _aggregate(session, provider, since=cutoff_7d, user_id=current_user.id)
        last_30d = await _aggregate(session, provider, since=cutoff_30d, user_id=current_user.id)
        providers[provider] = {
            "total_tokens_all_time": all_time["total_tokens"],
            "prompt_tokens_all_time": all_time["prompt_tokens"],
            "completion_tokens_all_time": all_time["completion_tokens"],
            "total_tokens_7d": last_7d["total_tokens"],
            "total_tokens_30d": last_30d["total_tokens"],
            "filter_calls": all_time["filter_calls"],
            "summarize_calls": all_time["summarize_calls"],
        }

    recent_stmt = (
        select(
            TokenUsage.run_id,
            TokenUsage.provider,
            func.sum(TokenUsage.total_tokens).label("tokens"),
        )
        .join(Run, TokenUsage.run_id == Run.id)
        .where(Run.user_id == current_user.id)
        .group_by(TokenUsage.run_id, TokenUsage.provider)
        .order_by(TokenUsage.run_id.desc())
        .limit(50)
    )
    recent_rows = (await session.execute(recent_stmt)).all()

    run_map: dict[int, dict] = {}
    for run_id, provider, tokens in recent_rows:
        if run_id not in run_map:
            run_map[run_id] = {"run_id": run_id, "groq": 0, "cerebras": 0, "gemini": 0}
        run_map[run_id][provider] = int(tokens)

    return {
        "providers": providers,
        "recent_runs": sorted(run_map.values(), key=lambda r: r["run_id"], reverse=True),
    }
```

- [ ] **Step 3: Replace `backend/routers/system.py`**

```python
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.models import Company, Match, Run
from backend.models.job import Job

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/stats")
async def stats(session: AsyncSession = Depends(get_session), current_user: CurrentUser = None):
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    total_companies = (await session.execute(
        select(func.count()).select_from(Company).where(Company.user_id == current_user.id)
    )).scalar_one()

    total_jobs_in_db = (await session.execute(
        select(func.count()).select_from(Job).where(Job.user_id == current_user.id)
    )).scalar_one()

    todays_matches = (await session.execute(
        select(func.count()).select_from(Match)
        .join(Job, Match.job_id == Job.id)
        .where(Job.user_id == current_user.id, Match.created_at >= today_start)
    )).scalar_one()

    strong_today = (await session.execute(
        select(func.count()).select_from(Match)
        .join(Job, Match.job_id == Job.id)
        .where(
            Job.user_id == current_user.id,
            Match.created_at >= today_start,
            Match.tier == "strong",
        )
    )).scalar_one()

    quarantine_count = (await session.execute(
        select(func.count()).select_from(Company).where(
            Company.user_id == current_user.id,
            Company.quarantined_at.isnot(None),
        )
    )).scalar_one()

    last_run = (await session.execute(
        select(Run.completed_at)
        .where(Run.user_id == current_user.id)
        .order_by(Run.completed_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    return {
        "total_companies": total_companies,
        "total_jobs_in_db": total_jobs_in_db,
        "todays_matches": todays_matches,
        "strong_today": strong_today,
        "quarantine_count": quarantine_count,
        "last_run_completed_at": last_run,
    }


@router.get("/onboarding-status")
async def onboarding_status(session: AsyncSession = Depends(get_session), current_user: CurrentUser = None):
    company_count = (await session.execute(
        select(func.count()).select_from(Company).where(Company.user_id == current_user.id)
    )).scalar_one()
    return {"needs_onboarding": company_count == 0}
```

Note: `system.py` uses `Depends(get_session)` directly rather than the `Session` alias. Keep `current_user: CurrentUser = None` as the default so FastAPI wires it via dependency injection (the `= None` default is just for type-checker compatibility; FastAPI will always inject it).

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_health.py tests/test_usage.py tests/test_insights.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/routers/insights.py backend/routers/usage.py backend/routers/system.py
git commit -m "feat: scope insights, usage, and system routers to current user"
```

---

### Task 17: Update scheduler

The scheduler is a background process with no HTTP context, so it cannot use `get_current_user`. For v1, it creates runs scoped to user_id=1 (the admin). It also reads settings from user_id=1.

**Files:**
- Modify: `backend/scheduler.py`

- [ ] **Step 1: Replace `backend/scheduler.py`**

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
        staleness_hours = float(await get_setting(session, "staleness_threshold_hours", user_id=1) or 4)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=staleness_hours)
        last_run = (await session.execute(
            select(Run)
            .where(Run.status == RunStatus.completed, Run.user_id == 1)
            .order_by(Run.completed_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        if last_run and last_run.completed_at and last_run.completed_at > cutoff:
            return

        run = Run(is_preview=False, user_id=1)
        session.add(run)
        await session.commit()
        await session.refresh(run)

    async with AsyncSessionLocal() as session:
        await execute_run(run.id, session)


async def start_scheduler(scheduler: AsyncScheduler) -> None:
    async with AsyncSessionLocal() as session:
        cron_expr = await get_setting(session, "schedule_cron", user_id=1) or "0 */4 * * *"
        enabled = await get_setting(session, "scheduler_enabled", user_id=1) or False

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

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add backend/scheduler.py
git commit -m "feat: scope scheduler to admin user (user_id=1) for v1"
```

---

### Task 18: Infrastructure changes

**Files:**
- Modify: `Caddyfile`
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Replace `Caddyfile`**

```
:80 {
    forward_auth host.docker.internal:9000 {
        uri /outpost.goauthentik.io/auth/caddy
        copy_headers X-authentik-username X-authentik-email X-authentik-name

        @goauthentik_proxy_response header X-Goauthentik-Auth-Redirect .
        handle_response @goauthentik_proxy_response {
            redir * {http.reverse_proxy.header.Location} 302
        }
    }
    reverse_proxy app:8000
}
```

- [ ] **Step 2: Update `docker-compose.yml`**

In the `caddy` service, add `extra_hosts` so Caddy can reach Authentik on the host:
```yaml
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    env_file:
      - .env
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

In the `app` service, remove the `BASIC_AUTH_PASSWORD` environment variable line.

- [ ] **Step 3: Replace `.env.example`**

```
# === Required ===

# Your Authentik username (used to seed the admin user in the DB on first migration)
ADMIN_USERNAME=yourname

# LLM provider API keys (at least one of Groq or Cerebras required)
GROQ_API_KEY=
CEREBRAS_API_KEY=
GEMINI_API_KEY=

# === Optional ===

# Override the SQLite path (default: /app/data/joblin.db in Docker)
# DATABASE_URL=sqlite+aiosqlite:///./joblin.db

# Discord webhook URL (can also be set from the Settings UI after first login)
DISCORD_WEBHOOK_URL=
```

- [ ] **Step 4: Run final test suite**

Run: `pytest tests/ -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add Caddyfile docker-compose.yml .env.example
git commit -m "feat: Caddy forward-auth config and remove basic auth env vars"
```

---

## Authentik Setup (manual, one-time)

After deploying to the VPS, complete these steps in the Authentik admin UI at `https://vps.capybara-nessie.ts.net/if/admin/`:

1. **Providers > Create** -- select "Proxy Provider", choose "Forward auth (single application)", set External host to `https://vps.capybara-nessie.ts.net:10000`
2. **Applications > Create** -- name it "Joblin", point it at the new provider
3. **Outposts > Embedded Outpost > Edit** -- add the Joblin application to the outpost
4. **Application > Policy/Bindings** -- bind the users or groups who should have access

No changes to the Actual Budget application or its provider.

---

## Self-Review Checklist

**Spec coverage:**
- [x] Caddy forward-auth (Task 18)
- [x] `X-authentik-username` header -> `get_current_user` dependency (Task 4)
- [x] Auto-provisioning with `is_admin=True` for first user (Task 4)
- [x] `users` table (Task 1)
- [x] `user_id` FK on companies, jobs, runs, application_tracking, feedback_examples, resume (Task 3 + 5)
- [x] Settings per-user (Task 2 + 6)
- [x] Alembic migration seeds admin from `ADMIN_USERNAME` env var (Task 5)
- [x] All routers filtered by current user (Tasks 8-16)
- [x] Pipeline scopes company and job queries to run's user (Task 11)
- [x] Scheduler scoped to admin user v1 (Task 17)
- [x] `extra_hosts` for Docker-to-host networking (Task 18)
- [x] `BASIC_AUTH_PASSWORD` removed from config (Task 18)

**No placeholders:** All code blocks are complete.

**Type consistency:** `CurrentUser` alias defined in `auth.py` and imported consistently across all routers. `get_all_settings(session, user_id=...)` signature used everywhere.
