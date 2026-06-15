# Onboarding & Company Discovery Design

**Date:** 2026-06-15
**Status:** Approved

## Overview

Two linked improvements to how users add companies to Joblin:

1. **Onboarding overhaul** — replace the manual CSV import step with a curated default company picker (120+ companies pre-selected, search to deselect, fast parallel import)
2. **Add company by name** — users type company names only; an agentic background loop discovers the careers URL and ATS automatically, with live progress inline in the Companies table

A cross-cutting performance fix (parallel ATS probing) underpins both features.

---

## 1. Default Company Catalog

A new static data file `backend/data/default_companies.py` holds the curated list of 120+ companies as a Python list of dicts:

```python
DEFAULT_COMPANIES = [
    {"name": "Google", "careers_url": "https://careers.google.com/"},
    {"name": "Meta",   "careers_url": "https://www.metacareers.com/"},
    # ... 120+ entries
]
```

This file is the single source of truth for:
- The onboarding company picker (pre-populated list)
- The first lookup in the agentic discovery loop (if a name matches a catalog entry, skip web search entirely and go straight to ATS probing)

A new endpoint `GET /companies/defaults` returns this list so the frontend can populate the onboarding picker.

---

## 2. Performance Fix: Parallel ATS Probing

### Within `probe_ats()` (backend/scrapers/probe.py)

Currently probes 6 ATS types sequentially (up to 60s worst case). Changed to fire all 6 simultaneously with `asyncio.gather()`, returning the first 200 response. Worst-case per-company drops from ~60s to ~10s (one network round-trip).

### Bulk import endpoint

New `POST /companies/bulk` accepts `[{name, careers_url}]`. Uses `asyncio.gather()` with `asyncio.Semaphore(20)` to probe all companies concurrently (max 20 in-flight at once). Returns when all done. Expected time for 120 companies: ~15 seconds.

---

## 3. Onboarding Flow Changes

Step 3 of onboarding (currently CSV upload) is replaced:

**New Step 3 — Company Picker:**
- Fetches the default company list from `GET /companies/defaults`
- All 120+ companies pre-selected on load
- Search input filters the list by name in real time
- "Select All" / "Deselect All" toggle
- Count badge: "N selected"
- On confirm: calls `POST /companies/bulk` with the selected companies
- A progress indicator ("Adding companies...") is shown during the bulk import
- On completion: advances to Step 4 (test run) as before

Step 4 (test run preview) is unchanged.

---

## 4. Agentic Company Discovery

### Data Model

New migration adds two nullable columns to the `companies` table. **Safe for existing data** — both are nullable with defaults, so existing rows are unaffected:

```sql
ALTER TABLE companies ADD COLUMN discovery_status VARCHAR DEFAULT 'none';
ALTER TABLE companies ADD COLUMN discovery_message TEXT;
```

`discovery_status` values: `'none'` | `'discovering'` | `'failed'`

`discovery_message` stores the last human-readable status from the loop, e.g.:
- `"Searching web..."`
- `"Probing 10 candidates..."`
- `"Probing Ashby API..."`
- `"Could not find — paste URL manually"`

### New Endpoint: POST /companies/discover

Accepts `[{name: str}]` — no URL required. For each name:
1. Checks if name matches an entry in the default catalog (case-insensitive). If yes, skips web search and uses the known URL directly.
2. Creates a `Company` row with `discovery_status='discovering'`
3. Fires `asyncio.create_task(discover_company(company_id, name))`

Returns immediately with the created company IDs. The frontend does not wait for discovery to complete.

### Agentic Discovery Loop (`backend/scrapers/discover.py`)

Overall timeout: **90 seconds** per company.

