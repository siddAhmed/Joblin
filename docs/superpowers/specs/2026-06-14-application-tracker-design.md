# Application Tracker Design

**Date:** 2026-06-14
**Status:** Approved

## Overview

A dedicated Applications page for tracking jobs the user is interested in, has applied to, or heard back from. Covers both Joblin-discovered jobs and external applications the user found themselves. Includes a stats dashboard at the top and bulk selection support on both the Matches and Applications pages.

---

## Data Model

One new table: `application_tracking`.

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `job_id` | int FK nullable | References `jobs.id`. Null for external jobs. |
| `company_name` | str | Denormalized for display and external jobs. |
| `job_title` | str | Denormalized for display and external jobs. |
| `url` | str nullable | Job posting URL. |
| `applied_date` | date nullable | Null until status reaches `applied`. |
| `notes` | str nullable | Free-text user notes. |
| `status` | enum | `interested / applied / rejected / offer` |
| `source` | enum | `joblin / external`. Derived from `job_id` but stored explicitly for query simplicity. |
| `created_at` | datetime | |
| `updated_at` | datetime | |

For Joblin-discovered jobs, `company_name` and `job_title` are copied from the `Job` record at creation time so the Applications page can display them without joins.

---

## Backend API

New router: `backend/routers/applications.py`, mounted at `/api/applications`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/applications` | List all. Query params: `status`, `source`, `search` (company or title). |
| `POST` | `/api/applications` | Create a single entry. Used by Matches buttons and external job form. |
| `PATCH` | `/api/applications/{id}` | Update `status`, `notes`, `applied_date`. |
| `DELETE` | `/api/applications/{id}` | Remove a single entry. |
| `POST` | `/api/applications/bulk` | Bulk update/delete for the Applications page. Body: `{ ids: int[], action: "status_change" \| "delete", status?: string }`. `ids` are `application_tracking` primary keys. |
| `GET` | `/api/applications/stats` | Returns counts by status, source split, and a per-day series (last 30 days) for the chart. |

---

## Frontend

### New files

- `frontend/src/pages/Applications.tsx` - Applications page
- `frontend/src/api/applications.ts` - API calls (list, create, update, delete, bulkAction, stats)

### Modified files

- `frontend/src/components/Sidebar.tsx` - Add "Applications" nav item between Matches and Jobs
- `frontend/src/pages/Matches.tsx` - Replace "Apply" button with three buttons + add bulk selection
- Router file - Add `/applications` route pointing to `Applications.tsx`

---

## Matches Page Changes

Replace the existing "Apply" button on each match card with three new buttons:

- **View JD** - Opens `job.url` in a new tab. No API call.
- **Interested** - Calls `POST /api/applications` with `status=interested`, `source=joblin`. Button turns purple/filled on success to indicate it's tracked.
- **Applied** - Calls `POST /api/applications` with `status=applied`, `source=joblin`. Button turns blue/filled on success.

If a job is already in `application_tracking`, the relevant button shows as filled/active and clicking it again does nothing (idempotent).

**Bulk selection on Matches:**

- Checkbox appears on each match card (top-left corner) on hover.
- Selecting one or more cards shows a sticky bulk action bar at the bottom of the page.
- Bulk actions available: "Mark Interested", "Mark Applied", "Dismiss".
- "Mark Interested" / "Mark Applied" fires individual `POST /api/applications` calls in parallel (one per selected job). This avoids mixing job_ids and application_tracking ids in the bulk endpoint.
- "Dismiss" uses the existing dismiss logic.

---

## Applications Page

### Stats Dashboard (top)

Six stat cards in a row: **Total**, **Interested**, **Applied**, **Rejected**, **Offer**, **Response Rate** (Offer / Applied, as a percentage).

Two charts below the cards:

- **Applications Over Time** (left, wider) - Bar chart of applications per day over the last 30 days. Bars colored by status: blue = applied, purple = interested.
- **Joblin vs External** (right, narrower) - Two labeled bars showing count and percentage split.

### Applications Table

**Filter tabs:** All | Interested | Applied | Rejected | Offer (with count badges).

**Controls row:** Source dropdown (All / Joblin / External) + search input + "Add External Job" button (top-right).

**Table columns:** Status badge | Company | Role | Applied date | Source pill | LLM Score (Joblin jobs only, dash for external) | Notes (truncated) | Actions.

**Inline status change:** Clicking the status badge on any row opens a small dropdown to change status. Changing status to "applied" prompts for an applied date if not set.

**Bulk selection:**

- Checkbox in each row (leftmost column).
- Selecting one or more rows shows a bulk action bar above the table.
- Bulk actions: status change (any status) and delete.
- Calls `POST /api/applications/bulk`.

### Add External Job Modal

Triggered by "Add External Job" button. Fields:

- Company name (required)
- Job title (required)
- URL (optional)
- Status (select, defaults to "Applied")
- Date Applied (date picker, shown only when status is Applied/Rejected/Offer)
- Notes (optional textarea)

On submit: calls `POST /api/applications` with `source=external`.

---

## Key Behaviors

- A Joblin job can only have one `application_tracking` entry. Clicking "Interested" then "Applied" updates the existing record rather than creating a second one (upsert by `job_id`).
- The Matches page "Interested" and "Applied" buttons reflect current tracker state on load - if a job is already tracked, the matching button shows as active.
- Deleting a tracker entry from the Applications page does not affect the underlying `Job` or `Match` records.
- The Matches page buttons always upsert: clicking "Interested" on an already-tracked job sets it back to interested; clicking "Applied" advances it to applied. Full status control (including corrections) is available on the Applications page via the inline status dropdown.
- Notes can only be added or edited from the Applications page.
