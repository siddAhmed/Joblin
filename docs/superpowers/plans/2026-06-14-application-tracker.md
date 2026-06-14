# Application Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dedicated Applications page for tracking jobs (Joblin-discovered and external) with a stats dashboard, inline status management, and bulk selection on both the Matches and Applications pages.

**Architecture:** New `application_tracking` SQLAlchemy model with an optional `job_id` FK (null for external jobs). A new FastAPI router handles all CRUD, bulk, and stats endpoints. The frontend gets a new Applications page plus additions to the Matches page (View JD / Interested / Applied buttons and bulk tracking).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, React 19, TanStack React Query, Tailwind CSS, TypeScript.

---

## File map

| Action | Path |
|---|---|
| Create | `backend/models/application.py` |
| Modify | `backend/models/__init__.py` |
| Create | `backend/alembic/versions/<rev>_add_application_tracking.py` |
| Create | `backend/routers/applications.py` |
| Modify | `backend/main.py` |
| Create | `tests/test_applications.py` |
| Create | `frontend/src/api/applications.ts` |
| Create | `frontend/src/pages/Applications.tsx` |
| Modify | `frontend/src/App.tsx` |
| Modify | `frontend/src/components/Sidebar.tsx` |
| Modify | `frontend/src/pages/Matches.tsx` |

---

## Task 1: ApplicationTracking model + migration

**Files:**
- Create: `backend/models/application.py`
- Modify: `backend/models/__init__.py`
- Create: `backend/alembic/versions/<rev>_add_application_tracking.py`
- Create: `tests/test_applications.py`

- [ ] **Step 1: Write the first failing test**

Create `tests/test_applications.py`:

```python
async def test_list_applications_empty(client):
    response = await client.get("/api/applications")
    assert response.status_code == 200
    assert response.json() == []
```

- [ ] **Step 2: Run to confirm it fails**

```
pytest tests/test_applications.py::test_list_applications_empty -v
```
Expected: FAIL (404 — router not registered yet)

- [ ] **Step 3: Create the model**

