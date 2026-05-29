# Skills Insights Feature Design

**Date:** 2026-05-29
**Status:** Approved

## Overview

A manual, ever-evolving feature that lets the user select matched jobs, send their full JDs to an LLM, and accumulate a ranked list of skills most frequently demanded by roles that suit their profile. Each skill entry briefly cites which companies and roles asked for it.

---

## Data Model

### New table: `job_skills`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `job_id` | int FK -> jobs.id | |
| `skill_name` | str | LLM-canonical name, e.g. "PostgreSQL" |
| `created_at` | datetime | server default now() |

- Unique constraint on `(job_id, skill_name)` - prevents duplicates within a single job and acts as the deduplication anchor across runs.
- Index on `skill_name` for fast `GROUP BY` aggregation.
- Index on `job_id` for O(1) dedup check (if any row exists for a job_id, the job is already analyzed).

### Reset behavior

`job_skills` is excluded from the Danger tab reset alongside `token_usage`. Insights accumulate independently of job/run data and should survive a job data reset.

---

## Backend

### New router: `backend/routers/insights.py`

Registered at `/api/insights`.

#### `POST /insights/analyze`

Request body: `{ "match_ids": [int] }`

1. For each match_id, load the corresponding job.
2. Check if any `job_skills` row exists for that `job_id` - if yes, mark as skipped.
3. For new jobs: call `extract_skills(title, description)` on the filter provider.
4. Save results as `job_skills` rows, relying on the unique constraint to silently discard any duplicates (via `on_conflict_do_nothing`).
5. Return `{ "analyzed": N, "skipped": N, "skills_found": N }`.

Called once per match from the frontend loop (not batched), enabling per-job progress updates in the UI.

#### `GET /insights/skills`

Returns `[{ "name": str, "count": int }]` sorted by count descending. Used for the ranked skill list.

#### `GET /insights/skills/{name}/citations`

Returns `[{ "company_name": str, "job_title": str }]` for the given skill name. Used for the expandable citation list.

### LLM integration

New method `extract_skills(title: str, description: str) -> list[str]` added to `GroqAdapter`, `CerebrasAdapter`, and `GeminiAdapter`.

New prompt `build_skills_prompt(title, description)` added to `backend/llm/prompts.py`. The prompt instructs the LLM to:
- Output a JSON array of canonical skill name strings only.
- Include technical skills: languages, frameworks, tools, platforms, databases, cloud services.
- Include specific domain skills: "system design", "distributed systems", "event-driven architecture", "API design", etc.
- Exclude generic soft skills: communication, ownership, leadership, collaboration.
- Use standardized canonical names (e.g., always "PostgreSQL", never "Postgres"; always "React", never "React.js").

Token usage is recorded with `call_type="skills"` in the existing `token_usage` table via the same `_provider_name()` + `last_usage` pattern used in `pipeline.py`.

---

## Frontend

### Matches page (`Matches.tsx`)

When `selected.size > 0`, an "Analyze skills" button appears alongside the existing "Re-notify" button. On click, the user is navigated to `/insights?analyze=<comma-separated match IDs>`. No inline result is shown on the Matches page.

### Insights page (`/insights`, new `Insights.tsx`)

#### Analysis flow (triggered by `?analyze=` query param)

On mount, if `?analyze=...` is present:
1. Parse the match IDs from the query string.
2. Loop through them one at a time, calling `POST /api/insights/analyze` with a single match ID per call.
3. Show a progress line updated per job: "Analyzing 3 of 7: Senior Backend Engineer at Stripe..."
4. After each call, refetch the skills list - counts climb and new skills appear incrementally.
5. On completion, clear the `?analyze=` param from the URL and show: "Done - analyzed N, skipped M already processed."

#### Skills table

Always visible (even during analysis). Shows:
- A header: total skills tracked, total unique jobs analyzed.
- Ranked rows: rank number, skill name, count badge (e.g. `12`).
- Clicking a count badge expands an inline citations list showing company name + job title pairs for that skill. Collapses on second click.

### Routing and navigation

- New sidebar entry: `{ label: "Insights", icon: "◎", path: "/insights" }` - positioned between Usage and Settings.
- New route in `App.tsx`: `<Route path="/insights" element={<Insights />} />`.
- New title entry in `Layout.tsx`: `"/insights": "Insights"`.

---

## Error handling

- If the LLM returns malformed JSON from `extract_skills`, the job is skipped and the error is logged server-side. The frontend receives `analyzed: 0, skipped: 0, skills_found: 0` for that job and continues the loop.
- If the analyze call fails entirely (network/500), the frontend shows an inline error for that job and continues processing remaining jobs.

---

## Out of scope

- Automatic analysis on new matches (manual trigger only).
- Skill editing or merging in the UI.
- Filtering the insights by time range or company.
- Export of skills data.
