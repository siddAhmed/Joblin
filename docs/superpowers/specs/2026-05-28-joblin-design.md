# Joblin -- Design Spec

**Date:** 2026-05-28
**Status:** Approved

---

## 1. Overview

Joblin is a self-hosted web app that automatically tracks job postings from a user-curated list of companies, filters them against personalized criteria using LLMs, summarizes confirmed matches, and notifies via Discord. It is designed for a single user (or small team sharing credentials) and runs as one Docker Compose deployment.

---

## 2. Architecture

### Runtime topology

```
Browser (React SPA)
    |
    | HTTPS + Basic Auth
    v
Caddy (reverse proxy, Let's Encrypt, env-var basic auth)
    |
    | HTTP
    v
FastAPI :8000
  - Serves React SPA as static files at /
  - JSON API at /api/*
  - SSE stream at /api/runs/{id}/stream
  - APScheduler embedded (asyncio, runs scrape jobs in background)
  - SQLAlchemy 2.x async + SQLite
  - Alembic migrations
  - Scraping pipeline (ATS adapters + Crawl4AI fallback)
  - LLM pipeline (custom provider Protocol)
    |
    +-- Groq API (filter pass)
    +-- Cerebras API (summarize)
    +-- Gemini API (fallback)
    +-- Discord webhook
    +-- ATS JSON APIs (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday)
```

### Single-process design

APScheduler runs inside the FastAPI process as an asyncio scheduler. Scrape jobs are asyncio tasks -- no separate worker process or message broker. This keeps the deployment to one container behind Caddy.

---

## 3. Database Schema

All tables managed by SQLAlchemy 2.x declarative models + Alembic migrations. Database file: `joblin.db` (mounted as a named Docker volume).

### `companies`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| name | String | Display name |
| careers_url | String | User-supplied URL |
| ats_type | Enum | `greenhouse`, `lever`, `ashby`, `workable`, `smartrecruiters`, `workday`, `crawl4ai`, `custom` |
| ats_identifier | String? | ATS-specific token/slug (e.g. Greenhouse board token) |
| custom_api_url | String? | Override endpoint for custom ATS |
| css_selector | String? | Crawl4AI job-list selector override |
| is_active | Boolean | Default true |
| quarantine_count | Integer | Consecutive fetch failures |
| quarantined_at | DateTime? | Set when quarantine_count hits threshold |
| quarantine_reason | String? | Last error message |
| created_at | DateTime | |
| updated_at | DateTime | |

### `jobs`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| company_id | Integer FK | |
| job_id | String | Stable dedup key (ATS ID > URL hash > composite hash) |
| title | String | |
| location | String? | |
| url | String | |
| raw_description | Text | Full JD text |
| normalized_title | String | Lowercased, punctuation stripped |
| normalized_location | String? | |
| seniority | String? | Inferred from title |
| first_seen_at | DateTime | |
| last_seen_at | DateTime | Updated on each run that returns this job |
| is_active | Boolean | False when job disappears from ATS |

`job_id` has a unique constraint per company_id. A job seen again in a subsequent run updates `last_seen_at` only -- no new row, no re-processing.

### `matches`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| job_id | Integer FK | |
| run_id | Integer FK | First run that confirmed this job |
| score | Float | 0.0-1.0 from LLM filter |
| tier | Enum | `strong` (>= 0.70), `borderline` (0.40-0.69) |
| summary | Text | Cerebras-generated structured summary |
| filter_reasoning | Text? | One-line reasoning from Groq |
| is_preview | Boolean | True if run was preview mode |
| notified_at | DateTime? | Last Discord notification time |
| not_interested_at | DateTime? | Set when user dismisses |
| created_at | DateTime | |

One row per job. Re-notify updates `notified_at` without creating a new row.

### `runs`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| started_at | DateTime | |
| completed_at | DateTime? | |
| status | Enum | `running`, `completed`, `failed` |
| is_preview | Boolean | |
| company_ids | JSON? | Null = all companies |
| total_jobs_found | Integer | |
| total_passed_heuristic | Integer | |
| total_confirmed | Integer | |
| total_notified | Integer | |
| error_message | String? | Top-level failure message |