Create `backend/models/application.py`:

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
```

- [ ] **Step 4: Export the new model**

In `backend/models/__init__.py`, add:

```python
from backend.models.application import ApplicationTracking, ApplicationStatus, ApplicationSource
```

Add `"ApplicationTracking", "ApplicationStatus", "ApplicationSource"` to `__all__`.

- [ ] **Step 5: Create the migration**

Run:
```
alembic revision -m "add_application_tracking"
```

Open the generated file in `backend/alembic/versions/`. Set `down_revision = "a1b2c3d4e5f6"` (current HEAD). Fill the body:

```python
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table(
        "application_tracking",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("job_title", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("applied_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_application_job_id", "application_tracking", ["job_id"])
    op.create_index("ix_application_tracking_status", "application_tracking", ["status"])

def downgrade() -> None:
    op.drop_index("ix_application_tracking_status", "application_tracking")
    op.drop_constraint("uq_application_job_id", "application_tracking", type_="unique")
    op.drop_table("application_tracking")
```

Run: `alembic upgrade head`

- [ ] **Step 6: Create the stub router and register it**

Create `backend/routers/applications.py`:

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_session
from backend.models.application import ApplicationTracking

router = APIRouter(prefix="/applications", tags=["applications"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_applications(session: Session):
    rows = (await session.execute(select(ApplicationTracking))).scalars().all()
    return [_serialize(r) for r in rows]


def _serialize(app: ApplicationTracking) -> dict:
    return {
        "id": app.id,
        "job_id": app.job_id,
        "company_name": app.company_name,
        "job_title": app.job_title,
        "url": app.url,
        "applied_date": app.applied_date.isoformat() if app.applied_date else None,
        "notes": app.notes,
        "status": app.status,
        "source": app.source,
        "score": app.score,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "updated_at": app.updated_at.isoformat() if app.updated_at else None,
    }
```

In `backend/main.py`, add:
```python
from backend.routers.applications import router as applications_router
```
Then inside `create_app()`, add:
```python
app.include_router(applications_router, prefix="/api")
```

- [ ] **Step 7: Run the test — expect PASS**

```
pytest tests/test_applications.py::test_list_applications_empty -v
```
Expected: PASS

- [ ] **Step 8: Commit**

```
git add backend/models/application.py backend/models/__init__.py backend/alembic/versions/ backend/routers/applications.py backend/main.py tests/test_applications.py
git commit -m "feat: ApplicationTracking model, migration, and stub router"
```

---

## Task 2: Full applications router

**Files:**
- Modify: `backend/routers/applications.py`
- Modify: `tests/test_applications.py`

- [ ] **Step 1: Add all remaining tests**

Append to `tests/test_applications.py`:

```python
# ── create ─────────────────────────────────────────────────────────────

async def test_create_external_application(client):
    resp = await client.post("/api/applications", json={
        "company_name": "Acme",
        "job_title": "Engineer",
        "status": "applied",
        "source": "external",
        "url": "https://acme.com/jobs/1",
        "applied_date": "2026-06-14",
        "notes": "Found on HN",
    })
    assert resp.status_code == 201
    d = resp.json()
    assert d["company_name"] == "Acme"
    assert d["status"] == "applied"
    assert d["source"] == "external"
    assert d["job_id"] is None
    assert d["applied_date"] == "2026-06-14"


async def test_create_joblin_application_upserts(client):
    payload = {
        "job_id": 99,
        "company_name": "Stripe",
        "job_title": "SWE",
        "status": "interested",
        "source": "joblin",
    }
    r1 = await client.post("/api/applications", json=payload)
    assert r1.status_code == 201
    assert r1.json()["status"] == "interested"

    r2 = await client.post("/api/applications", json={**payload, "status": "applied"})
    assert r2.status_code == 201
    assert r2.json()["id"] == r1.json()["id"]
    assert r2.json()["status"] == "applied"

    list_resp = await client.get("/api/applications")
    assert len(list_resp.json()) == 1


# ── list filters ────────────────────────────────────────────────────────

async def test_list_filter_by_status(client):
    await client.post("/api/applications", json={"company_name": "A", "job_title": "E", "status": "interested", "source": "external"})
    await client.post("/api/applications", json={"company_name": "B", "job_title": "E", "status": "applied", "source": "external"})
    resp = await client.get("/api/applications?status=interested")
    assert len(resp.json()) == 1
    assert resp.json()[0]["company_name"] == "A"


async def test_list_search(client):
    await client.post("/api/applications", json={"company_name": "Stripe", "job_title": "SWE", "status": "applied", "source": "external"})
    await client.post("/api/applications", json={"company_name": "Linear", "job_title": "Designer", "status": "applied", "source": "external"})
    resp = await client.get("/api/applications?search=stripe")
    assert len(resp.json()) == 1
    assert resp.json()[0]["company_name"] == "Stripe"


# ── update ──────────────────────────────────────────────────────────────

async def test_update_application(client):
    create = await client.post("/api/applications", json={"company_name": "X", "job_title": "Y", "status": "interested", "source": "external"})
    app_id = create.json()["id"]
    resp = await client.patch(f"/api/applications/{app_id}", json={"status": "applied", "notes": "Submitted"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"
    assert resp.json()["notes"] == "Submitted"


async def test_update_not_found(client):
    resp = await client.patch("/api/applications/9999", json={"status": "applied"})
    assert resp.status_code == 404


# ── delete ──────────────────────────────────────────────────────────────

async def test_delete_application(client):
    create = await client.post("/api/applications", json={"company_name": "X", "job_title": "Y", "status": "interested", "source": "external"})
    app_id = create.json()["id"]
    assert (await client.delete(f"/api/applications/{app_id}")).status_code == 204
    assert (await client.get("/api/applications")).json() == []


async def test_delete_not_found(client):
    assert (await client.delete("/api/applications/9999")).status_code == 404


# ── bulk ────────────────────────────────────────────────────────────────

async def test_bulk_status_change(client):
    r1 = await client.post("/api/applications", json={"company_name": "A", "job_title": "E", "status": "interested", "source": "external"})
    r2 = await client.post("/api/applications", json={"company_name": "B", "job_title": "E", "status": "interested", "source": "external"})
    ids = [r1.json()["id"], r2.json()["id"]]
    resp = await client.post("/api/applications/bulk", json={"ids": ids, "action": "status_change", "status": "applied"})
    assert resp.json()["updated"] == 2
    assert all(a["status"] == "applied" for a in (await client.get("/api/applications")).json())


async def test_bulk_delete(client):
    r1 = await client.post("/api/applications", json={"company_name": "A", "job_title": "E", "status": "interested", "source": "external"})
    r2 = await client.post("/api/applications", json={"company_name": "B", "job_title": "E", "status": "interested", "source": "external"})
    ids = [r1.json()["id"], r2.json()["id"]]
    resp = await client.post("/api/applications/bulk", json={"ids": ids, "action": "delete"})
    assert resp.json()["deleted"] == 2
    assert (await client.get("/api/applications")).json() == []


# ── stats ────────────────────────────────────────────────────────────────

async def test_stats_empty(client):
    resp = await client.get("/api/applications/stats")
    assert resp.status_code == 200
    d = resp.json()
    assert d["total"] == 0
    assert d["response_rate"] == 0


async def test_stats_counts(client):
    for _ in range(3):
        await client.post("/api/applications", json={"company_name": "X", "job_title": "Y", "status": "applied", "source": "joblin"})
    await client.post("/api/applications", json={"company_name": "Z", "job_title": "W", "status": "offer", "source": "external"})
    d = (await client.get("/api/applications/stats")).json()
    assert d["total"] == 4
    assert d["by_status"]["applied"] == 3
    assert d["by_status"]["offer"] == 1
    assert d["response_rate"] == 33
    assert d["by_source"]["joblin"] == 3
    assert d["by_source"]["external"] == 1
```

- [ ] **Step 2: Run to confirm new tests fail**

```
pytest tests/test_applications.py -v
```
Expected: `test_list_applications_empty` PASS, all others FAIL.

- [ ] **Step 3: Replace `backend/routers/applications.py` with full implementation**

**Critical:** `/stats` and `/bulk` must be defined before `/{app_id}` — FastAPI matches routes in order and `/{app_id}` would capture the literal string "stats" first otherwise.

```python
from typing import Annotated
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_session
from backend.models.application import ApplicationSource, ApplicationStatus, ApplicationTracking

router = APIRouter(prefix="/applications", tags=["applications"])
Session = Annotated[AsyncSession, Depends(get_session)]


# /stats and /bulk MUST come before /{app_id}

@router.get("/stats")
async def get_stats(session: Session):
    status_rows = (await session.execute(
        select(ApplicationTracking.status, func.count().label("count"))
        .group_by(ApplicationTracking.status)
    )).all()
    counts = {r.status: r.count for r in status_rows}

    source_rows = (await session.execute(
        select(ApplicationTracking.source, func.count().label("count"))
        .group_by(ApplicationTracking.source)
    )).all()
    source_counts = {r.source: r.count for r in source_rows}

    applied = counts.get(ApplicationStatus.applied, 0)
    offer = counts.get(ApplicationStatus.offer, 0)

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_rows = (await session.execute(
        select(
            func.date(ApplicationTracking.created_at).label("day"),
            ApplicationTracking.status,
            func.count().label("count"),
        )
        .where(ApplicationTracking.created_at >= thirty_days_ago)
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


class BulkActionRequest(BaseModel):
    ids: list[int]
    action: str  # "status_change" or "delete"
    status: ApplicationStatus | None = None


@router.post("/bulk")
async def bulk_action(req: BulkActionRequest, session: Session):
    apps = (await session.execute(
        select(ApplicationTracking).where(ApplicationTracking.id.in_(req.ids))
    )).scalars().all()

    if req.action == "status_change":
        if req.status is None:
            raise HTTPException(status_code=400, detail="status required for status_change")
        for app in apps:
            app.status = req.status
        await session.commit()
        return {"updated": len(apps)}
    elif req.action == "delete":
        for app in apps:
            await session.delete(app)
        await session.commit()
        return {"deleted": len(apps)}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")


@router.get("")
async def list_applications(
    session: Session,
    status: str | None = Query(None),
    source: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    stmt = select(ApplicationTracking).order_by(ApplicationTracking.created_at.desc())
    if status:
        stmt = stmt.where(ApplicationTracking.status == status)
    if source:
        stmt = stmt.where(ApplicationTracking.source == source)
    if search:
        term = f"%{search}%"
        stmt = stmt.where(or_(
            ApplicationTracking.company_name.ilike(term),
            ApplicationTracking.job_title.ilike(term),
        ))
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return [_serialize(r) for r in rows]


class CreateApplicationRequest(BaseModel):
    job_id: int | None = None
    company_name: str
    job_title: str
    url: str | None = None
    applied_date: date | None = None
    notes: str | None = None
    status: ApplicationStatus
    source: ApplicationSource
    score: float | None = None


@router.post("", status_code=201)
async def create_application(req: CreateApplicationRequest, session: Session):
    if req.job_id is not None:
        existing = (await session.execute(
            select(ApplicationTracking).where(ApplicationTracking.job_id == req.job_id)
        )).scalar_one_or_none()
        if existing:
            existing.status = req.status
            await session.commit()
            await session.refresh(existing)
            return _serialize(existing)

    app = ApplicationTracking(
        job_id=req.job_id,
        company_name=req.company_name,
        job_title=req.job_title,
        url=req.url,
        applied_date=req.applied_date,
        notes=req.notes,
        status=req.status,
        source=req.source,
        score=req.score,
    )
    session.add(app)
    await session.commit()
    await session.refresh(app)
    return _serialize(app)


class UpdateApplicationRequest(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None
    applied_date: date | None = None


@router.patch("/{app_id}")
async def update_application(app_id: int, req: UpdateApplicationRequest, session: Session):
    app = (await session.execute(
        select(ApplicationTracking).where(ApplicationTracking.id == app_id)
    )).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if req.status is not None:
        app.status = req.status
    if req.notes is not None:
        app.notes = req.notes
    if req.applied_date is not None:
        app.applied_date = req.applied_date
    await session.commit()
    await session.refresh(app)
    return _serialize(app)


@router.delete("/{app_id}", status_code=204)
async def delete_application(app_id: int, session: Session):
    app = (await session.execute(
        select(ApplicationTracking).where(ApplicationTracking.id == app_id)
    )).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await session.delete(app)
    await session.commit()


def _serialize(app: ApplicationTracking) -> dict:
    return {
        "id": app.id,
        "job_id": app.job_id,
        "company_name": app.company_name,
        "job_title": app.job_title,
        "url": app.url,
        "applied_date": app.applied_date.isoformat() if app.applied_date else None,
        "notes": app.notes,
        "status": app.status,
        "source": app.source,
        "score": app.score,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "updated_at": app.updated_at.isoformat() if app.updated_at else None,
    }
```

- [ ] **Step 4: Run all tests — expect all PASS**

```
pytest tests/test_applications.py -v
```
Expected: All 14 tests PASS.

- [ ] **Step 5: Commit**

```
git add backend/routers/applications.py tests/test_applications.py
git commit -m "feat: applications router - CRUD, bulk, and stats endpoints"
```

---

## Task 3: Frontend API layer

**Files:**
- Create: `frontend/src/api/applications.ts`

- [ ] **Step 1: Create `frontend/src/api/applications.ts`**

```typescript
import { api } from "./client";

export type ApplicationStatus = "interested" | "applied" | "rejected" | "offer";
export type ApplicationSource = "joblin" | "external";

export interface ApplicationTracking {
  id: number;
  job_id: number | null;
  company_name: string;
  job_title: string;
  url: string | null;
  applied_date: string | null;
  notes: string | null;
  status: ApplicationStatus;
  source: ApplicationSource;
  score: number | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationStats {
  total: number;
  by_status: { interested: number; applied: number; rejected: number; offer: number };
  response_rate: number;
  by_source: { joblin: number; external: number };
  daily_series: Array<{
    date: string;
    interested?: number;
    applied?: number;
    rejected?: number;
    offer?: number;
  }>;
}

export const applicationsApi = {
  list: (params?: {
    status?: ApplicationStatus;
    source?: ApplicationSource;
    search?: string;
    limit?: number;
    offset?: number;
  }) => api.get<ApplicationTracking[]>("/applications", { params }).then((r) => r.data),

  create: (data: {
    job_id?: number;
    company_name: string;
    job_title: string;
    url?: string;
    applied_date?: string;
    notes?: string;
    status: ApplicationStatus;
    source: ApplicationSource;
    score?: number;
  }) => api.post<ApplicationTracking>("/applications", data).then((r) => r.data),

  update: (id: number, data: { status?: ApplicationStatus; notes?: string; applied_date?: string }) =>
    api.patch<ApplicationTracking>(`/applications/${id}`, data).then((r) => r.data),

  delete: (id: number) => api.delete(`/applications/${id}`),

  bulkAction: (data: { ids: number[]; action: "status_change" | "delete"; status?: ApplicationStatus }) =>
    api.post("/applications/bulk", data).then((r) => r.data),

  stats: () => api.get<ApplicationStats>("/applications/stats").then((r) => r.data),
};
```

- [ ] **Step 2: Verify TypeScript compiles**

```
cd frontend && npx tsc --noEmit
```
Expected: No errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/api/applications.ts
git commit -m "feat: applications API client and TypeScript types"
```

---

## Task 4: Applications page + route + sidebar

**Files:**
- Create: `frontend/src/pages/Applications.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Add the route in `frontend/src/App.tsx`**

Add import after line 14 (the last page import):
```typescript
import { Applications } from "./pages/Applications";
```

Add route inside `<Route element={<Layout />}>` after the Matches route (line 30):
```tsx
<Route path="/applications" element={<Applications />} />
```

- [ ] **Step 2: Add nav item in `frontend/src/components/Sidebar.tsx`**

In the `NAV` array, insert after the Matches entry:
```typescript
{ label: "Applications", icon: "⊙", path: "/applications" },
```

- [ ] **Step 3: Create `frontend/src/pages/Applications.tsx`**

```tsx
import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  applicationsApi,
  ApplicationTracking,
  ApplicationStatus,
} from "../api/applications";

// ── helpers ──────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<ApplicationStatus, string> = {
  interested: "Interested",
  applied: "Applied",
  rejected: "Rejected",
  offer: "Offer",
};

const STATUS_STYLE: Record<ApplicationStatus, { badge: string; dot: string }> = {
  interested: { badge: "bg-purple-900/40 text-purple-400", dot: "bg-purple-400" },
  applied:    { badge: "bg-blue-900/40 text-blue-400",     dot: "bg-blue-400" },
  rejected:   { badge: "bg-red-900/40 text-red-400",       dot: "bg-red-400" },
  offer:      { badge: "bg-emerald-900/40 text-emerald-400", dot: "bg-emerald-400" },
};

function StatusBadge({ status }: { status: ApplicationStatus }) {
  const s = STATUS_STYLE[status];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium ${s.badge}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {STATUS_LABEL[status]}
    </span>
  );
}

// ── stats section ─────────────────────────────────────────────────────────────

function StatsSection() {
  const { data: stats } = useQuery({
    queryKey: ["applications", "stats"],
    queryFn: applicationsApi.stats,
  });

  const cards = [
    { label: "Total",         value: stats?.total ?? 0,                    color: "text-[#e5e5e5]" },
    { label: "Interested",    value: stats?.by_status.interested ?? 0,     color: "text-purple-400" },
    { label: "Applied",       value: stats?.by_status.applied ?? 0,        color: "text-blue-400" },
    { label: "Rejected",      value: stats?.by_status.rejected ?? 0,       color: "text-red-400" },
    { label: "Offer",         value: stats?.by_status.offer ?? 0,          color: "text-emerald-400" },
    { label: "Response Rate", value: `${stats?.response_rate ?? 0}%`,      color: "text-yellow-400" },
  ];

  const series = stats?.daily_series ?? [];
  const maxVal = Math.max(1, ...series.map((d) => (d.applied ?? 0) + (d.interested ?? 0)));
  const joblin = stats?.by_source.joblin ?? 0;
  const external = stats?.by_source.external ?? 0;
  const sourceTotal = joblin + external || 1;

  return (
    <div className="mb-6">
      <div className="grid grid-cols-6 gap-3 mb-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-[#111] border border-[#1e1e1e] rounded-lg p-3">
            <div className="text-[10px] text-[#444] uppercase tracking-wider mb-1.5">{c.label}</div>
            <div className={`text-2xl font-bold leading-none ${c.color}`}>{c.value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-[1fr_260px] gap-3">
        {/* Bar chart */}
        <div className="bg-[#111] border border-[#1e1e1e] rounded-lg p-4">
          <div className="text-[10px] text-[#444] uppercase tracking-wider mb-3">Applications over time (30 days)</div>
          <div className="flex items-end gap-1 h-16">
            {series.length === 0 && <div className="text-xs text-[#333] m-auto">No data yet</div>}
            {series.map((d) => {
              const a = d.applied ?? 0;
              const i = d.interested ?? 0;
              return (
                <div key={d.date} className="flex-1 flex flex-col justify-end h-full gap-px" title={`${d.date}: ${a} applied, ${i} interested`}>
                  {a > 0 && <div className="w-full rounded-sm bg-blue-500/60" style={{ height: `${Math.round((a / maxVal) * 100)}%` }} />}
                  {i > 0 && <div className="w-full rounded-sm bg-purple-500/60" style={{ height: `${Math.round((i / maxVal) * 100)}%` }} />}
                </div>
              );
            })}
          </div>
          <div className="flex gap-4 mt-2">
            <span className="flex items-center gap-1.5 text-[10px] text-[#555]"><span className="w-2 h-2 rounded-sm bg-blue-500/60" />Applied</span>
            <span className="flex items-center gap-1.5 text-[10px] text-[#555]"><span className="w-2 h-2 rounded-sm bg-purple-500/60" />Interested</span>
          </div>
        </div>

        {/* Source split */}
        <div className="bg-[#111] border border-[#1e1e1e] rounded-lg p-4">
          <div className="text-[10px] text-[#444] uppercase tracking-wider mb-4">Joblin vs External</div>
          <div className="space-y-4">
            {[
              { label: "Joblin-sourced", value: joblin,    textColor: "text-emerald-400", barColor: "bg-emerald-500/60" },
              { label: "External",       value: external,  textColor: "text-indigo-400",  barColor: "bg-indigo-500/60" },
            ].map((s) => (
              <div key={s.label}>
                <div className="flex justify-between mb-1">
                  <span className={`text-xs font-medium ${s.textColor}`}>{s.label}</span>
                  <span className={`text-xs font-bold ${s.textColor}`}>{s.value}</span>
                </div>
                <div className="h-1.5 bg-[#1e1e1e] rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${s.barColor}`} style={{ width: `${Math.round((s.value / sourceTotal) * 100)}%` }} />
                </div>
              </div>
            ))}
            <div className="text-[10px] text-[#333] text-center mt-2">{Math.round((joblin / sourceTotal) * 100)}% discovered by Joblin</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── inline status dropdown ────────────────────────────────────────────────────

