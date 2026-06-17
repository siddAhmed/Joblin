# Match Dismiss Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Dismiss" button that permanently hides a match from the user's view without generating negative matching signals, while leaving "Not interested" unchanged.

**Architecture:** One nullable `hidden_at` column on `Match`; the list endpoint gains a `WHERE hidden_at IS NULL` filter; a new `POST /matches/{id}/dismiss` endpoint sets it; the frontend adds a Dismiss button in the expanded row and updates bulk dismiss to use the new path.

**Tech Stack:** Python/FastAPI/SQLAlchemy async (backend), Alembic (migrations), React/TypeScript/TanStack Query (frontend)

## Global Constraints

- `hidden_at` is nullable, no server default -- existing rows unaffected, no backfill.
- Dismissed matches are permanently hidden; no undo.
- `POST /jobs/{job_id}/dismiss` ("Not interested") is unchanged -- behavior, FeedbackExample creation, UI button placement all stay as-is.
- Ownership of a match is verified by joining through `Job` (`Job.user_id == current_user.id`); `Match` has no direct `user_id`.

---

### Task 1: Add `hidden_at` to Match model and migrate

**Files:**
- Modify: `backend/models/match.py`
- Create: `backend/alembic/versions/<generated-id>_add_hidden_at_to_matches.py`

**Interfaces:**
- Produces: `Match.hidden_at: Mapped[datetime | None]` (consumed by Task 2)

- [ ] **Step 1: Add `hidden_at` to the Match model**

In `backend/models/match.py`, add the field after `not_interested_at`:

```python
hidden_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

The updated column block should look like:

```python
notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
not_interested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
hidden_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

No import changes needed -- `DateTime`, `Mapped`, and `mapped_column` are already imported.

- [ ] **Step 2: Generate the Alembic migration**

```bash
cd C:\dev\joblin\backend
alembic revision --autogenerate -m "add_hidden_at_to_matches"
```

Open the generated file in `backend/alembic/versions/`. Verify it contains exactly this and nothing more:

```python
def upgrade() -> None:
    op.add_column('matches', sa.Column('hidden_at', sa.DateTime(), nullable=True))

def downgrade() -> None:
    op.drop_column('matches', 'hidden_at')
```

If autogenerate added anything else, remove it -- only this one column change belongs here.

- [ ] **Step 3: Run the migration**

```bash
cd C:\dev\joblin\backend
alembic upgrade head
```

Expected: last line reads `Running upgrade <prev_id> -> <new_id>, add_hidden_at_to_matches`

- [ ] **Step 4: Verify the column exists**

```bash
cd C:\dev\joblin\backend
python -c "
import asyncio
from sqlalchemy import text
from backend.database import engine

async def check():
    async with engine.connect() as conn:
        result = await conn.execute(text('PRAGMA table_info(matches)'))
        cols = [row[1] for row in result.all()]
        assert 'hidden_at' in cols, 'hidden_at column missing!'
        print('OK:', cols)

asyncio.run(check())
"
```

Expected: prints `OK:` followed by column list including `hidden_at`.

- [ ] **Step 5: Commit**

```bash
git add backend/models/match.py backend/alembic/versions/
git commit -m "feat: add hidden_at to matches for dismiss-from-view"
```

---

### Task 2: Dismiss endpoint + list filter

**Files:**
- Modify: `backend/routers/matches.py`

**Interfaces:**
- Consumes: `Match.hidden_at` (Task 1)
- Produces: `POST /matches/{match_id}/dismiss` → `{"status": "dismissed"}`; `GET /matches` silently excludes rows where `hidden_at IS NOT NULL`

- [ ] **Step 1: Add `HTTPException` to imports if missing**

Check the top of `backend/routers/matches.py`. The `from fastapi import ...` line must include `HTTPException`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
```

Add `HTTPException` if it is not already there.

- [ ] **Step 2: Add `WHERE hidden_at IS NULL` to the list query**

Find the `stmt = (select(Match, Job, Company)...)` block. Add `.where(Match.hidden_at == None)` immediately after `.where(Company.user_id == current_user.id)`:

```python
stmt = (
    select(Match, Job, Company)
    .join(Job, Match.job_id == Job.id)
    .join(Company, Job.company_id == Company.id)
    .where(Company.user_id == current_user.id)
    .where(Match.hidden_at == None)
    .order_by(Match.created_at.desc())
)
```

- [ ] **Step 3: Add the dismiss endpoint**

Append to the end of `backend/routers/matches.py`:

```python
@router.post("/{match_id}/dismiss")
async def dismiss_match(match_id: int, session: Session, current_user: CurrentUser):
    match = (await session.execute(
        select(Match)
        .join(Job, Match.job_id == Job.id)
        .where(Match.id == match_id, Job.user_id == current_user.id)
    )).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    match.hidden_at = datetime.now(timezone.utc)
    await session.commit()
    return {"status": "dismissed"}