### `run_company_results`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| run_id | Integer FK | |
| company_id | Integer FK | |
| status | Enum | `scraping`, `done`, `failed`, `skipped` |
| jobs_found | Integer | |
| passed_heuristic | Integer | |
| confirmed | Integer | |
| error_message | String? | |

### `settings`
| Column | Type | Notes |
|---|---|---|
| key | String PK | |
| value | JSON | Arbitrary value |
| updated_at | DateTime | |

Flat key-value store. Adding new settings never requires a migration. Keys defined at app start if absent.

Default keys: `discord_webhook_url`, `discord_mention_type` (none/user/role), `discord_mention_id`, `criteria`, `schedule_cron`, `staleness_threshold_hours`, `quarantine_threshold`, `groq_api_key`, `cerebras_api_key`, `gemini_api_key`, `llm_filter_provider`, `llm_summarize_provider`.

### `feedback_examples`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| job_id | Integer FK | |
| company_name | String | Denormalized for prompt use |
| normalized_title | String | |
| normalized_location | String? | |
| summary | Text | LLM summary at time of dismissal |
| dismissed_at | DateTime | |

Capped at 50 rows (oldest deleted when exceeded). On each filter prompt, the 5 most recent rows are injected as negative few-shot examples.

---

## 4. Scraping Pipeline

Executed per-company within each run. SSE events are emitted at each stage.

```
Run triggered (scheduler or POST /api/runs)
  -> Create runs row, emit: run_started
  -> For each company:
       emit: scraping {company_name}
       -> ATS fetch (see ATS Detection below)
       emit: N jobs found
       -> For each job:
            compute stable job_id
            if job_id in DB: update last_seen_at, skip
            else: run heuristic pre-filter
       emit: N passed heuristic
       -> For each job passing heuristic:
            call LLM filter (Groq)
            if score < 0.4: write job to DB, no match
            if score >= 0.4: create match row, call Cerebras for summary
       emit: N confirmed
       -> For each confirmed match (skip if is_preview):
            post Discord embed
            update match.notified_at
       emit: posted to Discord
       -> On N consecutive failures: quarantine company
  -> Update runs row, emit: run_done
```

### ATS Detection (on company add)

When a user adds a company by careers URL, the backend probes the following patterns in order:

1. Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs`
2. Lever: `https://api.lever.co/v0/postings/{slug}`
3. Ashby: `https://api.ashbyhq.com/posting-api/job-board/{slug}`
4. Workable: `https://{slug}.workable.com/spi/v3/jobs`
5. SmartRecruiters: `https://api.smartrecruiters.com/v1/companies/{slug}/postings`
6. Workday: pattern-matched from URL structure

If all probes fail, the modal shows a detection report (which URLs were tried, which returned non-200) and offers two choices: "Use generic scraper (Crawl4AI)" or "Enter a custom API endpoint." The user can set a CSS selector for the job-list container at any time from the Companies table.

### Heuristic Pre-filter

Applied before any LLM call to cut ~70% of volume. Checks (all configurable in Settings > Criteria):
- Title regex allowlist (e.g., `backend|platform|infrastructure`)
- Title regex denylist (e.g., `intern|contract|staff augmentation`)
- Location allowlist / denylist
- Seniority allowlist (inferred from title: junior/mid/senior/staff/principal/lead)
- Global exclusion keywords in JD text

### Job ID Cascade

```
1. ATS-provided ID (preferred -- stable across runs)
2. SHA-256 of canonical URL (stripped of query params)
3. SHA-256 of "{company_id}:{normalized_title}:{normalized_location}"
```

### First-run / Restart Logic

- Cold start: zero rows in `runs` table. Run normally, notifications enabled.
- Subsequent starts: diff against DB. Only notify on genuinely new `job_id` values.
- Staleness gate: if last completed run finished within `staleness_threshold_hours` (default 4), skip the scheduled run entirely. Applies to scheduler-triggered runs only -- manual "Run now" always executes regardless of staleness.

---