```
Step 1: Catalog lookup
  → name matches DEFAULT_COMPANIES? use that URL, skip to Step 3.

Step 2: Web search + heuristics (collect up to 10 candidate URLs)
  → crawl4ai scrapes DuckDuckGo HTML search for "{name} careers jobs"
  → extract up to 7 URLs from search results
  → generate heuristic candidates: careers.{slug}.com, jobs.{slug}.com, {slug}.com/careers
  → combined pool capped at 10 unique URLs

Step 3: LLM pass 1 — filter candidates
  → prompt: given company name + 10 candidate URLs, rank and return the most
    likely careers portal URLs (eliminates LinkedIn, Glassdoor, news articles)
  → model: claude-haiku-4-5-20251001 (low cost, fast)
  → output: ordered list of up to 10 filtered URLs

Step 4: Parallel ATS probe
  → run probe_ats() against all filtered candidates simultaneously
  → first 200 response from a known ATS wins
  → on hit: update company (ats_type, ats_identifier, discovery_status='none')

Step 5: If no ATS hit — LLM pass 2
  → crawl4ai fetches the top LLM-ranked URL (the most likely careers page)
  → pass page markdown to LLM: "what ATS or job board does this page use?
    Extract the API URL or identifier, or return the canonical jobs listing URL."
  → model: claude-haiku-4-5-20251001
  → on useful response: update company (ats_type=crawl4ai or detected type,
    careers_url=extracted URL, discovery_status='none')

Step 6: Fallback
  → LLM pass 2 returned nothing useful but a URL was found in Step 2/3:
    save company as crawl4ai with that URL, discovery_status='none'
  → No URL found at all OR 90s timeout exceeded:
    discovery_status='failed', discovery_message="Could not find — paste URL manually"
```

At each step transition, `discovery_message` is updated so the frontend can show live progress.

### Discovery message updates (SSE-free)

The loop writes `discovery_message` to the DB at each step. The frontend polls `GET /companies` every 4 seconds while any company has `discovery_status='discovering'`. No SSE needed — polling is sufficient given the 90s max duration and 4s interval.

---

## 5. Frontend Changes

### Companies Page — Add by Name

The "Add Company" modal gets a tab toggle: **By URL** (existing flow) | **By Name** (new).

"By Name" tab:
- Textarea: one company name per line
- Submit button: "Discover & Add"
- On submit: calls `POST /companies/discover`, closes modal immediately
- No waiting — user returns to the table and sees companies appear in "Discovering" state

### Companies Page — Discovering State

While any company has `discovery_status='discovering'`:
- Page polls `GET /companies` every 4 seconds
- Stops polling when all `discovery_status` values are `'none'` or `'failed'`

Discovering table row:
- Name column: company name + animated pulsing dot
- ATS column: `discovery_message` text (e.g., "Probing 10 candidates...")
- Status badge: "Discovering" (indigo)
- Actions column: disabled (no delete/retry during discovery)

### Companies Page — Failed State

Failed table row:
- Status badge: "Discovery Failed" (red)
- ATS column: "Could not find — paste URL manually"
- An inline text input + "Save" button replaces the normal ATS/status cells
- On submit: calls new `POST /companies/{id}/resolve` with `{careers_url}`, which runs `probe_ats()` against the provided URL, updates the company record (ats_type, ats_identifier, careers_url), and clears `discovery_status` back to `'none'`

### Onboarding — Step 3

Replaced as described in Section 3. The rest of the onboarding flow (Steps 1, 2, 4) is unchanged.

---

## 6. What Is Not Changing

- Existing `POST /companies` (add by URL) — unchanged
- Existing `PATCH /companies/{id}` — unchanged (css_selector, custom_api_url, is_active, ats_type, ats_identifier only)
- `POST /companies/import` (CSV bulk import) — kept as-is (still useful for power users)
- All scraper implementations (`greenhouse.py`, `lever.py`, etc.) — unchanged
- Pipeline, runs, filtering, Discord notifications — unchanged
- Multi-user data isolation — all new endpoints thread `user_id` through as before

---

## Key Constraints

- **No data loss on migration**: new columns are nullable with defaults; existing company rows are untouched
- **No new external API keys**: web search uses crawl4ai on DuckDuckGo HTML (already a dependency); LLM uses the existing Anthropic client already wired into the backend
- **Graceful degradation**: if discovery fails, the company is still created and the user can manually paste a URL — nothing is lost
- **Concurrency safety**: `asyncio.create_task` tasks are per-company and write to distinct DB rows; no shared mutable state
