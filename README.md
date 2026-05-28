# Joblin

Self-hosted job tracker. Scrapes company career pages, filters with LLMs, and notifies you on Discord when a strong match appears.

---

## Quick start (Docker)

### 1. Clone the repo

```bash
git clone https://github.com/yourname/joblin.git
cd joblin
```

### 2. Create your .env file

```bash
cp .env.example .env
```

Edit `.env` and fill in:

- `PUBLIC_HOSTNAME` -- your server's public domain (e.g. `joblin.example.com`)
- `CADDY_HASHED_PASSWORD` -- generate with:

  ```bash
  docker run --rm caddy:2-alpine caddy hash-password
  ```

  Paste the output (starting with `$2a$`) as the value.

- `BASIC_AUTH_PASSWORD` -- the plain-text version of the same password (used by the app internally)
- `GROQ_API_KEY` and/or `CEREBRAS_API_KEY` -- at least one required for LLM filtering

### 3. Point your DNS

Create an A record for `PUBLIC_HOSTNAME` pointing to your server's IP. Caddy handles TLS automatically via Let's Encrypt.

### 4. Start the stack

```bash
docker compose up -d
```

Open `https://<PUBLIC_HOSTNAME>` in your browser. The onboarding wizard appears on first login.

---

## Configuration reference

All settings below can be set via environment variables or (where noted) from the Settings UI after login.

| Variable | Required | Description |
|---|---|---|
| `PUBLIC_HOSTNAME` | Yes | Domain for Caddy TLS |
| `CADDY_HASHED_PASSWORD` | Yes | Bcrypt hash for basic auth |
| `BASIC_AUTH_PASSWORD` | Yes | Plain-text password (app internal use) |
| `GROQ_API_KEY` | One of these | Groq API key (filter LLM) |
| `CEREBRAS_API_KEY` | One of these | Cerebras API key (summarize LLM) |
| `GEMINI_API_KEY` | No | Gemini fallback (optional) |
| `DISCORD_WEBHOOK_URL` | No | Configurable from Settings UI |
| `DATABASE_URL` | No | Defaults to `/app/data/joblin.db` in Docker |

---

## Development setup

### Prerequisites

- Python 3.12+
- Node 20+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Backend

```bash
python -m venv .venv
.venv/Scripts/activate   # Windows
# or: source .venv/bin/activate   # macOS/Linux

pip install -r backend/requirements.txt
playwright install chromium

alembic upgrade head
uvicorn backend.main:app --reload
```

Backend runs at http://localhost:8000.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend dev server runs at http://localhost:5173 and proxies `/api` to the backend.

### Tests

```bash
pytest tests/ -v
```

---

## Architecture overview

```
Browser
  |
Caddy (TLS + basic auth)
  |
FastAPI app (port 8000)
  |-- /api/*        JSON API
  |-- /*            React SPA (served as static files from frontend/dist)
  |
  |-- APScheduler   Background scrape jobs (cron)
  |-- SQLite        joblin.db (persisted via Docker volume)
```

**LLM pipeline:**

1. Heuristics pre-filter -- title regex, location, seniority, exclusion keywords
2. Groq llama-3.1-8b-instant -- LLM filter pass (score 0.0-1.0)
3. Cerebras llama-3.3-70b -- summarize confirmed matches (score >= 0.40)
4. Discord -- post embeds (green = strong >= 0.70, yellow = borderline)

**ATS adapters (auto-detected by probing):**

Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday. Falls back to Crawl4AI + Playwright for custom career pages.

---

## License

MIT