## 5. LLM Pipeline

### Provider Protocol

A Python `Protocol` with two async methods:

```python
class LLMProvider(Protocol):
    async def filter(
        self, job: JobRecord, criteria: CriteriaConfig, negative_examples: list[FeedbackExample]
    ) -> FilterResult: ...

    async def summarize(self, job: JobRecord, match: MatchRecord) -> str: ...
```

Concrete implementations: `GroqAdapter`, `CerebrasAdapter`, `GeminiAdapter`. A factory function reads `llm_filter_provider` and `llm_summarize_provider` from settings and returns the appropriate instance. Swapping providers is one settings change -- no code change.

Default assignment:
- Filter pass: `GroqAdapter` (`llama-3.1-8b-instant`) -- high volume, cheap, fast
- Summarize: `CerebrasAdapter` (`gpt-oss-120b`) -- confirmed matches only, higher quality
- Fallback: `GeminiAdapter` (Flash Lite model -- verify exact model ID via Context7 at implementation) -- used when primary provider errors

### Filter Prompt Structure

```
System: You are a job relevance filter. Score the job 0.0-1.0 against the criteria.
        Return JSON: {"score": float, "reasoning": "one sentence"}.

Criteria: {criteria as structured text}

Negative examples (jobs the user dismissed as not interested):
{up to 5 recent feedback_examples as bullet points}

Job to score:
Title: {title}
Company: {company_name}
Location: {location}
Description: {raw_description truncated to 2000 chars}
```

Score thresholds: strong >= 0.70 (green), borderline 0.40-0.69 (yellow), discard < 0.40.

### Summarize Prompt Structure

```
System: Summarize this job posting for a candidate deciding whether to apply.
        Return 4 sections: Role snapshot, Key requirements, Why it matched, Red flags.
        Be direct. Max 200 words total.

Job: {title} at {company_name}
Criteria matched at score {score}:
Description: {raw_description}
```

### "Not Interested" Learning Signal

When a user marks a job "not interested":
1. Write a row to `feedback_examples` (company name, normalized title, location, summary).
2. Trim `feedback_examples` to 50 most recent rows.
3. Future filter prompts include the 5 most recent as negative few-shot examples.

This is global (not per-company) and affects all future LLM filter calls.

---

## 6. Discord Notifications

### Mention Configuration (Settings > Discord)

Three modes, selectable via dropdown:
- **None** -- no @mention in any notification
- **User** -- @{user_id} prepended to strong-match embeds
- **Role** -- @{role_id} prepended to strong-match embeds

Mention ID field appears conditionally when User or Role is selected.

### Embed Structure

**Strong match (green):**
```
[optional @mention]
[green left border]
Title: {job title}
Company: {company} | Location: {location}
Score: 0.83 | STRONG MATCH
{4-section summary}
[Apply] button linking to job URL
```

**Borderline match (yellow):**
```
[yellow left border]
Title: {job title}
Company: {company} | Location: {location}
Score: 0.52 | BORDERLINE
{4-section summary}
[Apply] button
```

Preview-mode matches skip Discord entirely but appear in the UI with a "preview" badge.

---

## 7. API Routes

All routes prefixed `/api/`. React SPA served at `/` (catch-all for client-side routing).

### Companies
| Method | Path | Description |
|---|---|---|
| GET | `/api/companies` | List all |
| POST | `/api/companies` | Add (triggers ATS probe) |
| PATCH | `/api/companies/{id}` | Update (selector, active, custom URL) |
| DELETE | `/api/companies/{id}` | Remove |
| POST | `/api/companies/{id}/retry` | Clear quarantine |
| POST | `/api/companies/probe` | Probe ATS type for a URL |
| POST | `/api/companies/import` | Bulk CSV import |

### Jobs + Matches
| Method | Path | Description |
|---|---|---|
| GET | `/api/jobs` | List (filters: company, date, tier, search, status) |
| GET | `/api/jobs/{id}` | Full detail + raw JD |
| POST | `/api/jobs/{id}/dismiss` | Mark not interested (writes feedback_examples) |
| GET | `/api/matches` | Match-only view (same filters) |
| POST | `/api/matches/notify` | Bulk re-notify selected matches |