function StatusDropdown({ app }: { app: ApplicationTracking }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();
  const update = useMutation({
    mutationFn: (status: ApplicationStatus) => applicationsApi.update(app.id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)}><StatusBadge status={app.status} /></button>
      {open && (
        <div className="absolute left-0 top-full mt-1 z-20 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg overflow-hidden shadow-xl w-36">
          {(["interested", "applied", "rejected", "offer"] as ApplicationStatus[]).map((s) => (
            <button
              key={s}
              className="w-full text-left px-3 py-2 text-xs hover:bg-[#222] flex items-center gap-2"
              onClick={() => { update.mutate(s); setOpen(false); }}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${STATUS_STYLE[s].dot}`} />
              {STATUS_LABEL[s]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── add external job modal ────────────────────────────────────────────────────

function AddExternalJobModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    company_name: "", job_title: "", url: "",
    status: "applied" as ApplicationStatus,
    applied_date: "", notes: "",
  });
  const set = (key: string, value: string) => setForm((f) => ({ ...f, [key]: value }));

  const create = useMutation({
    mutationFn: () => applicationsApi.create({
      company_name: form.company_name,
      job_title: form.job_title,
      url: form.url || undefined,
      applied_date: form.applied_date || undefined,
      notes: form.notes || undefined,
      status: form.status,
      source: "external",
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["applications"] }); onClose(); },
  });

  const showDate = ["applied", "rejected", "offer"].includes(form.status);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-[#111] border border-[#1e1e1e] rounded-xl w-full max-w-md p-6">
        <h2 className="text-sm font-semibold text-[#e5e5e5] mb-4">Add External Job</h2>
        <div className="space-y-3">
          {[
            { label: "Company *", key: "company_name", type: "text", placeholder: "" },
            { label: "Job Title *", key: "job_title", type: "text", placeholder: "" },
            { label: "URL", key: "url", type: "text", placeholder: "https://..." },
          ].map((f) => (
            <div key={f.key}>
              <label className="block text-[10px] text-[#555] uppercase tracking-wider mb-1">{f.label}</label>
              <input
                type={f.type}
                placeholder={f.placeholder}
                className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm text-[#e5e5e5] outline-none focus:border-[#4e9eff]"
                value={(form as Record<string, string>)[f.key]}
                onChange={(e) => set(f.key, e.target.value)}
              />
            </div>
          ))}
          <div>
            <label className="block text-[10px] text-[#555] uppercase tracking-wider mb-1">Status</label>
            <select
              className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm text-[#e5e5e5] outline-none"
              value={form.status}
              onChange={(e) => set("status", e.target.value)}
            >
              <option value="interested">Interested</option>
              <option value="applied">Applied</option>
              <option value="rejected">Rejected</option>
              <option value="offer">Offer</option>
            </select>
          </div>
          {showDate && (
            <div>
              <label className="block text-[10px] text-[#555] uppercase tracking-wider mb-1">Date Applied</label>
              <input
                type="date"
                className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm text-[#e5e5e5] outline-none focus:border-[#4e9eff]"
                value={form.applied_date}
                onChange={(e) => set("applied_date", e.target.value)}
              />
            </div>
          )}
          <div>
            <label className="block text-[10px] text-[#555] uppercase tracking-wider mb-1">Notes</label>
            <textarea
              className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm text-[#e5e5e5] outline-none focus:border-[#4e9eff] resize-none"
              rows={3}
              value={form.notes}
              onChange={(e) => set("notes", e.target.value)}
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button className="px-4 py-2 text-xs text-[#666] hover:text-[#999] border border-[#1e1e1e] rounded-md" onClick={onClose}>Cancel</button>
          <button
            className="px-4 py-2 text-xs bg-[#1d4ed8] hover:bg-blue-600 text-white rounded-md disabled:opacity-50"
            disabled={!form.company_name || !form.job_title || create.isPending}
            onClick={() => create.mutate()}
          >
            Add Job
          </button>
        </div>
      </div>
    </div>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────

const ALL_STATUSES = ["interested", "applied", "rejected", "offer"] as ApplicationStatus[];

export function Applications() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | "all">("all");
  const [sourceFilter, setSourceFilter] = useState<"all" | "joblin" | "external">("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [showModal, setShowModal] = useState(false);

  const { data: apps = [], isLoading } = useQuery({
    queryKey: ["applications", statusFilter, sourceFilter, search],
    queryFn: () => applicationsApi.list({
      status: statusFilter === "all" ? undefined : statusFilter,
      source: sourceFilter === "all" ? undefined : sourceFilter,
      search: search || undefined,
    }),
  });

  const { data: stats } = useQuery({
    queryKey: ["applications", "stats"],
    queryFn: applicationsApi.stats,
  });

  const bulkMutation = useMutation({
    mutationFn: (data: { ids: number[]; action: "status_change" | "delete"; status?: ApplicationStatus }) =>
      applicationsApi.bulkAction(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["applications"] }); setSelected(new Set()); },
  });

  const deleteSingle = useMutation({
    mutationFn: (id: number) => applicationsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  const toggleSelect = (id: number) =>
    setSelected((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const tabCount = (s: ApplicationStatus | "all") =>
    s === "all" ? (stats?.total ?? 0) : (stats?.by_status[s] ?? 0);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-5">
        <h1 className="text-base font-semibold text-[#e5e5e5]">Applications</h1>
        <p className="text-xs text-[#555] mt-0.5">Track jobs you're interested in, applied to, or heard back from</p>
      </div>

      <StatsSection />

      {/* Tab + control row */}
      <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <div className="flex gap-0.5 bg-[#111] border border-[#1e1e1e] rounded-lg p-1">
          {(["all", ...ALL_STATUSES] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                statusFilter === s ? "bg-[#1a2233] text-[#4e9eff]" : "text-[#555] hover:text-[#888]"
              }`}
            >
              {s === "all" ? "All" : STATUS_LABEL[s]}{" "}
              <span className={statusFilter === s ? "text-[#4e9eff]" : "text-[#333]"}>{tabCount(s)}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <select
            className="bg-[#111] border border-[#1e1e1e] rounded-md px-3 py-1.5 text-xs text-[#666] outline-none"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value as typeof sourceFilter)}
          >
            <option value="all">All sources</option>
            <option value="joblin">Joblin</option>
            <option value="external">External</option>
          </select>
          <input
            className="bg-[#111] border border-[#1e1e1e] rounded-md px-3 py-1.5 text-xs text-[#999] placeholder-[#333] outline-none focus:border-[#333] w-48"
            placeholder="Search company or role..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button
            className="bg-[#1d4ed8] hover:bg-blue-600 text-white text-xs font-medium px-3 py-1.5 rounded-md"
            onClick={() => setShowModal(true)}
          >
            + Add External Job
          </button>
        </div>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-3 bg-[#111] border border-[#2a2a2a] rounded-lg px-4 py-2.5">
          <span className="text-xs text-[#888]">{selected.size} selected</span>
          <div className="flex gap-2 ml-auto flex-wrap">
            {ALL_STATUSES.map((s) => (
              <button
                key={s}
                className="text-xs px-3 py-1 border border-[#1e1e1e] rounded-md text-[#666] hover:text-[#999] hover:border-[#333]"
                onClick={() => bulkMutation.mutate({ ids: [...selected], action: "status_change", status: s })}
              >
                {STATUS_LABEL[s]}
              </button>
            ))}
            <button
              className="text-xs px-3 py-1 border border-red-900/40 text-red-500/60 hover:text-red-400 rounded-md"
              onClick={() => { if (confirm(`Delete ${selected.size} application(s)?`)) bulkMutation.mutate({ ids: [...selected], action: "delete" }); }}
            >
              Delete
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-[#111] border border-[#1e1e1e] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1e1e] bg-[#0a0a0a]">
              <th className="w-10 px-4 py-2.5">
                <input
                  type="checkbox"
                  className="accent-[#4e9eff]"
                  checked={apps.length > 0 && selected.size === apps.length}
                  onChange={() => setSelected(apps.length === selected.size ? new Set() : new Set(apps.map((a) => a.id)))}
                />
              </th>
              {["Status", "Company", "Role", "Applied", "Source", "Score", "Notes", ""].map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-[10px] text-[#444] uppercase tracking-wider font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-xs text-[#444]">Loading...</td></tr>
            )}
            {!isLoading && apps.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-xs text-[#444]">No applications yet</td></tr>
            )}
            {apps.map((app) => (
              <tr key={app.id} className="border-b border-[#141414] hover:bg-[#0d0d0d]">
                <td className="w-10 px-4 py-2.5">
                  <input type="checkbox" className="accent-[#4e9eff]" checked={selected.has(app.id)} onChange={() => toggleSelect(app.id)} />
                </td>
                <td className="px-4 py-2.5"><StatusDropdown app={app} /></td>
                <td className="px-4 py-2.5 text-[#e5e5e5] font-medium text-xs">{app.company_name}</td>
                <td className="px-4 py-2.5 text-[#888] text-xs">{app.job_title}</td>
                <td className="px-4 py-2.5 text-[#555] text-xs">{app.applied_date ?? "—"}</td>
                <td className="px-4 py-2.5">
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${app.source === "joblin" ? "bg-emerald-900/30 text-emerald-500" : "bg-indigo-900/30 text-indigo-400"}`}>
                    {app.source === "joblin" ? "Joblin" : "External"}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs">
                  {app.score != null
                    ? <span className="bg-blue-900/30 text-blue-400 px-1.5 py-0.5 rounded font-semibold">{app.score.toFixed(2)}</span>
                    : <span className="text-[#333]">—</span>}
                </td>
                <td className="px-4 py-2.5 text-[#444] text-xs max-w-[180px] truncate">{app.notes ?? ""}</td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-1.5">
                    {app.url && (
                      <a href={app.url} target="_blank" rel="noreferrer" className="text-[10px] px-2 py-1 border border-[#1e1e1e] rounded text-[#555] hover:text-[#4e9eff] hover:border-[#333]">↗</a>
                    )}
                    <button
                      className="text-[10px] px-2 py-1 border border-red-900/30 text-red-500/40 hover:text-red-400 rounded"
                      onClick={() => deleteSingle.mutate(app.id)}
                    >✕</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && <AddExternalJobModal onClose={() => setShowModal(false)} />}
    </div>
  );
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```
cd frontend && npx tsc --noEmit
```
Expected: No errors.

- [ ] **Step 5: Start the dev server and verify the page works**

```
cd frontend && npm run dev
```

Navigate to http://localhost:5173/applications. Check:
- "Applications" appears in the sidebar
- Stats cards show (all zeros is correct)
- Bar chart shows "No data yet"
- Table shows "No applications yet"
- "+ Add External Job" opens the modal; filling company + title enables the button; submitting creates a row in the table and the stats update

- [ ] **Step 6: Commit**

```
git add frontend/src/pages/Applications.tsx frontend/src/App.tsx frontend/src/components/Sidebar.tsx
git commit -m "feat: Applications page with stats dashboard, table, and external job modal"
```

---

## Task 5: Matches page — View JD, Interested, Applied, bulk tracking

**Files:**
- Modify: `frontend/src/pages/Matches.tsx`

- [ ] **Step 1: Add imports at the top of `Matches.tsx`**

```typescript
import { applicationsApi, ApplicationTracking, ApplicationStatus } from "../api/applications";
```

- [ ] **Step 2: Load tracker state in the `Matches` component**

Inside the top-level `Matches` function, alongside existing `useQuery` calls, add:

```typescript
const { data: trackedApps = [] } = useQuery({
  queryKey: ["applications"],
  queryFn: () => applicationsApi.list(),
});

const trackerMap = new Map<number, ApplicationTracking>(
  trackedApps
    .filter((a): a is ApplicationTracking & { job_id: number } => a.job_id != null)
    .map((a) => [a.job_id, a])
);
```

- [ ] **Step 3: Add `TrackButtons` component above `MatchRow`**

Add this new component in `Matches.tsx`, above the `MatchRow` function definition:

```tsx
function TrackButtons({
  match,
  trackerMap,
}: {
  match: Match;
  trackerMap: Map<number, ApplicationTracking>;
}) {
  const qc = useQueryClient();
  const tracked = trackerMap.get(match.job_id);

  const track = useMutation({
    mutationFn: (status: ApplicationStatus) =>
      applicationsApi.create({
        job_id: match.job_id,
        company_name: match.company_name,
        job_title: match.job_title,
        url: match.job_url ?? undefined,
        status,
        source: "joblin",
        score: match.score,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  const isInterested = tracked?.status === "interested";
  const isApplied =
    tracked?.status === "applied" ||
    tracked?.status === "rejected" ||
    tracked?.status === "offer";

  return (
    <>
      <button
        className={`text-xs px-3 py-1.5 border rounded-md transition-colors ${
          isInterested
            ? "bg-purple-900/40 border-purple-800/60 text-purple-400"
            : "border-[#1e1e1e] text-[#666] hover:text-purple-400 hover:border-purple-900/60"
        }`}
        onClick={() => track.mutate("interested")}
        disabled={track.isPending}
      >
        ★ Interested
      </button>
      <button
        className={`text-xs px-3 py-1.5 border rounded-md transition-colors ${
          isApplied
            ? "bg-blue-900/40 border-blue-800/60 text-blue-400"
            : "border-[#1e1e1e] text-[#666] hover:text-blue-400 hover:border-blue-900/60"
        }`}
        onClick={() => track.mutate("applied")}
        disabled={track.isPending}
      >
        ✓ Applied
      </button>
    </>
  );
}
```

- [ ] **Step 4: Update `MatchRow`'s props to accept `trackerMap`**

Find the `MatchRow` function signature and add `trackerMap` to its props:

```typescript
// Before:
function MatchRow({ match, selected, onSelect }: { match: Match; selected: boolean; onSelect: () => void })

// After:
function MatchRow({
  match,
  selected,
  onSelect,
  trackerMap,
}: {
  match: Match;
  selected: boolean;
  onSelect: () => void;
  trackerMap: Map<number, ApplicationTracking>;
})
```

- [ ] **Step 5: Replace the Apply button in `MatchRow`**

Find the existing Apply button in the expanded section of `MatchRow`. It looks like:
```tsx
{applyUrl && <a href={applyUrl} target="_blank">Apply</a>}
```
(may have Tailwind classes — find the exact line)

Replace it with:
```tsx
{applyUrl && (
  <a
    href={applyUrl}
    target="_blank"
    rel="noreferrer"
    className="text-xs px-3 py-1.5 border border-[#1e1e1e] rounded-md text-[#4e9eff] hover:border-[#333]"
  >
    ↗ View JD
  </a>
)}
<TrackButtons match={match} trackerMap={trackerMap} />
```

- [ ] **Step 6: Pass `trackerMap` to every `<MatchRow />` call site**

Find all places where `<MatchRow` is rendered (likely one spot in the Matches component's return) and add the prop:

```tsx
<MatchRow
  key={match.id}
  match={match}
  selected={selectedMatches.has(match.id)}
  onSelect={() => { /* existing toggle logic */ }}
  trackerMap={trackerMap}
/>
```

Use the actual variable names from the file (`selectedMatches` and the toggle handler may differ — check the file).

- [ ] **Step 7: Add bulk tracking buttons to the existing bulk action bar**

Find the existing bulk action bar in the `Matches` component (contains the "Re-notify N selected" button). Add two buttons before the existing ones:

```tsx
<button
  className="text-xs px-3 py-1 border border-[#1e1e1e] rounded text-[#666] hover:text-purple-400 hover:border-purple-900/60"
  onClick={() => {
    const toTrack = matches.filter((m) => selectedMatches.has(m.id));
    Promise.all(
      toTrack.map((m) =>
        applicationsApi.create({
          job_id: m.job_id,
          company_name: m.company_name,
          job_title: m.job_title,
          url: m.job_url ?? undefined,
          status: "interested",
          source: "joblin",
          score: m.score,
        })
      )
    ).then(() => qc.invalidateQueries({ queryKey: ["applications"] }));
  }}
>
  ★ Mark Interested
</button>
<button
  className="text-xs px-3 py-1 border border-[#1e1e1e] rounded text-[#666] hover:text-blue-400 hover:border-blue-900/60"
  onClick={() => {
    const toTrack = matches.filter((m) => selectedMatches.has(m.id));
    Promise.all(
      toTrack.map((m) =>
        applicationsApi.create({
          job_id: m.job_id,
          company_name: m.company_name,
          job_title: m.job_title,
          url: m.job_url ?? undefined,
          status: "applied",
          source: "joblin",
          score: m.score,
        })
      )
    ).then(() => qc.invalidateQueries({ queryKey: ["applications"] }));
  }}
>
  ✓ Mark Applied
</button>
```

Use the actual variable names from the file: `matches` may be named differently (e.g., `data`), and `selectedMatches` may differ. Check the existing bulk action handler to find the correct names.

- [ ] **Step 8: Verify TypeScript compiles**

```
cd frontend && npx tsc --noEmit
```
Expected: No errors.

- [ ] **Step 9: Test in the browser**

Start the dev server. On the Matches page:
- Expand a match card — "↗ View JD", "★ Interested", "✓ Applied", "✦ Tailor Resume" appear
- Clicking "★ Interested" turns the button purple; navigate to /applications to confirm the job is there with status "interested"
- Clicking "✓ Applied" on the same card turns it blue; check /applications shows status updated to "applied" (upserted, same row)
- Select multiple cards via checkbox; bulk action bar shows "★ Mark Interested", "✓ Mark Applied", plus the existing actions
- "Dismiss" continues to work as before

- [ ] **Step 10: Commit**

```
git add frontend/src/pages/Matches.tsx
git commit -m "feat: Matches page - View JD, Interested/Applied buttons, bulk tracking"
```
