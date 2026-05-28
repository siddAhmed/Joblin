# Joblin

Self-hosted job tracker that scrapes company career pages, filters postings against your personal criteria using LLMs, and notifies you on Discord when a strong match appears. No SaaS, no subscriptions, runs on a single server or locally in Docker.

---

## Features

### Company tracking
- Add companies by name and careers URL; the app auto-detects the ATS (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday) by probing known API patterns
- Falls back to Crawl4AI + Playwright for custom career pages with optional per-company CSS selector overrides
- Bulk import via CSV (columns: `name`, `careers_url`)
- Quarantine system: companies that fail scraping N times in a row are quarantined and skipped; manual retry button from the UI

### LLM filtering pipeline
Every run applies a three-stage pipeline per job:

1. **Heuristics pre-filter** -- title regex allowlist/denylist, location allowlist/denylist, seniority keywords, exclusion keywords. Runs without any LLM call, cuts ~70% of volume.
2. **LLM filter pass** -- Groq `llama-3.1-8b-instant` scores each job 0.0-1.0 against your profile and criteria. Jobs scoring below 0.40 are dropped.
3. **LLM summarize pass** -- Cerebras `llama-3.3-70b` writes a concise summary for every confirmed match (score >= 0.40). Gemini `gemini-2.0-flash-lite` acts as fallback for either step if the primary key is missing.

Scores >= 0.70 are **strong matches** (green), 0.40-0.69 are **borderline** (yellow).

### Runs
- Manual "Run now" button with optional company subset selection
- **Preview mode**: runs the full pipeline and stores results but skips Discord notifications; matches shown with a "preview" badge
- **Seeding run**: if the database is empty, the first run stores everything without sending Discord notifications (avoids notification flood on first use)
- **Stop run**: cancel an in-progress run between companies
- Live progress via Server-Sent Events: per-company events stream in real time (scraping, jobs found, passed heuristic, confirmed, posted to Discord)
- Run history with per-company breakdown table; click any run to watch the SSE stream

### Matches
- Filtered view showing only LLM-confirmed matches
- Each card shows job title, company, location, score, tier, and a summary snippet
- "Not interested" / dismiss: stamps the match and writes a feedback example used as a negative signal in future LLM filter calls (up to 50 examples kept)
- Bulk re-notify: send selected matches to Discord on demand

### Jobs
- Full history of every scraped job with search and company filter
- Expandable view showing the raw description and LLM summary

### Settings
| Tab | What you configure |
|---|---|
| Discord | Webhook URL, mention type (@here / @role / none), mention ID. Test button sends a sample embed. |
| Criteria | Title allowlist/denylist (regex), location allowlist/denylist (regex), profile description (sent to LLM), exclusion keywords |
| Schedule | Cron expression for automatic scheduled runs |
| LLM Keys | Groq, Cerebras, Gemini API keys (stored in DB, override env vars) |
| Presets | One-click apply of bundled presets: `backend-generalist`, `python-ml`, `frontend` |

**Criteria live test**: paste any job description and immediately see the score and reasoning from the LLM filter using your current settings.

### Usage page
Tracks token consumption per LLM provider (Groq, Cerebras, Gemini) recorded from every filter and summarize call. Shows all-time, 7-day, and 30-day totals, call counts, and a per-run breakdown table. Links to each provider's quota dashboard.

### Onboarding wizard
Shown automatically on an empty database. Walks through Discord setup, criteria configuration (pick a preset or customize), company list import, and a preview test run before enabling the scheduler.

---

## Quick start (Docker, local)

### 1. Clone

```bash
git clone https://github.com/yourname/joblin.git
cd joblin
```

### 2. Create `.env`

```bash
cp .env.example .env
```

Edit `.env`:

```env
PUBLIC_HOSTNAME=localhost
CADDY_HASHED_PASSWORD=$$2a$$14$$...    # see note below
BASIC_AUTH_PASSWORD=yourpassword
GROQ_API_KEY=gsk_...
CEREBRAS_API_KEY=...
GEMINI_API_KEY=...                      # optional
DISCORD_WEBHOOK_URL=                    # optional, set from UI after login
```

**Generate the Caddy password hash:**

