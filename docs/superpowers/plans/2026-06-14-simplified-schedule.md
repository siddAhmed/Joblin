# Simplified Schedule UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the raw cron input in Settings with preset chips + time/timezone pickers, and fix the scheduler to run per-user jobs instead of hardcoding user_id=1.

**Architecture:** The frontend computes a cron string from the selected preset and saves all schedule state keys + `schedule_cron` in one PATCH. The backend scheduler reads only `schedule_cron` but now creates one APScheduler job per user keyed `scrape_cron_{user_id}`. A `sync_user_schedule` helper in scheduler.py is called by the settings router after every PATCH so the running scheduler stays in sync without a restart.

**Tech Stack:** Python/FastAPI/APScheduler 4.x (backend), React 19/TypeScript/TanStack Query/Tailwind (frontend), Vitest (frontend unit tests), pytest-anyio (backend tests)

**Working directory:** `C:\dev\joblin-schedule` (git worktree on `feat/simplified-schedule`)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/config.py` | Modify | Add 7 new default keys |
| `backend/scheduler.py` | Rewrite | Per-user jobs, timezone support, sync helper |
| `backend/main.py` | Modify | Store scheduler in `app.state.scheduler` |
| `backend/routers/settings.py` | Modify | Call sync helper after PATCH |
| `tests/test_scheduler.py` | Create | Scheduler unit tests |
| `frontend/src/utils/scheduleUtils.ts` | Create | Pure helpers: types, presetToCron, describeSchedule, constants |
| `frontend/src/utils/scheduleUtils.test.ts` | Create | Vitest unit tests for scheduleUtils |
| `frontend/src/pages/Settings.tsx` | Modify | Replace schedule tab with chip UI (ScheduleTab component) |

---

## Task 1: Add new setting defaults

**Files:**
- Modify: `backend/config.py:10-32`

- [ ] **Step 1: Add the 7 new keys to DEFAULTS**

Open `backend/config.py`. In the `DEFAULTS` dict, add these entries after `"schedule_cron": "0 */4 * * *"`:

```python
    "schedule_cron": "0 */4 * * *",
    "schedule_preset": "custom",
    "schedule_time": "06:00",
    "schedule_day_of_week": 1,
    "schedule_timezone": "Asia/Kolkata",
    "schedule_custom_mode": "cron",
    "schedule_interval_value": 4,
    "schedule_interval_unit": "hours",
    "staleness_threshold_hours": 4,
```

The full DEFAULTS block should now be:

```python
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
    "schedule_preset": "custom",
    "schedule_time": "06:00",
    "schedule_day_of_week": 1,
    "schedule_timezone": "Asia/Kolkata",
    "schedule_custom_mode": "cron",
    "schedule_interval_value": 4,
    "schedule_interval_unit": "hours",
    "staleness_threshold_hours": 4,
    "quarantine_threshold": 3,
    "groq_api_key": os.getenv("GROQ_API_KEY", ""),
    "cerebras_api_key": os.getenv("CEREBRAS_API_KEY", ""),
    "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
    "llm_filter_provider": "groq",
    "llm_summarize_provider": "cerebras",
    "scheduler_enabled": False,
}
```

- [ ] **Step 2: Commit**

```bash
git add backend/config.py
git commit -m "feat: add schedule preset and timezone setting defaults"
```

---

## Task 2: Rewrite scheduler.py for per-user jobs and timezone support

**Files:**
- Rewrite: `backend/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scheduler.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest


@pytest.mark.anyio
async def test_schedule_user_job_creates_job_with_correct_id_and_timezone():
    """_schedule_user_job creates a job keyed scrape_cron_{user_id} with the user's timezone."""
    mock_scheduler = AsyncMock()

    settings_map = {
        "schedule_cron": "0 9 * * *",
        "scheduler_enabled": True,
        "schedule_timezone": "Asia/Kolkata",
    }

    async def fake_get_setting(session, key, user_id):
        return settings_map.get(key)

    with patch("backend.scheduler.AsyncSessionLocal") as mock_sl, \
         patch("backend.scheduler.get_setting", side_effect=fake_get_setting):
        mock_session = AsyncMock()
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        from backend.scheduler import _schedule_user_job
        await _schedule_user_job(mock_scheduler, user_id=42)

    mock_scheduler.add_schedule.assert_called_once()
    _, kwargs = mock_scheduler.add_schedule.call_args
    assert kwargs.get("id") == "scrape_cron_42" or mock_scheduler.add_schedule.call_args.kwargs.get("id") == "scrape_cron_42"


