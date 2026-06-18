# Shared Job Catalog Design

**Date:** 2026-06-18
**Status:** Approved

## Problem

Each user gets their own copy of the 130-company default catalog and their own `jobs` rows with raw descriptions. At 3 users this is harmless; at 30 users the same ATS endpoints get hit 30× per cycle, raw descriptions are stored 30×, and careers pages start throttling or IP-blocking the scraper. LLM calls and heuristic filtering are intentionally per-user and must stay that way.

## Goal

Scrape each company once per cycle, store raw job data once, and run per-user heuristic + LLM processing against the shared raw data.

---

## Schema

### New shared tables

**`company_catalog`** (replaces per-user `companies`)

| Column | Notes |
|--------|-------|
| `id` | PK |
| `name` | |
| `careers_url` | UNIQUE |
| `ats_type` | enum: greenhouse, lever, ashby, workable, smartrecruiters, workday, crawl4ai, custom |
| `ats_identifier` | |
| `custom_api_url` | |
| `css_selector` | |
| `is_active` | global toggle |
| `quarantine_count` | |
| `quarantined_at` | |
| `quarantine_reason` | |
| `discovery_status` | |
| `discovery_message` | |
| `source` | enum: `default` \| `user_submitted` |
| `last_scraped_at` | updated after each successful scrape |
| `created_at` | |
| `updated_at` | |