```bash
docker run --rm caddy:2-alpine caddy hash-password --plaintext yourpassword
```

The output starts with `$2a$`. In `.env`, escape every `$` as `$$`:

```
CADDY_HASHED_PASSWORD=$$2a$$14$$xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Build and run

```bash
# With Caddy (production-style, handles TLS)
docker compose up -d
docker compose logs -f app

# Without Caddy (simplest for local use, direct port 8000)
docker build -t joblin .
docker run -d --name joblin \
  -p 8000:8000 \
  -v joblin_data:/app/data \
  --env-file .env \
  -e DATABASE_URL=sqlite+aiosqlite:////app/data/joblin.db \
  joblin
```

**Local access (no Caddy):** `http://localhost:8000`

**WSL2 note:** if Windows has something on port 80, find the WSL2 IP with `ip addr show eth0 | grep 'inet '` and access via that IP instead of localhost.

### 4. First login

The onboarding wizard appears automatically. Follow the four steps:

1. Paste your Discord webhook URL and test it
2. Choose a preset (e.g. `backend-generalist`) or fill in criteria manually
3. Import companies via CSV or paste a list
4. Run a preview scrape to verify everything works before enabling notifications

---

## Production deployment (public server + TLS)

### 1. Point DNS

Create an A record for your domain pointing to the server IP. Caddy handles TLS via Let's Encrypt automatically.

### 2. Set env vars

```env
PUBLIC_HOSTNAME=joblin.example.com
CADDY_HASHED_PASSWORD=$$2a$$14$$...
BASIC_AUTH_PASSWORD=yourpassword
GROQ_API_KEY=gsk_...
CEREBRAS_API_KEY=...
```

### 3. Deploy

```bash
git pull
docker compose up -d --build
```

Open `https://joblin.example.com`. Login with username `joblin` and the plaintext password you hashed.

**Note:** Caddy auto-renews TLS certificates. The `caddy_data` Docker volume persists certificate state across restarts.

---

## Environment variables reference

| Variable | Required | Description |
|---|---|---|
| `PUBLIC_HOSTNAME` | Yes (Caddy) | Domain or `localhost`; used as the Caddy site address |
| `CADDY_HASHED_PASSWORD` | Yes (Caddy) | Bcrypt hash of the login password. Escape `$` as `$$` in `.env` |
| `BASIC_AUTH_PASSWORD` | Yes | Plaintext password stored for app internal use |
| `GROQ_API_KEY` | One required | Filter LLM (llama-3.1-8b-instant) |
| `CEREBRAS_API_KEY` | One required | Summarize LLM (llama-3.3-70b) |
| `GEMINI_API_KEY` | No | Fallback for both filter and summarize |
| `DISCORD_WEBHOOK_URL` | No | Also configurable from Settings UI |
| `DATABASE_URL` | No | Defaults to `/app/data/joblin.db` in Docker, `./joblin.db` in dev |

API keys set in `.env` are overridden by keys saved from the Settings UI (they are stored in the database).

---

## CSV import format

```csv
name,careers_url
Stripe,https://stripe.com/jobs
Datadog,https://www.datadoghq.com/careers/
Vercel,https://vercel.com/careers
```

The ATS type is auto-detected during import. No ATS column needed.

---

## Criteria configuration

The criteria fields feed into two different pipeline stages:

**Heuristic pre-filter (no LLM cost):**
- `title_allowlist` / `title_denylist` -- Python regex matched against the job title (case-insensitive). Example: `backend|platform|infrastructure`
- `location_allowlist` / `location_denylist` -- Same, matched against the location string. Leave empty to allow all locations.
- `exclusion_keywords` -- List of phrases; any match in the description immediately drops the job.

**LLM filter pass:**
- `profile_description` -- Free-text description of who you are and what you want. This is included verbatim in the LLM filter prompt. Be specific about work authorization, remote preference, seniority, tech stack, and anything else that matters.

**Example profile description for a candidate in India seeking remote or sponsored roles:**

```
Experienced backend engineer skilled in Python, distributed systems, and API design.
Based in India. Only interested in fully remote roles or positions that explicitly
offer visa sponsorship and relocation. Not eligible for roles requiring existing
work authorization outside India. Targeting senior or staff-level positions at
product companies, not agencies or consulting firms.
```

