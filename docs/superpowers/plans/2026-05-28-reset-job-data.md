# Reset Job Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `POST /api/admin/reset` endpoint and a Danger tab in Settings that wipes jobs, matches, runs, run_company_results, and feedback_examples while keeping companies, settings, and token_usage.

**Architecture:** New `backend/routers/admin.py` handles deletion in FK-safe order and returns counts. Settings.tsx gains a `"danger"` tab with an inline confirmation gate (user must type `RESET`) that calls the endpoint via the existing axios `api` client and invalidates affected TanStack Query caches on success.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, pytest-anyio, React 18, TanStack Query v5, shadcn/ui patterns.

---

## File Map

| File | Change |
|---|---|
| `backend/routers/admin.py` | New -- reset endpoint |
| `backend/main.py` | Modify -- register admin router |
| `tests/test_admin.py` | New -- backend tests |
| `frontend/src/pages/Settings.tsx` | Modify -- add danger tab |

---

## Task 1: Backend reset endpoint

**Files:**
- Create: `backend/routers/admin.py`
- Modify: `backend/main.py`
- Create: `tests/test_admin.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_admin.py`:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_reset_returns_200_with_deleted_counts(client: AsyncClient):
    resp = await client.post("/api/admin/reset")
    assert resp.status_code == 200
    data = resp.json()
    assert "deleted" in data
    assert set(data["deleted"].keys()) == {
        "feedback_examples", "matches", "run_company_results", "jobs", "runs"
    }
    for v in data["deleted"].values():
        assert isinstance(v, int)


@pytest.mark.anyio
async def test_reset_on_empty_db_returns_zeros(client: AsyncClient):
    resp = await client.post("/api/admin/reset")
    assert resp.status_code == 200
    data = resp.json()
    for v in data["deleted"].values():
        assert v == 0


@pytest.mark.anyio
async def test_reset_is_idempotent(client: AsyncClient):
    resp1 = await client.post("/api/admin/reset")
    resp2 = await client.post("/api/admin/reset")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    for v in resp2.json()["deleted"].values():
        assert v == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:\dev\joblin
.venv\Scripts\pytest tests/test_admin.py -v
```

Expected: FAIL with 404 (route not registered yet).

- [ ] **Step 3: Write `backend/routers/admin.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models.feedback import FeedbackExample
from backend.models.job import Job
from backend.models.match import Match
from backend.models.run import Run, RunCompanyResult

