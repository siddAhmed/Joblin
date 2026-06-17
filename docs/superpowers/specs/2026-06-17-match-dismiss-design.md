# Match Dismiss Design

**Date:** 2026-06-17
**Status:** Approved

## Problem

The Matches section accumulates every match ever found with no way to clean it up. The existing "Not interested" button creates a negative `FeedbackExample` that suppresses similar roles in future pipeline runs -- wrong tool for aspirational roles the user likes but cannot apply to yet (e.g., overqualified YOE requirement). Users need a neutral "remove from view" action that has no effect on future matching signals.

Additionally, in the future Joblin will move to a shared jobs DB across users; the dismiss action must operate on the per-user `Match` record, not the shared `Job` record.

## Scope

- Add a "Dismiss" action that hides a match from the user's list permanently.
- "Not interested" is unchanged in behavior and UI placement.
- No undelete/undo; dismissed matches are gone from the user's view.
- Bulk dismiss in the Matches toolbar is updated to use the new dismiss path (not the not-interested path).

## Data Model

Add one nullable column to `matches`:

```
hidden_at: DateTime | None  (default NULL)
```

A new Alembic migration sets `hidden_at` as nullable with no server default. All existing rows remain `NULL`; no backfill required. The `Job` record is untouched, preserving visibility for other users.

## Backend

### New endpoint

```
POST /matches/{match_id}/dismiss
```

- Ownership verified by joining through `Job` (`match.job.user_id == current_user.id`); returns 404 if match not found or owned by another user.
- Sets `match.hidden_at = utcnow()`.
- Commits. Returns `{"status": "dismissed"}`.
- Does **not** create a `FeedbackExample` -- this is the key behavioral difference from `POST /jobs/{job_id}/dismiss`.

### List filter

The `GET /matches` query gains a `WHERE hidden_at IS NULL` clause. Hidden matches are excluded from all responses; no opt-in parameter to retrieve them.

## Frontend

### API layer (`frontend/src/api/matches.ts`)

Add:
```ts
dismiss: (match_id: number) => api.post(`/matches/${match_id}/dismiss`).then(r => r.data)
```

### Match row (`frontend/src/pages/Matches.tsx`)

Add a "Dismiss" button in the expanded match row alongside "Not interested". On success, invalidates `["matches"]` query so the row disappears immediately.

### Bulk toolbar (`frontend/src/pages/Matches.tsx`)

The existing `✕ Dismiss` bulk action currently calls `jobsApi.dismiss` (the not-interested path). Update it to call `matchesApi.dismiss` per selected match so bulk-dismiss hides without generating negative signals.

## What does not change

- `POST /jobs/{job_id}/dismiss` ("Not interested") -- behavior, signals, FeedbackExample creation all unchanged.
- The "Not interested" button in the expanded match row -- unchanged.
- Dashboard recent matches -- already filtered by the `/matches` endpoint, so dismissed rows disappear there automatically.