All scraping config is canonical — no per-user overrides. Quarantine is global (if a site is down, it's down for everyone).

**`raw_jobs`** (global scraped data)

| Column | Notes |
|--------|-------|
| `id` | PK |
| `catalog_company_id` | FK → `company_catalog` |
| `job_id` | string from ATS |
| `title` | |
| `location` | |
| `url` | |
| `raw_description` | |
| `normalized_title` | lowercase, alphanumeric — deterministic, compute once |
| `normalized_location` | |
| `seniority` | derived from title regex — deterministic |
| `first_seen_at` | |
| `last_seen_at` | |
| `is_active` | still appearing on careers page |

UNIQUE on `(catalog_company_id, job_id)`.

### Modified per-user tables

**`user_companies`** (replaces `companies`, now a junction table)

| Column | Notes |
|--------|-------|
| `id` | PK |
| `user_id` | FK → `users` |
| `catalog_id` | FK → `company_catalog` |
| `is_active` | user's toggle, independent of catalog |
| `created_at` | |

UNIQUE on `(user_id, catalog_id)`.

**`user_jobs`** (replaces `jobs`)

| Column | Notes |
|--------|-------|
| `id` | PK |
| `user_id` | FK → `users` |
| `raw_job_id` | FK → `raw_jobs` |
| `run_id` | FK → `runs` — the run that first surfaced this job for this user |
| `passed_heuristic` | bool |
| `preview_only` | bool |
| `first_seen_at` | |

UNIQUE on `(user_id, raw_job_id)`.

### Unchanged tables (FK updates only)

| Table | FK change |
|-------|-----------|
| `matches` | `job_id` → `user_jobs.id` |
| `feedback_examples` | `job_id` → `user_jobs.id` |
| `application_tracking` | `job_id` → `user_jobs.id` |
| `run_company_results` | `company_id` → `company_catalog.id` |

`runs`, `settings`, `token_usage`, `resume`, `application_tracking` are otherwise unchanged.

---

## Pipeline

The current single-pass pipeline splits into two sequential phases per run.

### Phase 1 — Scrape (shared)

For each company in the run's scope:

- **Manual run:** always scrape regardless of `last_scraped_at`
- **Scheduled run:** read `company_catalog.last_scraped_at`; if within `global_scrape_cache_hours` (admin setting, default 2h), skip scraping and proceed with existing `raw_jobs`

Scrape → upsert `raw_jobs` on `(catalog_company_id, job_id)`. On conflict, update `last_seen_at`, `is_active`, `raw_description`. After all companies in scope are done, update `company_catalog.last_scraped_at` for each scraped company.

Concurrent manual runs hitting the same company are safe: the upsert is idempotent.

### Phase 2 — Process (per-user)

For the run's user and their active companies:

1. Pull all `raw_jobs` for those companies not yet in `user_jobs` for this user (LEFT JOIN / NOT EXISTS)
2. Apply heuristic filter (seniority, location, keyword regex from user settings) → create `user_jobs` row with `passed_heuristic`
3. For `passed_heuristic=True` jobs: LLM filter call → score
4. For score ≥ 0.4: LLM summarize call → create `match` row

This phase is identical to today's processing logic, sourcing from `raw_jobs` instead of the old `jobs` table.

`run_company_results` is recorded per-user-run as today. `jobs_found` reflects the raw count from Phase 1; `passed_heuristic` and `confirmed` reflect per-user Phase 2 outcomes.

### Admin setting

`global_scrape_cache_hours` stored in `settings` under akadmin (`user_id=1`). Readable by the scheduler when deciding whether to skip Phase 1 for a company. Defaults to `2`.

---

## Custom Company Promotion

When a user adds a company by URL:

1. Normalize the URL: lowercase domain, strip `www.`, strip `https?://`, strip trailing slash
2. Query `company_catalog` for a matching normalized `careers_url`
3. **Match found:** create `user_companies` entry linking to the existing catalog row (if not already linked)
4. **No match:** create a new `company_catalog` row (`source='user_submitted'`), then create `user_companies` entry
5. ATS discovery runs on the catalog entry — result is shared with any other user who later adds the same URL

### API response — `match_status`

The add-company endpoint returns a `match_status` field so the frontend can surface the right message to the user:

| `match_status` | Condition | Suggested UI message |
|----------------|-----------|----------------------|
| `added_new` | New catalog entry created, ATS discovery queued | "Added — detecting ATS type..." |
| `linked_existing_working` | Catalog entry exists, `discovery_status=success` | "Already in our catalog and working — added to your list" |
| `linked_existing_pending` | Catalog entry exists, ATS not yet confirmed | "Already in our catalog (ATS detection pending) — added to your list" |
| `linked_existing_quarantined` | Catalog entry exists but quarantined | "This company is in our catalog but currently quarantined due to scraping failures — added anyway" |
| `already_in_your_list` | User already has a `user_companies` row for this catalog entry | "You're already monitoring this company" |

URL normalization runs on both the submitted value and stored `careers_url` values before comparison, so `https://www.greenhouse.io/careers/google` and `http://greenhouse.io/careers/google` resolve to the same catalog entry.

---

## Migration

Single Alembic migration, data-preserving:

1. **Create `company_catalog`** — populate by deduplicating existing `companies` by `careers_url`. For collisions, pick the most recently updated row as canonical. Set `source='default'` for rows whose name matches the hardcoded defaults list, `'user_submitted'` otherwise. Populate `last_scraped_at` as the `updated_at` of the winning row.

2. **Create `user_companies`** — populate from existing `companies`: `(user_id, catalog_id)` mapped via the dedup table built in step 1, preserving `is_active`.

3. **Create `raw_jobs`** — populate by deduplicating existing `jobs` mapped through old-company → catalog mapping. For collisions (same job seen by multiple users): `first_seen_at` = earliest, `last_seen_at` = latest, `raw_description` from the most recent row, `is_active` = True if any row had it True.

4. **Create `user_jobs`** — populate from existing `jobs`: each row maps to its corresponding `raw_job` via `(catalog_company_id, job_id)`. Set `passed_heuristic=True` for all existing rows (cannot be recomputed retroactively).

5. **Update FKs** on `matches`, `feedback_examples`, `application_tracking`, `run_company_results`.

6. **Rename** old `companies` → `_deprecated_companies`, old `jobs` → `_deprecated_jobs`. Drop in a follow-up migration after confirming data integrity.

---

## What Does Not Change

- LLM calls and heuristic filtering are per-user — this is the point of the app
- `runs`, `matches`, `settings`, `token_usage`, `feedback_examples`, `application_tracking`, `resume` remain per-user
- BYOK model unchanged — each user's LLM API keys apply to their Phase 2 processing
- Frontend API surface is largely unchanged; responses compose `user_jobs` + `raw_jobs` data the same way `jobs` is read today