### Runs
| Method | Path | Description |
|---|---|---|
| GET | `/api/runs` | History with per-company breakdown |
| POST | `/api/runs` | Start run (`{company_ids?, preview}`) |
| GET | `/api/runs/{id}` | Single run detail |
| GET | `/api/runs/{id}/stream` | SSE progress stream |

### Settings + Presets
| Method | Path | Description |
|---|---|---|
| GET | `/api/settings` | Get all settings |
| PATCH | `/api/settings` | Partial update |
| POST | `/api/settings/discord/test` | Send test embed |
| POST | `/api/settings/criteria/test` | Score pasted JD against current criteria |
| GET | `/api/presets` | List built-in presets |
| POST | `/api/presets/{name}/apply` | Overwrite criteria with preset |

### System
| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/stats` | Dashboard stats (today's matches, companies, last run, quarantine count) |

---

## 8. Frontend

### Tech Stack

Vite + React 18 + TypeScript + Tailwind CSS + shadcn/ui + TanStack Query + React Router. Dense, dark, dashboard-style aesthetic (Linear/Vercel).

### Navigation

Left sidebar. Collapsible to a 44px icon rail via chevron button. Collapse state persisted to `localStorage`. In collapsed mode: icon-only navigation with notification dots (blue = count, orange = quarantine warning). Tooltips on hover show screen names.

### Screens

**Dashboard**
- Stat row: today's matches, strong matches, companies tracked, jobs in DB
- Quarantine warning banner (when present), links to Companies screen
- Today's match feed, color-coded green (strong) / yellow (borderline) with score
- Topbar: "Run now" (POST /api/runs) + "Preview run" (preview: true) buttons

**Matches**
- Match rows with tier color, score, company, location
- Filters: tier, company, date range, search
- Expandable row: JD + LLM summary, "Not interested" button, "Re-notify" button
- Bulk select + "Re-notify selected" action
- Preview badge on preview-mode matches

**All Jobs**
- Full job history table including non-matches
- Same filters as Matches plus status (matched / not matched / dismissed)
- Expandable: raw JD + summary (if match exists) + "Not interested" button

**Companies**
- Table: name, ATS type badge, status (active/quarantined), last seen, job count
- Inline actions: edit selector, retry (quarantined), delete
- "Add company" modal: name + URL input, probe results displayed, ATS type resolved or fallback choice offered
- Bulk CSV import (name, careers_url columns required)

**Runs**
- History table: start time, duration, status, counts (found / heuristic / confirmed / notified)
- Active run: live SSE progress view, per-company status updating in real time
- Past run: click to expand per-company breakdown

**Settings -- five tabs**
- *Discord:* webhook URL, test button, mention type selector (None/User/Role), conditional mention ID field
- *Criteria:* structured form (title regex, location, seniority, exclusion keywords, free-text profile description); live JD tester (paste JD, score runs against current criteria, returns score + reasoning)
- *Schedule:* cron expression editor, staleness threshold, enable/disable toggle
- *LLM keys:* API key fields for Groq / Cerebras / Gemini; provider selector for filter and summarize roles
- *Presets:* cards for `backend-generalist`, `python-ml`, `frontend`; "Apply" button imports criteria

**Onboarding wizard** (shown when zero companies in DB)
Four steps:
1. Discord setup (webhook URL + test)
2. Criteria selection (pick preset or customize)
3. Company import (CSV upload or paste)
4. Test run (preview mode, shows results before enabling scheduler)

---

## 9. SSE Progress Stream

Endpoint: `GET /api/runs/{id}/stream` (Content-Type: `text/event-stream`)

Event types emitted during a run:

```
run_started       {"run_id": int, "company_count": int}
company_scraping  {"company_id": int, "company_name": str}
company_done      {"company_id": int, "jobs_found": int, "passed_heuristic": int, "confirmed": int}
company_failed    {"company_id": int, "error": str}
discord_posted    {"count": int}
run_done          {"run_id": int, "status": "completed"|"failed", "total_confirmed": int}
```

The stream closes when `run_done` is emitted. The frontend reconnects on disconnect (EventSource API handles this automatically).

---

## 10. Deployment

### Project Layout

```
joblin/
  backend/
    main.py             FastAPI app factory
    models/             SQLAlchemy models
    routers/            API route modules
    scrapers/           ATS adapters + Crawl4AI fallback
    llm/                Provider protocol + adapters
    scheduler.py        APScheduler setup
    alembic/            Migrations
  frontend/
    src/
    dist/               Built SPA (gitignored, built in Docker)
  presets/
    backend-generalist.json
    python-ml.json
    frontend.json
  docker-compose.yml
  Dockerfile
  Caddyfile
  .env.example
  README.md
