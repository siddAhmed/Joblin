# Joblin — Complete Platform Documentation

> Self-hosted job tracker that scrapes company career pages, filters postings against your personal criteria using LLMs, and notifies you on Discord when a strong match appears.

---

## Table of Contents

1. [Platform Overview](#platform-overview)
2. [Architecture](#architecture)
3. [Authentication & Multi-User](#authentication--multi-user)
4. [Company Management](#company-management)
5. [The Scraping Pipeline](#the-scraping-pipeline)
6. [Criteria Configuration](#criteria-configuration-in-depth)
7. [The LLM Filtering Pipeline](#the-llm-filtering-pipeline)
8. [Runs](#runs)
9. [Scheduled Runs](#scheduled-runs)
10. [Matches](#matches)
11. [Applications Tracker](#applications-tracker)
12. [Resume Tailoring](#resume-tailoring)
13. [Insights & Skill Analysis](#insights--skill-analysis)
14. [Discord Notifications](#discord-notifications)
15. [Settings Reference](#settings-reference)
16. [Presets](#presets)
17. [Usage & Token Tracking](#usage--token-tracking)
18. [LLM Providers](#llm-providers)
19. [Data Model](#data-model)
20. [API Reference](#api-reference)
21. [Environment Variables Reference](#environment-variables-reference)
22. [Deployment](#deployment)
23. [Development Setup](#development-setup)
24. [Admin Operations](#admin-operations)

---

## Platform Overview

Joblin watches company career pages on your behalf. It scrapes ATS job boards (or falls back to a headless browser), runs every new posting through a two-stage LLM pipeline calibrated to your personal criteria, and posts strong matches to Discord. Everything runs on a single server or locally in Docker; there is no SaaS and no subscription.

**Core loop:**

```
Scheduler / Manual trigger
  → Scrape company career pages (ATS API or Playwright)
  → Heuristic pre-filter (title regex, location regex, seniority, exclusion keywords)
  → LLM filter pass (scores 0.0–1.0 against your profile)
  → LLM summarize pass (writes a structured summary for confirmed matches)
  → Post to Discord (if score ≥ 0.40 and not a preview/seeding run)
  → Store in DB for browsing in the UI
```

---

## Architecture

```
Browser
  │
Caddy (optional: TLS termination + Authentik forward-auth)
  │
FastAPI app  :8000
  ├── /api/*         JSON REST API
  └── /*             React SPA (served as static files from frontend/dist)
        │
        ├── APScheduler    Cron-based background scheduler (per user)
        ├── SQLite         /app/data/joblin.db (persisted via Docker volume)
        └── Playwright     Headless Chromium (Crawl4AI fallback scraper)
```

**Stack:**

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Alembic |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS / shadcn/ui |
| Database | SQLite (async via `aiosqlite`) |
| Scheduler | APScheduler 4.x (`AsyncScheduler`, `CronTrigger`) |
| Scraping | httpx (ATS APIs), Crawl4AI + Playwright (fallback) |
| LLM | Groq, Cerebras, Gemini (pluggable provider pattern) |
| Proxy | Caddy 2 (TLS, forward-auth) |
| Auth | Authentik (OIDC/forward-auth via Caddy) |

**Startup sequence:**

1. FastAPI app starts; `lifespan` context manager runs.
2. `seed_defaults` ensures user ID 1 has all default settings in the DB.
3. `AsyncScheduler` starts; `start_scheduler` reads each user's `schedule_cron` and `scheduler_enabled` settings and registers or removes cron jobs accordingly.
4. Alembic migrations run automatically on Docker startup (`alembic upgrade head` in Dockerfile entrypoint).

---

## Authentication & Multi-User

### Authentik (production)

Joblin uses [Authentik](https://goauthentik.io/) as its identity provider. Caddy's `forward_auth` directive intercepts every request and validates it against the Authentik outpost. On successful authentication, Authentik injects HTTP headers into the upstream request:

```
X-authentik-username   →  used as the user identifier in Joblin
X-authentik-email
X-authentik-name
```

The `ADMIN_USERNAME` env var (set in `.env`) must exactly match the Authentik username of the person setting up the instance. This value is used during the Alembic migration to pre-seed the admin user row in the `users` table.

**Fixing a wrong username** (if you see an empty onboarding screen):

```bash
docker exec joblin-app-1 python -c "
  import sqlite3; c=sqlite3.connect('/app/data/joblin.db')
  c.execute('DELETE FROM users WHERE id=2')
  c.execute(\"UPDATE users SET authentik_username='YOUR_USERNAME' WHERE id=1\")
  c.commit(); print('done')
"
```

> Always `DELETE` the wrong row **before** the `UPDATE` to avoid the unique constraint.

### Multi-user

Each Authentik user who logs in gets their own row in `users`. All data (companies, jobs, matches, runs, settings, feedback, applications, resume) is scoped to `user_id`. The scheduler maintains a separate cron job per user (`scrape_cron_{user_id}`).

---

## Company Management

### Adding a company

From the **Companies** page, enter a company name and careers URL. Joblin immediately probes the URL across all supported ATS APIs in parallel (see [Supported ATS Systems](#supported-ats-systems)) and stores the detected type and identifier.

Internally this creates two records:
- `CompanyCatalog` — the canonical company record, shared across users.
- `UserCompany` — the per-user join record; holds `is_active` state.

If another user already added the same company URL, Joblin links your `UserCompany` to the existing `CompanyCatalog` entry — no duplicate scraping.

### Discover by name only

You can paste a list of **company names** (without URLs) and Joblin will attempt to discover the careers URL automatically using a multi-step agentic pipeline:

1. **Catalog fast path** — checks the built-in default companies list.
2. **Web search** — queries DuckDuckGo for `{name} careers jobs`, extracts URLs.
3. **Heuristic candidates** — generates `careers.{slug}.com`, `jobs.{slug}.com`, `{slug}.com/careers`.
4. **LLM pass 1** — Claude Haiku filters and ranks candidate URLs.
5. **Parallel ATS probe** — probes all ranked candidates simultaneously.
6. **LLM pass 2** — if no ATS match, crawls the top-ranked page with Playwright and uses Claude Haiku to analyze the page content and identify the ATS type.
7. **Fallback** — stores as `crawl4ai` with the best candidate URL if nothing better is found.

Discovery runs as a background task (90-second timeout). The `UserCompany` is `is_active=False` until discovery completes.

### CSV import

Upload a CSV file with columns `name` and `careers_url`. ATS detection runs for each row. No ATS column needed.

```csv
name,careers_url
Stripe,https://stripe.com/jobs
Datadog,https://www.datadoghq.com/careers/
Vercel,https://vercel.com/careers
```

### Company editing

From the company list, you can override:
- `ats_type` — force a specific ATS (e.g., switch from `crawl4ai` to `greenhouse`).
- `ats_identifier` — the board slug used in ATS API calls.
- `custom_api_url` — an alternate URL for scraping (used instead of `careers_url`).
- `css_selector` — a CSS selector for the Crawl4AI fallback to extract job listings from.
- `is_active` — pause a company without removing it.

### Quarantine system

When a company's scraper fails (timeout or exception), its `quarantine_count` increments. Once it reaches `quarantine_threshold` (default: 3 consecutive failures), the company is **quarantined**:
- `quarantined_at` is stamped with the current time.
- `quarantine_reason` stores the last error message.
- Quarantined companies are skipped in future scheduled runs.

The quarantine threshold is configurable per-user in the admin settings. To re-enable a quarantined company, use the **Retry** button in the UI (`POST /api/companies/{id}/retry`), which resets `quarantine_count`, `quarantined_at`, and `quarantine_reason` and sets `is_active=True`.

### Supported ATS systems

| ATS | Detection method | API endpoint pattern |
|---|---|---|
| **Greenhouse** | HTTP 200 on API probe | `boards-api.greenhouse.io/v1/boards/{slug}/jobs` |
| **Lever** | HTTP 200 on API probe | `api.lever.co/v0/postings/{slug}` |
| **Ashby** | HTTP 200 on API probe | `api.ashbyhq.com/posting-api/job-board/{slug}` |
| **Workable** | HTTP 200 on API probe | `{slug}.workable.com/spi/v3/jobs` |
| **SmartRecruiters** | HTTP 200 on API probe | `api.smartrecruiters.com/v1/companies/{slug}/postings` |
| **Workday** | URL pattern match | `workday.com` or `myworkdayjobs.com` in careers URL |
| **Crawl4AI** | Fallback | Playwright headless browser + optional CSS selector |

The `slug` is extracted from the careers URL path; if the path segment is a generic word (`jobs`, `careers`, `openings`, etc.), the company name is slugified instead.

---

## The Scraping Pipeline

### Phase 1: Scrape

`execute_run` → `_scrape_phase`

For each active, non-quarantined company in the user's list:

1. **Cache check** (scheduled runs only): if the company was scraped within `global_scrape_cache_hours` (default: 2h), it's skipped and existing active `RawJob` rows are counted. Manual runs always re-scrape.
2. **Fetch** via the appropriate ATS scraper module (60-second timeout).
3. **Upsert raw jobs**: for each job returned:
   - Compute a stable `job_id` (see deduplication below).
   - Normalize the title and location (lowercase, strip non-alphanumeric).
   - Detect seniority from the normalized title.
   - If a `RawJob` with the same `job_id` exists: update `last_seen_at` and `is_active=True` (and refresh description if available).
   - Otherwise: insert a new `RawJob`.
4. On failure: increment `quarantine_count`, quarantine if threshold reached, emit `company_failed` event.
5. On success: reset `quarantine_count` to 0, update `last_scraped_at`.

### Job deduplication

`compute_job_id` in `backend/scrapers/job_id.py` produces a stable string ID:

1. **ATS-provided ID** — used if the scraper returns a non-empty `id` field.
2. **Canonical URL hash** — SHA256 of the normalized job URL.
3. **Composite hash** — SHA256 of `company_id + normalized_title + normalized_location` (fallback when no URL is available).

---

## Criteria Configuration (In-Depth)

All criteria are stored under the `criteria` key in the `settings` table (as a JSON object). They are split between two pipeline stages.

### Heuristic pre-filter criteria (free — no LLM cost)

These run in `backend/scrapers/heuristics.py` via `passes_heuristic()`.

#### `title_allowlist`
Python regex (case-insensitive) matched against the **job title**. A non-empty allowlist means the title **must** match at least one alternative.

```
# Example: only titles related to backend/infra work
backend|platform|infrastructure|systems|distributed|data engineer|api
```

#### `title_denylist`
Python regex matched against the job title. Any match **rejects** the job.

```
# Example: exclude intern, contract, and non-eng roles
intern|contract|marketing|sales|design|front.?end
```

#### `location_allowlist`
Python regex matched against the **location string**. If set, only jobs whose location matches are forwarded. Jobs with no location are **not filtered** (location field may be empty for remote-first listings).

```
# Example: only remote or US-based
remote|united states|new york|san francisco
```

#### `location_denylist`
Python regex matched against the location string. Any match **rejects** the job (only applies if the location field is non-empty).

```
# Example: exclude on-site Singapore/India roles (you want fully remote or sponsored)
singapore|india|bangalore|mumbai|chennai
```

#### `seniority_allowlist`
A list of seniority levels. If set, only titles whose inferred seniority is in this list pass. Seniority is inferred by regex against the normalized title.

Recognized levels: `junior`, `mid`, `senior`, `staff`, `principal`, `lead`, `manager`

```json
["senior", "staff", "principal", "lead"]
```

If no seniority level is detected in the title, the job **passes** regardless of this filter (the filter only acts when a level is positively detected and it's not in your allowlist).

#### `exclusion_keywords`
A list of plain strings. If **any** keyword appears in the raw job description (case-insensitive substring match), the job is immediately rejected.

```json
["clearance required", "on-site only", "US citizens only"]
```

---

### LLM filter criteria

#### `profile_description`
Free-text description of who you are and what you're looking for. This is injected verbatim into the LLM filter prompt as the `Profile:` line. **Be specific.** The LLM uses this as its primary scoring signal.

**What to include:**
- Your tech stack and areas of expertise.
- Work authorization and location constraints (very important — the LLM is explicitly instructed to score < 0.40 for jobs outside your country/remote preference when authorization constraints are present).
- Remote/hybrid/on-site preference.
- Seniority level you're targeting.
- Company type preference (product vs. agency, startup vs. enterprise).
- Anything else that matters (e.g., "not interested in pure DevOps roles").

**Example:**

```
Experienced backend engineer skilled in Python, distributed systems, and API design.
Based in India. Only interested in fully remote roles or positions that explicitly
offer visa sponsorship and relocation. Not eligible for roles requiring existing
work authorization outside India. Targeting senior or staff-level positions at
product companies, not agencies or consulting firms.
```

---

## The LLM Filtering Pipeline

### Phase 2: Process

`execute_run` → `_process_phase`

Runs after scraping. For each `RawJob` that hasn't been processed by this user:

#### Step 1: Heuristic pre-filter
`passes_heuristic(raw_job, criteria)` — evaluates all five heuristic fields. If it fails, a `UserJob` record is written with `passed_heuristic=False` and processing stops for this job. No LLM call is made.

This stage typically cuts ~70% of scraped volume.

#### Step 2: LLM filter
The filter provider (default: Groq `llama-3.1-8b-instant`) receives:
- The job title, company name, location, and up to 2000 characters of the raw description.
- Your full criteria config (profile description, title regex, seniority).
- Up to 5 **negative feedback examples** — jobs you previously dismissed as "not interested," included as a negative signal.

**System prompt instructs the model to:**
- Score the job 0.0–1.0 against the criteria.
- Return JSON: `{"score": <float>, "reasoning": "<one sentence>"}`.
- Score < 0.40 for jobs that violate location/authorization constraints if the profile specifies them.

**Score thresholds:**

| Score | Tier | Action |
|---|---|---|
| `< 0.40` | (dropped) | Discarded; no match record created |
| `0.40–0.69` | `borderline` | Match record created (yellow badge) |
| `≥ 0.70` | `strong` | Match record created (green badge) |

#### Step 3: LLM summarize
For confirmed matches (score ≥ 0.40), the summarize provider (default: Groq `llama-3.3-70b-versatile`) generates a structured summary with four labeled sections:
1. **Role snapshot** — what the job is.
2. **Key requirements** — must-haves.
3. **Why it matched** — against your profile.
4. **Red flags** — anything concerning.

Max 200 words total, using up to 3000 characters of the description.

#### Step 4: Discord notification
If `discord_webhook_url` is set, the run is not a preview, and it's not a seeding run, the match is posted to Discord with a rich embed (score, tier color, summary, job URL, mention).

### Negative feedback loop

When you click **"Not interested"** on a match, a `FeedbackExample` record is created with the job's company name, normalized title, normalized location, and summary. The pipeline loads the **5 most recent** feedback examples for the current user and injects them into the LLM filter prompt as negative signals. Maximum 50 feedback examples are kept per user (oldest pruned).

### Seeding run detection

Before the first actual run, there are no `UserJob` records for the user. The pipeline detects this (`existing_count == 0`) and marks the run as a **seeding run**. During a seeding run, all pipeline stages run normally — scraping, heuristics, LLM — but **Discord notifications are suppressed**. This prevents a flood of notifications on first use when the system processes hundreds of historical jobs at once.

---

## Runs

### Run types

| Type | Description |
|---|---|
| **Normal run** | Full pipeline; posts new matches to Discord. |
| **Preview run** | Full pipeline including LLM; stores matches with `is_preview=True`; **no Discord notifications**. Matches shown with a "preview" badge in the UI. |
| **Seeding run** | Auto-detected on first run (no existing `UserJob` rows); Discord suppressed regardless of `is_preview` flag. |
| **Scheduled run** | Triggered by APScheduler cron job; checks staleness guard before running. |

### Company subset

When triggering a manual run, you can optionally select a **subset of companies** (by `UserCompany.id`). Only the selected companies are scraped in that run. Useful for testing a specific company or re-running after adding new entries.

### Staleness guard (scheduled runs)

The scheduler checks whether the most recent completed run finished within `staleness_threshold_hours` (default: 4h). If a run completed recently enough, the scheduled trigger is a no-op. This prevents redundant runs if you manually triggered one recently.

### Live progress (SSE)

Every run emits Server-Sent Events to `GET /api/runs/{id}/stream`. Events:

| Event type | Payload |
|---|---|
| `run_started` | `{run_id, company_count, seeding}` |
| `company_skipped_cache` | `{company_id, company_name, cached_jobs}` |
| `company_failed` | `{company_id, error}` |
| `company_done` | `{company_id, jobs_found}` |
| `discord_posted` | `{count}` |
| `run_done` | `{run_id, status, total_confirmed, seeding}` |
| `ping` | `{}` (keepalive every 30s if idle) |

The frontend subscribes to this stream when viewing an active run and re-subscribes when navigating to a past run's detail page.

### Cancellation

`POST /api/runs/{id}/cancel` sets a flag in the in-process `_cancelled_runs` set. The pipeline checks this flag between companies (in the scrape phase) and between jobs (in the process phase). On detection, the run is stamped `status=cancelled` and the SSE stream is terminated.

### Run history

`GET /api/runs` returns the last 50 runs (newest first) with aggregate stats: `total_jobs_found`, `total_new_jobs`, `total_passed_heuristic`, `total_confirmed`, `total_notified`.

`GET /api/runs/{id}` returns per-company breakdown (`RunCompanyResult` rows) with per-company `jobs_found`, `passed_heuristic`, `confirmed`, and error messages.

---

## Scheduled Runs

### Enabling the scheduler

In **Settings → Schedule**, toggle "Enable scheduler" on. The scheduler syncs immediately (`sync_user_schedule`) — no restart needed.

### Cron expression

Enter a standard 5-field cron expression:

```
┌───── minute (0-59)
│ ┌─── hour (0-23)
│ │ ┌─ day of month (1-31)
│ │ │ ┌ month (1-12)
│ │ │ │ ┌ day of week (0-6, 0=Sun)
│ │ │ │ │
* * * * *
```

**Common examples:**

| Expression | Meaning |
|---|---|
| `0 */4 * * *` | Every 4 hours (default) |
| `0 9 * * *` | Every day at 9:00 AM |
| `0 9 * * 1-5` | Weekdays at 9:00 AM |
| `0 9,18 * * *` | Twice daily at 9 AM and 6 PM |
| `0 */2 * * *` | Every 2 hours |

### Timezone

The schedule timezone is set separately (default: `Asia/Kolkata`). The cron expression is evaluated in this timezone. Set it to your local timezone to get predictable firing times.

**Common timezone strings:** `UTC`, `America/New_York`, `America/Los_Angeles`, `Europe/London`, `Europe/Berlin`, `Asia/Kolkata`, `Asia/Singapore`, `Asia/Tokyo`, `Australia/Sydney`.

### How the scheduler works internally

`start_scheduler` (called at startup) iterates all users and calls `_schedule_user_job` for each. This function:

1. Reads `schedule_cron`, `scheduler_enabled`, and `schedule_timezone` from the user's settings.
2. If `scheduler_enabled=False`: removes any existing cron job for this user (`scrape_cron_{user_id}`).
3. If `scheduler_enabled=True`: registers (or replaces) a `CronTrigger` cron job with `ConflictPolicy.replace`.

When you save schedule settings in the UI, the backend calls `sync_user_schedule` immediately — the new cron expression takes effect without a restart.

---

## Matches

### Viewing matches

The **Matches** page shows all LLM-confirmed matches (score ≥ 0.40) ordered newest-first. You can filter by tier (`strong` / `borderline`) and by company.

Each card shows:
- Job title, company, location
- Score (e.g., `0.83`) and tier badge
- LLM-generated summary with all four sections
- "Not interested" button and "Open job" link

### "Not interested" / Dismiss

Clicking **Not interested** (`POST /api/matches/{id}/dismiss`) stamps `hidden_at` on the match. The match disappears from the list. A `FeedbackExample` record is created and fed back into the LLM filter on subsequent runs as a negative signal.

> **Note:** In the current implementation, `hidden_at` is set but `FeedbackExample` creation is handled by the frontend calling a separate endpoint — check the [matches router](../backend/routers/matches.py) for the exact flow.

### Bulk re-notify

Select multiple matches and click **Send to Discord** (`POST /api/matches/notify`). Useful for sharing matches you found interesting with others, or re-sending after changing your Discord webhook.

### Preview matches

Matches from preview runs have `is_preview=True`. They appear with a "preview" badge. When you run a real (non-preview) run that processes the same jobs, the existing `UserJob` and `Match` rows are promoted: `preview_only=False` and `is_preview=False` are set, and no duplicate records are created.

---

## Applications Tracker

The **Applications** page is a full-featured application pipeline tracker independent of the job scraping.

### Statuses

| Status | Meaning |
|---|---|
| `interested` | You're interested but haven't applied yet |
| `applied` | Application submitted |
| `rejected` | Rejected at any stage |
| `offer` | Received an offer |

### Sources

| Source | Meaning |
|---|---|
| `joblin` | Came from a Joblin match |
| `external` | You added it manually (found elsewhere) |

### Stats

`GET /api/applications/stats` returns:
- Total count
- Breakdown by status
- Breakdown by source (joblin vs. external)
- Offer/application response rate (%)
- Daily activity series for the last 30 days (for charting)

### Creating an application

Applications can be created from a match card (one-click "Mark as Applied") or manually from the Applications page. When linked to a `UserJob` (`job_id`), the unique constraint prevents duplicate application records — updating status on an existing linked application updates the existing record.

### Bulk actions

Select multiple applications and apply a status change or delete them in bulk.

---

## Resume Tailoring

The **Resume** page provides an LLM-powered resume tailoring workflow. Requires a LaTeX resume uploaded as `.tex` content.

### Workflow

1. **Upload your resume** (LaTeX `.tex` content) — stored in the `resume` table.
2. Optionally upload an **activities bank** — a supplementary text file with additional bullet points, projects, or experiences not in your main resume.
3. From a match card, click **Tailor Resume** — this streams three phases via SSE:

   | Phase | What happens |
   |---|---|
   | 1 — Analyze | LLM extracts `required_skills`, `preferred_skills`, `key_themes`, `seniority_signals`, and `keywords` from the job description. |
   | 2 — Select | LLM reviews your resume (and activities bank if present) and selects 6–8 most relevant items to emphasize. |
   | 3 — Tailor | LLM rewrites your `.tex` resume incorporating the selected items, preserving LaTeX structure and escaping special characters. |

4. The tailored `.tex` content is returned. You can copy it or **compile to PDF** directly in the browser.

### PDF compilation

`POST /api/resume/compile` compiles `.tex` content using [Tectonic](https://tectonic-typesetting.github.io/) (a self-contained LaTeX engine). Returns a PDF binary. 60-second timeout. Tectonic must be installed in the Docker image.

### Provider

The resume tailoring provider is the same as the summarize provider (configured via `llm_summarize_provider`). The tailor prompts enforce strict LaTeX escaping rules to avoid broken output.

---

## Insights & Skill Analysis

The **Insights** page provides skill demand analysis across your matched jobs.

### How it works

1. Select matches to analyze (`POST /api/insights/analyze`).
2. For each selected match, the filter LLM provider's `extract_skills` method is called with the job's title and description.
3. Skills are extracted as a JSON array of canonical names (e.g., `"PostgreSQL"` not `"Postgres"`, `"Kubernetes"` not `"k8s"`).
4. Stored in `job_skills` table (deduplicated by `job_id + skill_name`).

### Viewing skills

`GET /api/insights/skills` returns skills ranked by frequency across all your analyzed jobs, with a count per skill.

`GET /api/insights/skills/{name}/citations` returns which job titles and companies mentioned a specific skill — useful for understanding which companies value a given technology.

---

## Discord Notifications

### Setup

In **Settings → Discord**, paste your webhook URL and configure:

- **Mention type**: `none`, `@here`, or `@role`
- **Mention ID**: Role ID (for `@role` mentions) — right-click the role in Discord → Copy ID

Use the **Test** button to send a sample embed and verify the webhook works before enabling notifications.

### Notification content

Each match is posted as a Discord embed containing:
- Job title and company
- Location
- Score and tier (color-coded: green for strong, yellow for borderline)
- LLM-generated summary
- Link to the job posting
- Optional mention (`@here` or `@role`)

### Notification timing

- **Normal runs**: notifications fire immediately as each job is confirmed.
- **Preview runs**: no notifications.
- **Seeding runs** (first run on empty DB): no notifications.
- **Bulk re-notify**: `POST /api/matches/notify` resends selected matches on demand.

---

## Settings Reference

All settings are stored per-user in the `settings` table (key-value, JSON-serialized values).

### Discord tab

| Key | Type | Default | Description |
|---|---|---|---|
| `discord_webhook_url` | string | `""` | Discord webhook URL. Also settable via `DISCORD_WEBHOOK_URL` env var. |
| `discord_mention_type` | string | `"none"` | `"none"`, `"here"`, or `"role"` |
| `discord_mention_id` | string | `""` | Role ID for `"role"` mention type |

### Criteria tab

| Key | Type | Default | Description |
|---|---|---|---|
| `criteria.title_allowlist` | regex string | `""` | Title must match (empty = allow all) |
| `criteria.title_denylist` | regex string | `"intern\|junior"` | Title must NOT match |
| `criteria.location_allowlist` | regex string | `""` | Location must match (empty = allow all) |
| `criteria.location_denylist` | regex string | `""` | Location must NOT match |
| `criteria.seniority_allowlist` | string[] | `["senior","staff","principal","lead","mid"]` | Allowed seniority levels |
| `criteria.exclusion_keywords` | string[] | `[]` | Description keyword blocklist |
| `criteria.profile_description` | string | `""` | Free-text profile for LLM context |

### Schedule tab

| Key | Type | Default | Description |
|---|---|---|---|
| `scheduler_enabled` | bool | `false` | Enable/disable the cron scheduler |
| `schedule_cron` | string | `"0 */4 * * *"` | 5-field cron expression |
| `schedule_timezone` | string | `"Asia/Kolkata"` | IANA timezone string |
| `staleness_threshold_hours` | number | `4` | Min hours between scheduled runs |

### LLM Keys tab

| Key | Type | Default | Description |
|---|---|---|---|
| `groq_api_key` | string | from env | Groq API key (overrides `GROQ_API_KEY` env var) |
| `cerebras_api_key` | string | from env | Cerebras API key |
| `gemini_api_key` | string | from env | Gemini API key |
| `llm_filter_provider` | string | `"groq"` | Provider for filter pass: `groq`, `cerebras`, `gemini` |
| `llm_summarize_provider` | string | `"cerebras"` | Provider for summarize pass: `groq`, `cerebras`, `gemini` |

API keys saved in Settings UI override environment variable values. The precedence is: **DB setting > env var > empty string**.

### Advanced / Admin

| Key | Type | Default | Description |
|---|---|---|---|
| `quarantine_threshold` | number | `3` | Consecutive failures before quarantine |
| `global_scrape_cache_hours` | number | `2` | Cache window for scheduled scrapes |
| `auto_dismiss_on_apply` | bool | `true` | Auto-hide match when marked as applied |

### Criteria live test

In Settings → Criteria, paste any job description and click **Test**. Joblin calls the LLM filter immediately with your current settings and returns the score (0.0–1.0) and one-sentence reasoning. Uses real LLM quota.

### API key validation

In Settings → LLM Keys, paste keys and click **Validate**. Joblin makes a minimal test call to each provider and returns `{valid: bool, error: string}` per key. Keys are not stored unless you explicitly save.

---

## Presets

Presets are JSON files in `presets/`. Applying a preset from Settings → Presets **overwrites your current criteria** (title allowlist/denylist, location rules, seniority, exclusion keywords, and profile description). You can customize after applying.

### Available presets

| Preset | Group | Title allowlist | Focus |
|---|---|---|---|
| `backend-generalist` | Experienced | `backend\|platform\|infrastructure\|systems\|distributed\|data engineer\|api` | Python backend, senior/staff |
| `python-ml` | Experienced | `machine learning\|ml engineer\|data scientist\|mlops\|ai engineer` | ML/AI engineering |
| `frontend` | Experienced | `frontend\|ui engineer\|react\|web engineer` | Frontend/fullstack |
| `vlsi` | Experienced | `vlsi\|rtl\|fpga\|verilog\|asic\|chip design\|verification engineer\|...` | Hardware/VLSI engineering |
| `intern-backend` | Intern | Backend internship titles | Entry-level backend |
| `intern-frontend` | Intern | Frontend internship titles | Entry-level frontend |
| `intern-fullstack` | Intern | Fullstack internship titles | Entry-level fullstack |
| `intern-ml` | Intern | ML/AI internship titles | Entry-level ML |
| `intern-generalist` | Intern | Software engineering intern | General SWE internship |

### Preset structure

```json
{
  "group": "experienced",
  "label": "Backend generalist",
  "description": "Python, distributed systems, infrastructure",
  "criteria": {
    "title_allowlist": "backend|platform|...",
    "title_denylist": "intern|contract|...",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["senior", "staff", "principal", "lead"],
    "exclusion_keywords": ["clearance required", "on-site only"],
    "profile_description": "..."
  }
}
```

To add a custom preset, create a new `.json` file in the `presets/` directory following the same structure.

---

## Usage & Token Tracking

The **Usage** page tracks LLM token consumption across all runs.

### What's tracked

Every `filter` and `summarize` LLM call records a `TokenUsage` row:
- `provider` — `groq`, `cerebras`, or `gemini`
- `call_type` — `filter` or `summarize`
- `prompt_tokens`, `completion_tokens`, `total_tokens`
- `run_id` — which run triggered the call

### Views

- **All-time totals** by provider
- **7-day** and **30-day** windowed totals
- **Call counts** per window
- **Per-run breakdown** table — useful for estimating cost per run

### Quota dashboard links

The Usage page links directly to each provider's quota/billing dashboard:
- [Groq console](https://console.groq.com)
- [Cerebras cloud](https://cloud.cerebras.ai)
- [Google AI Studio](https://aistudio.google.com)

---

## LLM Providers

### Provider model defaults

| Provider | Filter model | Summarize model |
|---|---|---|
| **Groq** | `llama-3.1-8b-instant` | `llama-3.3-70b-versatile` |
| **Cerebras** | `gpt-oss-120b` | `gpt-oss-120b` |
| **Gemini** | `gemini-2.0-flash-lite` | `gemini-2.0-flash-lite` |

Models can be overridden per-provider via settings keys (`groq_filter_model`, `groq_summarize_model`, `cerebras_model`, `gemini_filter_model`, `gemini_summarize_model`).

### Fallback behavior

If the primary filter or summarize call raises any exception, it is logged as a warning and processing continues:
- Failed filter: `filter_result = None` → job is not confirmed (silently dropped).
- Failed summarize: `summary = ""` → match is stored with an empty summary.

There is no automatic provider fallback at the call level. Use the `llm_filter_provider` / `llm_summarize_provider` settings to explicitly switch providers.

### Provider protocol

All providers implement the `LLMProvider` protocol (`backend/llm/protocol.py`):

```python
async def filter(title, company_name, location, description, criteria, negative_examples) -> FilterResult
async def summarize(title, company_name, description, score) -> str
async def extract_skills(title, description) -> list[str]
async def analyze_job(job_description) -> dict
async def select_activities(requirements, tex_content, activities_content) -> str
async def tailor_resume(tex_content, selected_items) -> str
```

---

## Data Model

### Tables

| Table | Description |
|---|---|
| `users` | One row per Authentik user. `authentik_username` is the lookup key from the `X-authentik-username` header. |
| `company_catalog` | Canonical company records shared across users. Holds ATS config, quarantine state, discovery state. |
| `user_companies` | Per-user company subscriptions. `is_active` enables/disables per user. |
| `raw_jobs` | Every scraped job posting. Deduplicated by `job_id`. `is_active` tracks whether seen in latest scrape. `last_seen_at` updated on subsequent scrapes. |
| `user_jobs` | Per-user view of raw jobs. Records heuristic pass/fail, run ID, `preview_only` flag. One row per (user, raw_job) pair. |
| `matches` | LLM-confirmed matches. Score, tier, summary, filter reasoning, preview flag, notification timestamp, hidden timestamp. |
| `runs` | Run records with aggregate stats and status (`running`, `completed`, `failed`, `cancelled`). |
| `run_company_results` | Per-company breakdown per run. Jobs found, passed heuristic, confirmed, error messages. |
| `token_usage` | LLM token consumption per call. Linked to run. |
| `settings` | Key-value store. Per-user. JSON-serialized values. |
| `feedback_examples` | "Not interested" signals. Used as negative examples in LLM filter prompts. |
| `job_skills` | Skills extracted from job descriptions by the Insights feature. |
| `application_tracking` | User-managed application pipeline (interested → applied → rejected/offer). |
| `resume` | Per-user LaTeX resume storage + activities bank. |

### Key relationships

```
users
  ├── user_companies → company_catalog
  ├── user_jobs → raw_jobs → company_catalog
  │     └── matches
  ├── runs → run_company_results
  ├── settings
  ├── feedback_examples
  ├── application_tracking → user_jobs
  ├── resume
  └── token_usage (via runs)
```

---

## API Reference

All endpoints are under `/api`. Authentication is handled at the Caddy layer (Authentik forward-auth); all requests reaching the app are pre-authenticated. The app resolves the current user from the `X-authentik-username` header.

### System

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |

### Companies

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/companies` | List user's companies |
| `GET` | `/api/companies/defaults` | Built-in default company list |
| `POST` | `/api/companies` | Add a company (runs ATS probe) |
| `POST` | `/api/companies/bulk` | Add multiple companies |
| `POST` | `/api/companies/import` | Import CSV file |
| `POST` | `/api/companies/discover` | Discover by name(s) — async |
| `POST` | `/api/companies/probe` | Probe ATS without adding |
| `PATCH` | `/api/companies/{id}` | Update ATS config / active state |
| `DELETE` | `/api/companies/{id}` | Remove from user's list |
| `POST` | `/api/companies/{id}/retry` | Un-quarantine a company |
| `POST` | `/api/companies/{id}/resolve` | Re-probe ATS with a new URL |

### Runs

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/runs` | Start a run (`preview: bool`, optional `company_ids`) |
| `GET` | `/api/runs` | List last 50 runs |
| `GET` | `/api/runs/{id}` | Get run with per-company breakdown |
| `POST` | `/api/runs/{id}/cancel` | Request cancellation |
| `GET` | `/api/runs/{id}/stream` | SSE stream of run events |

### Jobs

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/jobs` | List scraped jobs (with search, company filter) |

### Matches

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/matches` | List matches (filter by tier, company, pagination) |
| `POST` | `/api/matches/notify` | Bulk re-send matches to Discord |
| `POST` | `/api/matches/{id}/dismiss` | Dismiss (hide) a match |

### Settings

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/settings` | Get all settings |
| `PATCH` | `/api/settings` | Update one or more settings |
| `POST` | `/api/settings/discord/test` | Send test Discord notification |
| `POST` | `/api/settings/criteria/test` | Test criteria against a job description |
| `POST` | `/api/settings/validate-keys` | Validate API keys (Groq, Cerebras, Gemini) |

### Presets

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/presets` | List available presets |
| `POST` | `/api/presets/{name}/apply` | Apply a preset (overwrites criteria) |

### Usage

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/usage` | Token usage stats |

### Insights

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/insights/analyze` | Extract skills from selected matches |
| `GET` | `/api/insights/skills` | List skills with frequency counts |
| `GET` | `/api/insights/skills/{name}/citations` | Jobs mentioning a specific skill |

### Resume

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/resume` | Get stored LaTeX resume |
| `PUT` | `/api/resume` | Save LaTeX resume |
| `GET` | `/api/resume/activities` | Get activities bank |
| `PUT` | `/api/resume/activities` | Save activities bank |
| `POST` | `/api/resume/compile` | Compile `.tex` to PDF (returns binary) |
| `POST` | `/api/resume/tailor` | Tailor resume for a job (SSE stream) |

### Applications

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/applications` | List applications (filter by status, source, search) |
| `POST` | `/api/applications` | Create an application |
| `PATCH` | `/api/applications/{id}` | Update status, notes, applied date |
| `DELETE` | `/api/applications/{id}` | Delete an application |
| `GET` | `/api/applications/stats` | Stats + daily series |
| `POST` | `/api/applications/bulk` | Bulk status change or delete |

### Admin

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/admin/reset` | Delete all user job data (matches, runs, user_jobs, feedback) — keeps companies and settings |

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `ADMIN_USERNAME` | **Yes** | Authentik username of the admin user. Must match exactly (case-sensitive). Used to seed the admin user in the DB on first run. |
| `GROQ_API_KEY` | One of three required | API key for Groq (filter LLM). Get from [console.groq.com](https://console.groq.com). |
| `CEREBRAS_API_KEY` | One of three required | API key for Cerebras (summarize LLM). Get from [cloud.cerebras.ai](https://cloud.cerebras.ai). |
| `GEMINI_API_KEY` | No | API key for Google Gemini (fallback). Get from [aistudio.google.com](https://aistudio.google.com). |
| `DISCORD_WEBHOOK_URL` | No | Discord webhook URL. Can also be set from the Settings UI after login. |
| `DATABASE_URL` | No | SQLite connection string. Default inside Docker: `sqlite+aiosqlite:////app/data/joblin.db`. |

Keys set in `.env` serve as defaults. Any key saved through the **Settings UI** overrides the env var for that user (stored in `settings` table).

---

## Deployment

### Docker Compose (recommended)

```bash
git clone https://github.com/yourname/joblin.git
cd joblin
cp .env.example .env
# Edit .env: set ADMIN_USERNAME, at least one LLM key
docker compose up -d
docker compose logs -f app
```

The Compose file includes:
- `app` — the Joblin FastAPI container
- `caddy` — the Caddy reverse proxy (TLS + Authentik forward-auth)

**Caddy configuration** (`Caddyfile`):
- All requests pass through Authentik forward-auth.
- SSE endpoints (`/api/runs/*/stream`) have `flush_interval -1` to disable response buffering.
- The app container is addressed as `app:8000` internally.

### Standalone Docker (no Caddy)

```bash
docker build -t joblin .
docker run -d --name joblin \
  -p 8000:8000 \
  -v joblin_data:/app/data \
  --env-file .env \
  -e DATABASE_URL=sqlite+aiosqlite:////app/data/joblin.db \
  joblin
```

Access at `http://localhost:8000`. No TLS, no auth — suitable for local use or behind an existing reverse proxy.

### Updating

```bash
cd ~/joblin
git pull
docker compose build && docker compose up -d
```

Alembic migrations run automatically on container startup. The `joblin_data` Docker volume persists the database across rebuilds.

### WSL2 tip

If building from `/mnt/c/...` is slow, sync to native ext4 first:

```bash
rsync -av --delete /mnt/c/dev/joblin/ ~/joblin/ \
  --exclude='.git' --exclude='.venv' --exclude='frontend/node_modules' \
  --exclude='frontend/dist' --exclude='*.db'
```

---

## Development Setup

### Prerequisites

- Python 3.12+
- Node 20+
- Playwright Chromium (`playwright install chromium`)

### Backend

```bash
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows

pip install -r backend/requirements.txt
playwright install chromium

cp .env.example .env   # fill in ADMIN_USERNAME + at least one LLM key
alembic upgrade head
uvicorn backend.main:app --reload
```

Backend API: `http://localhost:8000/api`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dev server: `http://localhost:5173` — proxies `/api` to backend via Vite config.

### Tests

```bash
pytest tests/ -v
```

28 tests covering health, companies, runs, LLM adapters, Discord, scrapers, and usage.

---

## Admin Operations

### Reset job data

`POST /api/admin/reset` clears all of a user's job-related data while preserving companies, settings, and resume:
- Deletes `UserJob`, `Match`, `Run`, `RunCompanyResult`, `FeedbackExample` for the current user.
- Does **not** delete `RawJob` (shared), `CompanyCatalog` (shared), `UserCompany`, or `Settings`.

Available from the Settings page in the UI.

### Manual DB fixes

Access the SQLite DB directly from within the container:

```bash
docker exec -it joblin-app-1 python -c "
import sqlite3
c = sqlite3.connect('/app/data/joblin.db')
# your queries here
c.close()
"
```

Or copy the DB out for inspection:

```bash
docker cp joblin-app-1:/app/data/joblin.db ./joblin_backup.db
```

### Alembic migrations

Migrations are in `backend/alembic/versions/`. To create a new migration after changing models:

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

Migrations run automatically on container startup via the Dockerfile entrypoint.