```

`Job`, `datetime`, and `timezone` are already imported in this file -- no new imports needed.

- [ ] **Step 4: Verify manually**

Start the backend. Get a real match ID from the list, then dismiss it:

```bash
# List matches (get a match id from the output)
curl -s http://localhost:8000/matches -H "Authorization: Bearer <token>"

# Dismiss match id 5 (replace with a real id)
curl -X POST http://localhost:8000/matches/5/dismiss -H "Authorization: Bearer <token>"
# Expected: {"status":"dismissed"}

# Confirm it no longer appears in the list
curl -s http://localhost:8000/matches -H "Authorization: Bearer <token>"
# Match id 5 must not appear

# Confirm 404 for wrong user or non-existent match
curl -X POST http://localhost:8000/matches/99999/dismiss -H "Authorization: Bearer <token>"
# Expected: 404
```

- [ ] **Step 5: Commit**

```bash
git add backend/routers/matches.py
git commit -m "feat: add dismiss endpoint and filter hidden matches from list"
```

---

### Task 3: Frontend -- API method, Dismiss button, bulk update

**Files:**
- Modify: `frontend/src/api/matches.ts`
- Modify: `frontend/src/pages/Matches.tsx`

**Interfaces:**
- Consumes: `POST /matches/{match_id}/dismiss` (Task 2)
- Produces: `matchesApi.dismiss(match_id)` callable; "Dismiss" button in expanded row; bulk `✕ Dismiss` uses new endpoint

- [ ] **Step 1: Add `dismiss` to `matchesApi`**

In `frontend/src/api/matches.ts`, add `dismiss` to the exported object:

```typescript
export const matchesApi = {
  list: (params?: { tier?: string; limit?: number; offset?: number }) =>
    api.get<Match[]>("/matches", { params }).then((r) => r.data),
  notify: (match_ids: number[]) => api.post("/matches/notify", { match_ids }).then((r) => r.data),
  dismiss: (match_id: number) => api.post(`/matches/${match_id}/dismiss`).then((r) => r.data),
};
```

- [ ] **Step 2: Add `hideMatch` mutation to `MatchRow`**

In `frontend/src/pages/Matches.tsx`, inside the `MatchRow` component, add a second mutation after the existing `dismiss` mutation (which handles "Not interested"):

```typescript
const hideMatch = useMutation({
  mutationFn: () => matchesApi.dismiss(match.id),
  onSuccess: () => qc.invalidateQueries({ queryKey: ["matches"] }),
});
```

`matchesApi` is already imported at the top of this file (`import { matchesApi } from "@/api/matches"`).

- [ ] **Step 3: Add "Dismiss" button in the expanded action row**

Find the `<div className="flex gap-2 mt-3">` block inside the expanded section of `MatchRow`. Add the Dismiss button before "Not interested":

```tsx
<button
  onClick={() => hideMatch.mutate()}
  disabled={hideMatch.isPending}
  className="text-[11px] border border-[#2a2a2a] rounded px-2 py-1 text-[#888] hover:text-red-400"
>
  Dismiss
</button>
<button onClick={() => dismiss.mutate()} className="text-[11px] border border-[#2a2a2a] rounded px-2 py-1 text-[#888] hover:text-[#ccc]">Not interested</button>
```

- [ ] **Step 4: Update bulk `✕ Dismiss` to use `matchesApi.dismiss`**

Find the `✕ Dismiss` button in the bulk toolbar section of the `Matches` function. It currently calls `jobsApi.dismiss(m.job_id)`. Replace the `onClick` handler:

```tsx
<button
  className="text-xs px-3 py-1 border border-[#1e1e1e] rounded text-[#666] hover:text-red-400 hover:border-red-900/60"
  onClick={() => {
    const toDismiss = matches.filter((m) => selected.has(m.id));
    Promise.all(toDismiss.map((m) => matchesApi.dismiss(m.id)))
      .then(() => qc.invalidateQueries({ queryKey: ["matches"] }))
      .catch(() => {});
  }}
>
  ✕ Dismiss
</button>
```

- [ ] **Step 5: Verify in browser**

Start the frontend dev server (`npm run dev` in `frontend/`). Navigate to `/matches`:

1. Expand any match row -- confirm a "Dismiss" button appears to the left of "Not interested"
2. Click "Dismiss" -- the row disappears immediately from the list
3. Navigate to Dashboard -- the dismissed match does not appear in Recent Matches (the API filter handles this automatically)
4. Select 2+ matches via checkboxes and click `✕ Dismiss` in the toolbar -- all selected rows disappear
5. Verify "Not interested" still works: clicking it still calls the jobs dismiss endpoint (you can confirm in the network tab -- it should hit `/jobs/{job_id}/dismiss`, not `/matches/{id}/dismiss`), and the match remains visible (this is expected -- "Not interested" is a signal tool, not a view tool)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/matches.ts frontend/src/pages/Matches.tsx
git commit -m "feat: add Dismiss button to match row and update bulk dismiss"
```