@pytest.mark.anyio
async def test_schedule_user_job_removes_job_when_disabled():
    """_schedule_user_job removes the existing job when scheduler_enabled is False."""
    mock_scheduler = AsyncMock()

    async def fake_get_setting(session, key, user_id):
        return {"schedule_cron": "0 9 * * *", "scheduler_enabled": False, "schedule_timezone": "UTC"}.get(key)

    with patch("backend.scheduler.AsyncSessionLocal") as mock_sl, \
         patch("backend.scheduler.get_setting", side_effect=fake_get_setting):
        mock_session = AsyncMock()
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        from backend.scheduler import _schedule_user_job
        await _schedule_user_job(mock_scheduler, user_id=7)

    mock_scheduler.add_schedule.assert_not_called()
    mock_scheduler.remove_schedule.assert_called_once_with("scrape_cron_7")


@pytest.mark.anyio
async def test_run_scrape_job_uses_provided_user_id():
    """_run_scrape_job creates a Run for the given user_id, not hardcoded user_id=1."""
    from unittest.mock import AsyncMock, patch, MagicMock

    with patch("backend.scheduler.AsyncSessionLocal") as mock_sl, \
         patch("backend.scheduler.get_setting", return_value=999), \
         patch("backend.pipeline.execute_run", new_callable=AsyncMock):

        # First session: staleness check → no recent run → create new Run
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        from backend.scheduler import _run_scrape_job
        await _run_scrape_job(user_id=99)

    # The Run object added to session should have user_id=99
    added_run = mock_session.add.call_args[0][0]
    assert added_run.user_id == 99
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/dev/joblin-schedule
python -m pytest tests/test_scheduler.py -v
```

Expected: `ImportError` or `AttributeError` because `_schedule_user_job` and updated `_run_scrape_job` don't exist yet.

- [ ] **Step 3: Rewrite backend/scheduler.py**

Replace the entire file:

```python
from datetime import datetime, timezone, timedelta

from apscheduler import AsyncScheduler, ConflictPolicy
from apscheduler.triggers.cron import CronTrigger

from backend.database import AsyncSessionLocal
from backend.config import get_setting