---

## Presets

Three built-in presets are available under Settings > Presets:

| Preset | Title allowlist | Focus |
|---|---|---|
| `backend-generalist` | backend, platform, infrastructure, systems, distributed, data engineer, api | Python backend, senior/staff |
| `python-ml` | machine learning, ml engineer, data scientist, mlops, ai engineer | ML/AI engineering |
| `frontend` | frontend, ui engineer, react, web engineer | Frontend/fullstack |

Applying a preset overwrites your current criteria settings. You can customize after applying.

---

## Supported ATS systems

| ATS | Detection method |
|---|---|
| Greenhouse | API probe at `boards-api.greenhouse.io/v1/boards/{slug}/jobs` |
| Lever | API probe at `api.lever.co/v0/postings/{slug}` |
| Ashby | API probe at `api.ashbyhq.com/posting-api/job-board/{slug}` |
| Workable | API probe at `{slug}.workable.com/spi/v3/jobs` |
| SmartRecruiters | API probe at `api.smartrecruiters.com/v1/companies/{slug}/postings` |
| Workday | URL pattern matching on the careers URL |
| Crawl4AI | Fallback for any URL that doesn't match above; uses Playwright headless browser with optional CSS selector |

ATS detection is automatic when you add a company. You can override the detected type and identifier from the company edit UI.

---

## Updating after code changes

### With Docker Compose

```bash
cd ~/joblin
git pull
sudo docker compose build && sudo docker compose up -d
```

Compose only rebuilds layers that changed. Python dependency changes rebuild from the `pip install` layer; frontend changes rebuild from `npm ci`. Unchanged layers are cached.

### Without Compose (direct docker run)

```bash
cd ~/joblin
git pull
sudo docker stop joblin && sudo docker rm joblin
sudo docker build -t joblin .
sudo docker run -d --name joblin \
  -p 8000:8000 \
  -v joblin_data:/app/data \
  --env-file .env \
  -e DATABASE_URL=sqlite+aiosqlite:////app/data/joblin.db \
  joblin
sudo docker logs -f joblin
```

The `joblin_data` volume persists the database across rebuilds. New Alembic migrations run automatically on startup.

### WSL2 tip

If building from `/mnt/c/...` (Windows filesystem) is slow, sync to native ext4 first:

```bash
rsync -av --delete /mnt/c/dev/joblin/ ~/joblin/ \
  --exclude='.git' --exclude='.venv' --exclude='frontend/node_modules' \
  --exclude='frontend/dist' --exclude='*.db'
```

Then build from `~/joblin`.

---

## Development setup

### Prerequisites

- Python 3.12+
- Node 20+

### Backend

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r backend/requirements.txt
playwright install chromium

cp .env.example .env   # fill in at least one LLM key
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

Dev server: `http://localhost:5173` (proxies `/api` to backend automatically via Vite config)

### Tests

```bash
pytest tests/ -v
```

28 tests covering health, companies, runs, LLM adapters, Discord, scrapers, and usage.

---

## Architecture

```
Browser
  |
Caddy (optional: TLS termination + basic auth)
  |
FastAPI app  :8000
  |-- /api/*   JSON REST API
  |-- /*        React SPA (served as static files from frontend/dist)
  |
  +-- APScheduler   Cron-based background run scheduler
  +-- SQLite        Persisted via Docker volume at /app/data/joblin.db
```

**Data model:**

| Table | Description |
|---|---|
| `companies` | Tracked companies with ATS config and quarantine state |
| `jobs` | Every scraped job posting, deduplicated by ATS ID or URL hash |
| `matches` | LLM-confirmed matches with score, tier, summary, and notification state |
| `runs` | Run history with aggregate stats and status |
| `run_company_results` | Per-company breakdown for each run |
| `token_usage` | LLM token consumption recorded per filter/summarize call |
| `settings` | Key-value store for all configurable settings |
| `feedback_examples` | "Not interested" signals used as negative LLM examples |

**Job deduplication:** ATS-provided ID takes priority, falls back to canonical URL hash, then composite hash of `company + normalized_title + normalized_location`. Jobs seen on subsequent runs have their `last_seen_at` updated rather than creating duplicates.

---

## License

MIT
