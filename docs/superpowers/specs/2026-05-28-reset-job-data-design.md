# Reset Job Data Design

**Goal:** Add a "Reset job data" action that wipes all scraped job history so the user can start fresh without losing company list, settings, or token usage history.

**Architecture:** A single `POST /api/admin/reset` endpoint deletes rows from five tables in FK-safe order. A new Danger tab in Settings exposes the action behind an inline confirmation gate (user must type `RESET`). On success the frontend invalidates all affected queries so the UI reflects empty state immediately.

---

## What gets wiped

| Table | Wiped | Reason |
|---|---|---|
| `jobs` | Yes | Core job history |
| `matches` | Yes | Depends on jobs |
| `runs` | Yes | Run history |
| `run_company_results` | Yes | Depends on runs |
| `feedback_examples` | Yes | Depends on jobs; feedback signals become stale anyway |
| `companies` | No | User curated, expensive to rebuild |
| `settings` | No | API keys, Discord config, criteria |
| `token_usage` | No | Historical spend data; run_id values become orphaned references but the Usage page reads token_usage directly without joining runs, so display is unaffected |

---

## Backend

**File:** `backend/routers/admin.py` (new)

Endpoint: `POST /api/admin/reset`

Deletion order (FK-safe):
1. `feedback_examples` (references jobs)
2. `matches` (references jobs and runs)
3. `run_company_results` (references runs and companies)
4. `jobs` (references companies)
5. `runs`

Response:
```json
{
  "deleted": {
    "feedback_examples": 12,
    "matches": 34,
    "run_company_results": 8,
    "jobs": 210,
    "runs": 3
  }
}
```

Register in `backend/main.py` under `/api` prefix.

---

## Frontend

**File:** `frontend/src/pages/Settings.tsx` (modify)

Add `"danger"` to the `Tab` union and the tabs array. The Danger tab renders one section:

- Heading: "Reset job data"
- Description: lists exactly what is deleted and what is kept (one line each)
- Red "Reset job data" button that reveals an inline confirmation form
- Confirmation form: text input with placeholder `Type RESET to confirm`, a red confirm button (disabled until input equals `RESET` exactly), and a cancel link
- On confirm: calls `POST /api/admin/reset`, then invalidates `["runs"]`, `["jobs"]`, `["matches"]`, `["stats"]` queries and resets the input state
- On error: shows error message inline

No new API file needed -- the call is a one-liner added directly in the component via the existing `api` axios instance.

---

## Error handling

- If the endpoint fails mid-deletion (unlikely with SQLite), return a 500 with which tables were cleared before the failure. The frontend shows the error message inline.
- The confirmation input prevents accidental clicks. No additional rate limiting needed for a single-user self-hosted app.