router = APIRouter(prefix="/admin", tags=["admin"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/reset")
async def reset_job_data(session: Session):
    counts = {}

    counts["feedback_examples"] = (await session.execute(select(func.count()).select_from(FeedbackExample))).scalar() or 0
    await session.execute(delete(FeedbackExample))

    counts["matches"] = (await session.execute(select(func.count()).select_from(Match))).scalar() or 0
    await session.execute(delete(Match))

    counts["run_company_results"] = (await session.execute(select(func.count()).select_from(RunCompanyResult))).scalar() or 0
    await session.execute(delete(RunCompanyResult))

    counts["jobs"] = (await session.execute(select(func.count()).select_from(Job))).scalar() or 0
    await session.execute(delete(Job))

    counts["runs"] = (await session.execute(select(func.count()).select_from(Run))).scalar() or 0
    await session.execute(delete(Run))

    await session.commit()
    return {"deleted": counts}
```

- [ ] **Step 4: Register the router in `backend/main.py`**

Add the import line after the existing router imports:

```python
from backend.routers.admin import router as admin_router
```

Add inside `create_app()` after the other `include_router` calls:

```python
app.include_router(admin_router, prefix="/api")
```

The full updated import block:

```python
from backend.routers import system, companies, runs as runs_router, jobs, matches, settings as settings_router, presets
from backend.routers.usage import router as usage_router
from backend.routers.admin import router as admin_router
```

The full updated `create_app()`:

```python
def create_app() -> FastAPI:
    app = FastAPI(title="Joblin", lifespan=lifespan)
    app.include_router(system.router, prefix="/api")
    app.include_router(companies.router, prefix="/api")
    app.include_router(runs_router.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(matches.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(presets.router, prefix="/api")
    app.include_router(usage_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")
    return app
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv\Scripts\pytest tests/test_admin.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Run full test suite**

```bash
.venv\Scripts\pytest tests/ -q
```

Expected: 30 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/admin.py backend/main.py tests/test_admin.py
git commit -m "feat: POST /api/admin/reset endpoint"
```

---

## Task 2: Danger tab in Settings

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: Add danger tab state and imports**

At the top of `Settings.tsx`, update the `Tab` type and add `useState` for the confirmation input and reset state. The existing imports are fine -- `api` is available via `settingsApi` using the same axios instance, but for the reset call use `api` directly.

Add `import { api } from "@/api/client";` after the existing imports.

Add two new state variables inside `Settings()` after the existing ones:

```tsx
const [resetInput, setResetInput] = useState("");
const [resetError, setResetError] = useState<string | null>(null);
const [resetDone, setResetDone] = useState(false);
const [showResetConfirm, setShowResetConfirm] = useState(false);
```

- [ ] **Step 2: Update the Tab type and tabs array**

Change:
```tsx
type Tab = "discord" | "criteria" | "schedule" | "llm" | "presets";
```

To:
```tsx
type Tab = "discord" | "criteria" | "schedule" | "llm" | "presets" | "danger";
```

Change the `tabs` array from:
```tsx
const tabs: { key: Tab; label: string }[] = [
  { key: "discord", label: "Discord" },
  { key: "criteria", label: "Criteria" },
  { key: "schedule", label: "Schedule" },
  { key: "llm", label: "LLM Keys" },
  { key: "presets", label: "Presets" },
];
```

To:
```tsx
const tabs: { key: Tab; label: string }[] = [
  { key: "discord", label: "Discord" },
  { key: "criteria", label: "Criteria" },
  { key: "schedule", label: "Schedule" },
  { key: "llm", label: "LLM Keys" },
  { key: "presets", label: "Presets" },
  { key: "danger", label: "Danger" },
];
```

- [ ] **Step 3: Add the reset handler function**

Inside `Settings()`, after the existing mutation declarations, add:

```tsx
async function handleReset() {
  setResetError(null);
  try {
    await api.post("/admin/reset");
    setResetDone(true);
    setResetInput("");
    setShowResetConfirm(false);
    qc.invalidateQueries({ queryKey: ["runs"] });
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["matches"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Reset failed";
    setResetError(msg);
  }
}
```

- [ ] **Step 4: Add the Danger tab panel**

Inside the return JSX, after the closing `}` of the presets tab panel and before the closing `</div>` of the component, add:

```tsx
      {tab === "danger" && (
        <div className="max-w-md space-y-4">
          <div className="border border-red-900 rounded-lg p-4 bg-[#0a0a0a]">
            <h3 className="text-sm font-semibold text-red-400 mb-2">Reset job data</h3>
            <div className="text-xs text-[#666] space-y-1 mb-4">
              <p>Permanently deletes:</p>
              <ul className="list-disc list-inside text-[#555] space-y-0.5">
                <li>All scraped jobs</li>
                <li>All matches and summaries</li>
                <li>All run history</li>
                <li>Feedback / not-interested signals</li>
              </ul>
              <p className="mt-2">Keeps: companies, settings, API keys, token usage history.</p>
            </div>

            {resetDone && (
              <div className="text-xs text-emerald-500 mb-3">Reset complete. Database is empty.</div>
            )}

            {!showResetConfirm ? (
              <button
                onClick={() => { setShowResetConfirm(true); setResetDone(false); }}
                className="text-xs border border-red-800 rounded px-3 py-1.5 text-red-400 hover:bg-red-950 transition-colors"
              >
                Reset job data
              </button>
            ) : (
              <div className="space-y-2">
                <input
                  value={resetInput}
                  onChange={(e) => setResetInput(e.target.value)}
                  placeholder="Type RESET to confirm"
                  className="w-full bg-[#111] border border-red-900 rounded px-3 py-2 text-sm text-[#e5e5e5] placeholder-[#444]"
                />
                {resetError && <div className="text-xs text-red-400">{resetError}</div>}
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleReset}
                    disabled={resetInput !== "RESET"}
                    className="text-xs border border-red-700 rounded px-3 py-1.5 text-red-400 bg-red-950 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-red-900 transition-colors"
                  >
                    Confirm reset
                  </button>
                  <button
                    onClick={() => { setShowResetConfirm(false); setResetInput(""); setResetError(null); }}
                    className="text-xs text-[#555] hover:text-[#888]"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
```

- [ ] **Step 5: Run TypeScript check**

```bash
cd C:\dev\joblin\frontend
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 6: Commit**

```bash
cd C:\dev\joblin
git add frontend/src/pages/Settings.tsx
git commit -m "feat: danger tab with reset job data confirmation UI"
```