```

### Environment Variables (`.env`)

```
APP_PASSWORD=<plain, hashed by Caddy at startup>
PUBLIC_HOSTNAME=jobs.example.com
GROQ_API_KEY=
CEREBRAS_API_KEY=
GEMINI_API_KEY=
DISCORD_WEBHOOK_URL=
```

All configurable values (Discord webhook URL, mention type/ID, schedule, staleness threshold, quarantine threshold, LLM API keys, provider selection) use environment variables as startup defaults: at first run, any `settings` table key that does not yet exist is seeded from the corresponding env var. Once a value is written via the Settings UI, the `settings` table value takes precedence over the env var for all subsequent reads.

### docker-compose.yml (outline)

Two services: `app` (FastAPI, port 8000 internal) and `caddy` (ports 80/443). A named volume mounts `joblin.db`. The `app` image is built from the repo `Dockerfile`, which runs `npm run build` then installs Python deps and starts uvicorn.

### Caddyfile

```
{PUBLIC_HOSTNAME} {
    basicauth /* {
        joblin {APP_PASSWORD_HASH}
    }
    reverse_proxy app:8000
}
```

The README includes the `caddy hash-password` command for generating the hash.

---

## 11. Build Phases

1. **Scaffold + DB + auth** -- repo structure, SQLAlchemy models, Alembic migrations, FastAPI skeleton, Caddy basic auth, Docker Compose working end-to-end
2. **Greenhouse scraper end-to-end** -- ATS probe, Greenhouse adapter, heuristic filter, one company scraped and stored in DB
3. **LLM filter + summarize + Discord** -- Groq filter pass, Cerebras summarize, Discord embed, SSE stream
4. **Remaining ATS adapters + Crawl4AI** -- Lever, Ashby, Workable, SmartRecruiters, Workday, Crawl4AI + Playwright fallback, CSS selector override
5. **Full UI** -- all screens implemented, TanStack Query wired to API, sidebar collapsible
6. **Onboarding wizard + SSE live view + preview mode + presets** -- wizard flow, live run progress, preview badge, preset JSON import
7. **Docker + Caddy + README** -- production docker-compose, Caddyfile, first-run instructions, .env.example

---

## 12. Key Constraints and Decisions

- **No em dashes** anywhere in code comments, docs, commit messages, or UI copy.
- **Context7 MCP** must be used to fetch current docs before writing code against any library (FastAPI, SQLAlchemy, Alembic, APScheduler, Crawl4AI, Playwright, httpx, groq, cerebras-cloud-sdk, google-genai, discord-webhook, Vite, React, TanStack Query, shadcn/ui).
- **Recall mode by default**: include borderline matches (score >= 0.4); never discard a borderline without storing it.
- **Preview mode**: writes all results to DB, skips Discord, marks matches with `is_preview=true`.
- **Quarantine threshold**: configurable (`quarantine_threshold` setting, default 3 consecutive failures).
- **Feedback cap**: `feedback_examples` capped at 50 rows; 5 most recent injected per filter prompt.
- **LLM provider swap**: one settings change, no code change. Provider protocol is the boundary.
- **Gemini model ID**: verify exact Flash Lite model string via Context7 at implementation time (Gemini API model names change frequently).
- **Sidebar collapse**: state persisted to `localStorage`; collapsed = 44px icon rail with notification dots.