async def _run_scrape_job(user_id: int) -> None:
    from backend.models.run import Run, RunStatus
    from backend.pipeline import execute_run
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        staleness_hours = float(await get_setting(session, "staleness_threshold_hours", user_id=user_id) or 4)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=staleness_hours)
        last_run = (await session.execute(
            select(Run)
            .where(Run.status == RunStatus.completed, Run.user_id == user_id)
            .order_by(Run.completed_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        if last_run and last_run.completed_at and last_run.completed_at > cutoff:
            return

        run = Run(is_preview=False, user_id=user_id)
        session.add(run)
        await session.commit()
        await session.refresh(run)

    async with AsyncSessionLocal() as session:
        await execute_run(run.id, session)


async def _schedule_user_job(scheduler: AsyncScheduler, user_id: int) -> None:
    async with AsyncSessionLocal() as session:
        cron_expr = str(await get_setting(session, "schedule_cron", user_id=user_id) or "0 */4 * * *")
        enabled = bool(await get_setting(session, "scheduler_enabled", user_id=user_id) or False)
        tz = str(await get_setting(session, "schedule_timezone", user_id=user_id) or "UTC")

    job_id = f"scrape_cron_{user_id}"

    if not enabled:
        try:
            await scheduler.remove_schedule(job_id)
        except Exception:
            pass
        return

    parts = cron_expr.split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
    else:
        minute, hour, day, month, day_of_week = "0", "*/4", "*", "*", "*"

    await scheduler.add_schedule(
        _run_scrape_job,
        CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week, timezone=tz),
        id=job_id,
        kwargs={"user_id": user_id},
        conflict_policy=ConflictPolicy.replace,
    )


async def start_scheduler(scheduler: AsyncScheduler) -> None:
    from backend.models.user import User
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        user_ids = [u.id for u in (await session.execute(select(User))).scalars().all()]

    for user_id in user_ids:
        await _schedule_user_job(scheduler, user_id)


async def sync_user_schedule(scheduler: AsyncScheduler, user_id: int) -> None:
    await _schedule_user_job(scheduler, user_id)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_scheduler.py -v
```

Expected:
```
tests/test_scheduler.py::test_schedule_user_job_creates_job_with_correct_id_and_timezone PASSED
tests/test_scheduler.py::test_schedule_user_job_removes_job_when_disabled PASSED
tests/test_scheduler.py::test_run_scrape_job_uses_provided_user_id PASSED
```

- [ ] **Step 5: Commit**

```bash
git add backend/scheduler.py tests/test_scheduler.py
git commit -m "feat: per-user scheduler jobs with timezone support"
```

---

## Task 3: Store scheduler in app.state

**Files:**
- Modify: `backend/main.py:29-32`

- [ ] **Step 1: Add app.state.scheduler assignment**

In `backend/main.py`, add one line inside the lifespan to store the scheduler on `app.state`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from apscheduler import AsyncScheduler
    from backend.config import seed_defaults
    from backend.scheduler import start_scheduler

    async with AsyncSessionLocal() as session:
        await seed_defaults(session, user_id=1)

    async with AsyncScheduler() as scheduler:
        app.state.scheduler = scheduler          # <-- add this line
        await start_scheduler(scheduler)
        await scheduler.start_in_background()
        yield
```

- [ ] **Step 2: Verify the app still starts**

```bash
cd C:/dev/joblin-schedule
python -m pytest tests/test_health.py -v
```

Expected: all health tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: expose scheduler on app.state for router access"
```

---

## Task 4: Wire settings router to sync scheduler after PATCH

**Files:**
- Modify: `backend/routers/settings.py`
- Test: `tests/test_scheduler.py` (append)

- [ ] **Step 1: Write failing test**

Append to `tests/test_scheduler.py`:

```python
@pytest.mark.anyio
async def test_settings_patch_syncs_scheduler_when_schedule_keys_updated(client, app):
    """PATCH /settings with schedule keys calls sync_user_schedule."""
    with patch("backend.routers.settings.sync_user_schedule", new_callable=AsyncMock) as mock_sync:
        mock_scheduler = AsyncMock()
        app.state.scheduler = mock_scheduler

        response = await client.patch("/api/settings", json={"scheduler_enabled": True})

    assert response.status_code == 200
    mock_sync.assert_called_once_with(mock_scheduler, 1)


@pytest.mark.anyio
async def test_settings_patch_does_not_sync_for_non_schedule_keys(client, app):
    """PATCH /settings with non-schedule keys does not call sync_user_schedule."""
    with patch("backend.routers.settings.sync_user_schedule", new_callable=AsyncMock) as mock_sync:
        app.state.scheduler = AsyncMock()

        response = await client.patch("/api/settings", json={"discord_webhook_url": "https://example.com"})

    assert response.status_code == 200
    mock_sync.assert_not_called()
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_scheduler.py::test_settings_patch_syncs_scheduler_when_schedule_keys_updated tests/test_scheduler.py::test_settings_patch_does_not_sync_for_non_schedule_keys -v
```

Expected: FAIL — `sync_user_schedule` import doesn't exist in the router yet.

- [ ] **Step 3: Update settings router**

Replace `backend/routers/settings.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings, set_setting
from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.discord import post_match_to_discord
from backend.scheduler import sync_user_schedule

router = APIRouter(prefix="/settings", tags=["settings"])
Session = Annotated[AsyncSession, Depends(get_session)]

SCHEDULE_KEYS = {"schedule_cron", "scheduler_enabled", "schedule_timezone"}


@router.get("")
async def get_settings(session: Session, current_user: CurrentUser):
    return await get_all_settings(session, user_id=current_user.id)


@router.patch("")
async def update_settings(request: Request, body: dict, session: Session, current_user: CurrentUser):
    for key, value in body.items():
        await set_setting(session, key, value, user_id=current_user.id)

    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None and SCHEDULE_KEYS & set(body.keys()):
        await sync_user_schedule(scheduler, current_user.id)

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

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_scheduler.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Run full test suite to catch regressions**

```bash
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/settings.py tests/test_scheduler.py
git commit -m "feat: sync user scheduler job on settings PATCH"
```

---

## Task 5: Set up Vitest for frontend unit tests

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`

The frontend has no test runner yet. Vitest integrates with Vite with minimal config.

- [ ] **Step 1: Install Vitest**

```bash
cd C:/dev/joblin-schedule/frontend
npm install -D vitest
```

- [ ] **Step 2: Add test script to package.json**

In `frontend/package.json`, add `"test": "vitest run"` to scripts:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "preview": "vite preview",
  "test": "vitest run"
},
```

- [ ] **Step 3: Add test config to vite.config.ts**

Replace `frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  test: {
    environment: "node",
  },
});
```

- [ ] **Step 4: Verify Vitest is wired up**

```bash
npm test
```

Expected: `No test files found` (no error — just nothing to run yet).

- [ ] **Step 5: Commit**

```bash
cd C:/dev/joblin-schedule
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts
git commit -m "chore: add vitest for frontend unit tests"
```

---

## Task 6: Create scheduleUtils.ts with tests

**Files:**
- Create: `frontend/src/utils/scheduleUtils.ts`
- Create: `frontend/src/utils/scheduleUtils.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/utils/scheduleUtils.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { presetToCron, describeSchedule, type ScheduleState } from "./scheduleUtils";

const base: ScheduleState = {
  preset: "daily",
  time: "09:00",
  dayOfWeek: 1,
  timezone: "Asia/Kolkata",
  customMode: "interval",
  intervalValue: 4,
  intervalUnit: "hours",
  cronExpression: "0 */4 * * *",
};

describe("presetToCron", () => {
  it("daily at 09:00 → 0 9 * * *", () => {
    expect(presetToCron({ ...base, preset: "daily", time: "09:00" })).toBe("0 9 * * *");
  });

  it("daily at 09:30 → 30 9 * * *", () => {
    expect(presetToCron({ ...base, preset: "daily", time: "09:30" })).toBe("30 9 * * *");
  });

  it("twice_daily at 09:00 → 0 9,21 * * *", () => {
    expect(presetToCron({ ...base, preset: "twice_daily", time: "09:00" })).toBe("0 9,21 * * *");
  });

  it("twice_daily at 22:00 wraps correctly → 0 22,10 * * *", () => {
    expect(presetToCron({ ...base, preset: "twice_daily", time: "22:00" })).toBe("0 22,10 * * *");
  });

  it("every_2_days at 09:00 → 0 9 */2 * *", () => {
    expect(presetToCron({ ...base, preset: "every_2_days", time: "09:00" })).toBe("0 9 */2 * *");
  });

  it("every_3_days at 09:00 → 0 9 */3 * *", () => {
    expect(presetToCron({ ...base, preset: "every_3_days", time: "09:00" })).toBe("0 9 */3 * *");
  });

  it("weekly on Monday (1) at 09:00 → 0 9 * * 1", () => {
    expect(presetToCron({ ...base, preset: "weekly", time: "09:00", dayOfWeek: 1 })).toBe("0 9 * * 1");
  });

  it("weekly on Sunday (0) at 00:00 → 0 0 * * 0", () => {
    expect(presetToCron({ ...base, preset: "weekly", time: "00:00", dayOfWeek: 0 })).toBe("0 0 * * 0");
  });

  it("custom interval hours → 0 */4 * * *", () => {
    expect(presetToCron({ ...base, preset: "custom", customMode: "interval", intervalValue: 4, intervalUnit: "hours" })).toBe("0 */4 * * *");
  });

  it("custom interval days at 09:00 → 0 9 */3 * *", () => {
    expect(presetToCron({ ...base, preset: "custom", customMode: "interval", intervalValue: 3, intervalUnit: "days", time: "09:00" })).toBe("0 9 */3 * *");
  });

  it("custom cron → returned as-is", () => {
    expect(presetToCron({ ...base, preset: "custom", customMode: "cron", cronExpression: "*/15 * * * *" })).toBe("*/15 * * * *");
  });
});

describe("describeSchedule", () => {
  it("daily description mentions time and timezone label", () => {
    const result = describeSchedule({ ...base, preset: "daily", time: "09:00", timezone: "Asia/Kolkata" });
    expect(result).toContain("09:00");
    expect(result).toContain("IST");
  });

  it("weekly description mentions day name", () => {
    const result = describeSchedule({ ...base, preset: "weekly", dayOfWeek: 1 });
    expect(result).toContain("Monday");
  });

  it("twice daily shows both hours", () => {
    const result = describeSchedule({ ...base, preset: "twice_daily", time: "09:00" });
    expect(result).toContain("09:00");
    expect(result).toContain("21:00");
  });

  it("custom interval hours shows count", () => {
    const result = describeSchedule({ ...base, preset: "custom", customMode: "interval", intervalValue: 4, intervalUnit: "hours" });
    expect(result).toContain("4");
    expect(result).toContain("hour");
  });
});
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd C:/dev/joblin-schedule/frontend
npm test
```

Expected: `Cannot find module './scheduleUtils'` — the file doesn't exist yet.

- [ ] **Step 3: Create frontend/src/utils/scheduleUtils.ts**

Create the directory and file:

```ts
export type SchedulePreset =
  | "twice_daily"
  | "daily"
  | "every_2_days"
  | "every_3_days"
  | "weekly"
  | "custom";

export type CustomMode = "interval" | "cron";
export type IntervalUnit = "hours" | "days";

export interface ScheduleState {
  preset: SchedulePreset;
  time: string;          // HH:MM 24-hour
  dayOfWeek: number;     // 0=Sun ... 6=Sat
  timezone: string;      // IANA key
  customMode: CustomMode;
  intervalValue: number;
  intervalUnit: IntervalUnit;
  cronExpression: string; // raw cron, used when preset=custom and customMode=cron
}

export const TIMEZONES: { label: string; iana: string }[] = [
  { label: "IST (UTC+5:30)", iana: "Asia/Kolkata" },
  { label: "UTC", iana: "UTC" },
  { label: "GMT (UTC+0)", iana: "Europe/London" },
  { label: "EST (UTC-5)", iana: "America/New_York" },
  { label: "CST (UTC-6)", iana: "America/Chicago" },
  { label: "PST (UTC-8)", iana: "America/Los_Angeles" },
  { label: "CET (UTC+1)", iana: "Europe/Berlin" },
  { label: "SGT (UTC+8)", iana: "Asia/Singapore" },
  { label: "JST (UTC+9)", iana: "Asia/Tokyo" },
  { label: "AEST (UTC+10)", iana: "Australia/Sydney" },
];

export const PRESETS: { value: SchedulePreset; label: string }[] = [
  { value: "twice_daily", label: "Twice daily" },
  { value: "daily", label: "Daily" },
  { value: "every_2_days", label: "Every 2 days" },
  { value: "every_3_days", label: "Every 3 days" },
  { value: "weekly", label: "Weekly" },
  { value: "custom", label: "Custom" },
];

export const DAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"];
const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

function parseTime(time: string): { hour: number; min: number } {
  const [h, m] = time.split(":").map(Number);
  return { hour: h, min: m };
}

export function presetToCron(state: ScheduleState): string {
  const { hour, min } = parseTime(state.time);

  switch (state.preset) {
    case "twice_daily": {
      const hour2 = (hour + 12) % 24;
      return `${min} ${hour},${hour2} * * *`;
    }
    case "daily":
      return `${min} ${hour} * * *`;
    case "every_2_days":
      return `${min} ${hour} */2 * *`;
    case "every_3_days":
      return `${min} ${hour} */3 * *`;
    case "weekly":
      return `${min} ${hour} * * ${state.dayOfWeek}`;
    case "custom":
      if (state.customMode === "cron") return state.cronExpression;
      if (state.intervalUnit === "hours") return `0 */${state.intervalValue} * * *`;
      return `${min} ${hour} */${state.intervalValue} * *`;
  }
}

export function describeSchedule(state: ScheduleState): string {
  const tzLabel = TIMEZONES.find((t) => t.iana === state.timezone)?.label ?? state.timezone;
  const { hour, min } = parseTime(state.time);
  const minPad = String(min).padStart(2, "0");

  switch (state.preset) {
    case "twice_daily": {
      const hour2 = (hour + 12) % 24;
      const h2Pad = String(hour2).padStart(2, "0");
      return `Runs twice per day at ${state.time} and ${h2Pad}:${minPad} ${tzLabel}.`;
    }
    case "daily":
      return `Runs once per day at ${state.time} ${tzLabel}.`;
    case "every_2_days":
      return `Runs every 2 days at ${state.time} ${tzLabel}.`;
    case "every_3_days":
      return `Runs every 3 days at ${state.time} ${tzLabel}.`;
    case "weekly":
      return `Runs every ${DAY_NAMES[state.dayOfWeek]} at ${state.time} ${tzLabel}.`;
    case "custom":
      if (state.customMode === "cron") return `Custom schedule: ${state.cronExpression}`;
      if (state.intervalUnit === "hours") return `Runs every ${state.intervalValue} hour(s).`;
      return `Runs every ${state.intervalValue} day(s) at ${state.time} ${tzLabel}.`;
  }
}

export function stateFromSettings(s: Record<string, unknown>): ScheduleState {
  return {
    preset: (s.schedule_preset as SchedulePreset) ?? "custom",
    time: (s.schedule_time as string) ?? "06:00",
    dayOfWeek: (s.schedule_day_of_week as number) ?? 1,
    timezone: (s.schedule_timezone as string) ?? "Asia/Kolkata",
    customMode: (s.schedule_custom_mode as CustomMode) ?? "cron",
    intervalValue: (s.schedule_interval_value as number) ?? 4,
    intervalUnit: (s.schedule_interval_unit as IntervalUnit) ?? "hours",
    cronExpression: (s.schedule_cron as string) ?? "0 */4 * * *",
  };
}

export function stateToSettingsPayload(state: ScheduleState): Record<string, unknown> {
  return {
    schedule_preset: state.preset,
    schedule_time: state.time,
    schedule_day_of_week: state.dayOfWeek,
    schedule_timezone: state.timezone,
    schedule_custom_mode: state.customMode,
    schedule_interval_value: state.intervalValue,
    schedule_interval_unit: state.intervalUnit,
    schedule_cron: presetToCron(state),
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/dev/joblin-schedule/frontend
npm test
```

Expected:
```
✓ scheduleUtils.test.ts (15 tests)
Test Files  1 passed (1)
Tests  15 passed (15)
```

- [ ] **Step 5: Commit**

```bash
cd C:/dev/joblin-schedule
git add frontend/src/utils/scheduleUtils.ts frontend/src/utils/scheduleUtils.test.ts
git commit -m "feat: add scheduleUtils with presetToCron and describeSchedule"
```

---

## Task 7: Rewrite the Settings.tsx schedule tab

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

Replace lines 1-4 (imports) and lines 122-137 (the schedule tab content). All other tabs are untouched.

- [ ] **Step 1: Add the scheduleUtils import**

At the top of `frontend/src/pages/Settings.tsx`, add the import after the existing imports:

```tsx
import {
  type ScheduleState,
  PRESETS,
  TIMEZONES,
  DAY_LABELS,
  describeSchedule,
  stateFromSettings,
  stateToSettingsPayload,
} from "@/utils/scheduleUtils";
```

- [ ] **Step 2: Add the ScheduleTab component**

Add this function just above the `export function Settings()` declaration (line 8):

```tsx
function ScheduleTab({
  settings,
  onSave,
}: {
  settings: Record<string, unknown>;
  onSave: (data: Record<string, unknown>) => void;
}) {
  const [state, setState] = useState<ScheduleState>(() => stateFromSettings(settings));

  function save(next: ScheduleState) {
    onSave(stateToSettingsPayload(next));
  }

  function update(partial: Partial<ScheduleState>, saveNow = true) {
    const next = { ...state, ...partial };
    setState(next);
    if (saveNow) save(next);
  }

  const showTime =
    state.preset !== "custom" || (state.preset === "custom" && state.customMode === "interval" && state.intervalUnit === "days");
  const showTimezone = showTime;
  const showDayPicker = state.preset === "weekly";

  return (
    <div className="space-y-4 max-w-sm">
      {/* Preset chips */}
      <div>
        <div className="text-xs text-[#666] uppercase tracking-wider mb-2">Run frequency</div>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.value}
              onClick={() => update({ preset: p.value })}
              className={`px-3 py-1 rounded-full text-xs border transition-colors ${
                state.preset === p.value
                  ? "border-[#4e9eff] text-[#4e9eff] bg-[#0e2040]"
                  : "border-[#2a2a2a] text-[#666] hover:border-[#444] hover:text-[#888]"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Contextual panel */}
      <div className="bg-[#0a0a0a] border border-[#1e1e1e] rounded-lg p-3 space-y-3">
        {/* Weekly: day picker */}
        {showDayPicker && (
          <div>
            <div className="text-xs text-[#666] mb-1.5">Day</div>
            <div className="flex gap-1.5">
              {DAY_LABELS.map((label, i) => (
                <button
                  key={i}
                  onClick={() => update({ dayOfWeek: i })}
                  className={`w-7 h-7 rounded-full text-xs font-medium border transition-colors ${
                    state.dayOfWeek === i
                      ? "border-[#4e9eff] text-[#4e9eff] bg-[#0e2040]"
                      : "border-[#2a2a2a] text-[#555] hover:border-[#444]"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Custom: interval builder or cron input */}
        {state.preset === "custom" && (
          <div>
            {state.customMode === "interval" ? (
              <div>
                <div className="text-xs text-[#666] mb-1.5">Every</div>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    value={state.intervalValue}
                    onChange={(e) => setState((s) => ({ ...s, intervalValue: parseInt(e.target.value) || 1 }))}
                    onBlur={() => save(state)}
                    className="w-14 bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-sm text-[#e5e5e5] text-center"
                  />
                  <select
                    value={state.intervalUnit}
                    onChange={(e) => update({ intervalUnit: e.target.value as "hours" | "days" })}
                    className="bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]"
                  >
                    <option value="hours">hours</option>
                    <option value="days">days</option>
                  </select>
                </div>
                <button
                  onClick={() => update({ customMode: "cron" })}
                  className="text-xs text-[#4e4e88] underline mt-2"
                >
                  Switch to cron expression →
                </button>
              </div>
            ) : (
              <div>
                <div className="text-xs text-[#666] mb-1.5">Cron expression</div>
                <input
                  type="text"
                  defaultValue={state.cronExpression}
                  onBlur={(e) => update({ cronExpression: e.target.value })}
                  className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-1.5 text-sm text-[#e5e5e5] font-mono"
                  placeholder="0 */4 * * *"
                />
                <button
                  onClick={() => update({ customMode: "interval" })}
                  className="text-xs text-[#4e4e88] underline mt-2"
                >
                  ← Back to interval builder
                </button>
              </div>
            )}
          </div>
        )}

        {/* Time + timezone row */}
        {showTime && (
          <div className="flex gap-3 items-end">
            <div>
              <div className="text-xs text-[#666] mb-1.5">Run at</div>
              <input
                type="time"
                value={state.time}
                onChange={(e) => setState((s) => ({ ...s, time: e.target.value }))}
                onBlur={() => save(state)}
                className="bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-sm text-[#e5e5e5] font-mono"
              />
            </div>
            {showTimezone && (
              <div>
                <div className="text-xs text-[#666] mb-1.5">Timezone</div>
                <select
                  value={state.timezone}
                  onChange={(e) => update({ timezone: e.target.value })}
                  className="bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]"
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz.iana} value={tz.iana}>{tz.label}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}

        {/* Plain-English description */}
        <div className="text-xs text-[#555]">{describeSchedule(state)}</div>
      </div>

      {/* Staleness threshold */}
      <div>
        <div className="text-xs text-[#666] mb-1.5">Skip if last run was within</div>
        <div className="flex items-center gap-2">
          <input
            type="number"
            defaultValue={(settings.staleness_threshold_hours as number) ?? 4}
            onBlur={(e) => onSave({ staleness_threshold_hours: parseFloat(e.target.value) })}
            className="w-16 bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-sm text-[#e5e5e5] text-center"
          />
          <span className="text-xs text-[#666]">hours</span>
        </div>
      </div>

      {/* Enable toggle */}
      <label className="flex items-center gap-2 text-xs text-[#888] cursor-pointer">
        <input
          type="checkbox"
          defaultChecked={!!(settings.scheduler_enabled)}
          onChange={(e) => onSave({ scheduler_enabled: e.target.checked })}
        />
        Scheduler enabled
      </label>
    </div>
  );
}
```

- [ ] **Step 3: Replace the schedule tab render**

In the `Settings` function, find the schedule tab block (currently lines 122-137):

```tsx
      {tab === "schedule" && (
        <div className="space-y-3 max-w-sm">
          <label className="block text-xs text-[#888]">Cron expression</label>
          <input defaultValue={(s.schedule_cron as string) || "0 */4 * * *"}
            onBlur={(e) => update.mutate({ schedule_cron: e.target.value })}
            className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] font-mono" />
          <label className="block text-xs text-[#888]">Staleness threshold (hours)</label>
          <input type="number" defaultValue={(s.staleness_threshold_hours as number) ?? 4}
            onBlur={(e) => update.mutate({ staleness_threshold_hours: parseFloat(e.target.value) })}
            className="w-32 bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
          <label className="flex items-center gap-2 text-xs text-[#888] cursor-pointer">
            <input type="checkbox" defaultChecked={!!s.scheduler_enabled} onChange={(e) => update.mutate({ scheduler_enabled: e.target.checked })} />
            Enable scheduler
          </label>
        </div>
      )}
```

Replace it with:

```tsx
      {tab === "schedule" && (
        <ScheduleTab
          settings={s}
          onSave={(data) => update.mutate(data)}
        />
      )}
```

- [ ] **Step 4: Check TypeScript compiles**

```bash
cd C:/dev/joblin-schedule/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Run frontend tests to confirm nothing broke**

```bash
npm test
```

Expected: 15 tests pass.

- [ ] **Step 6: Commit**

```bash
cd C:/dev/joblin-schedule
git add frontend/src/pages/Settings.tsx frontend/src/utils/scheduleUtils.ts frontend/src/utils/scheduleUtils.test.ts
git commit -m "feat: replace cron input with preset chips and timezone selector"
```

---

## Self-Review Checklist

- [x] **schedule_timezone** flows from frontend → PATCH body → `sync_user_schedule` → `CronTrigger(timezone=tz)` ✓
- [x] **Per-user job IDs** (`scrape_cron_{user_id}`) created in `_schedule_user_job`, not a single `"scrape_cron"` ✓
- [x] **Migration safety**: existing users with no `schedule_preset` get default `"custom"/"cron"` showing their existing cron ✓ (via `stateFromSettings` defaults and config DEFAULTS)
- [x] **`_run_scrape_job` no longer hardcodes user_id=1** ✓
- [x] **Settings router guards**: `getattr(request.app.state, "scheduler", None)` prevents test failures when no scheduler is running ✓
- [x] **Staleness threshold** is preserved on the schedule tab (not removed) ✓
- [x] **Enable toggle** fires `onSave({ scheduler_enabled: ... })` which triggers the sync hook ✓ (because `scheduler_enabled` is in `SCHEDULE_KEYS`)
