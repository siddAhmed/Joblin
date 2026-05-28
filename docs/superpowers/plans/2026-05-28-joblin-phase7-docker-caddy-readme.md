# Joblin Phase 7 -- Docker + Caddy + README

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package Joblin for production deployment with a multi-stage Docker build, Caddy reverse proxy for auto-HTTPS and basic auth, and a complete README for first-run setup.

**Prerequisite:** Phase 6 complete and all tests passing.

---

## File Map

| File | Responsibility |
|---|---|
| `Dockerfile` | Multi-stage build: Node frontend build + Python backend image |
| `docker-compose.yml` | Two services (app + caddy), named volume for db persistence |
| `Caddyfile` | Auto-HTTPS, basic auth, reverse proxy to app:8000 |
| `.env.example` | Template for all required and optional environment variables |
| `README.md` | First-run instructions, configuration reference, development guide |

---

## Task 32: Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Write `Dockerfile`**

```dockerfile
# Stage 1: build the React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: production Python image
FROM python:3.12-slim AS app
WORKDIR /app

# System deps for Playwright + Crawl4AI
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Copy application code
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Copy built frontend into the static directory FastAPI serves
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Run Alembic migrations then start Uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 2: Verify the build locally**

```powershell
docker build -t joblin:dev .
```

Expected: image builds successfully, no errors in pip install or npm ci steps.

- [ ] **Step 3: Commit**

```powershell
git add Dockerfile
git commit -m "feat: multi-stage Dockerfile (Node frontend + Python backend)"
```

---

## Task 33: docker-compose.yml and Caddyfile

**Files:**
- Create: `docker-compose.yml`
- Create: `Caddyfile`

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
version: "3.9"

services:
  app:
    build: .
    restart: unless-stopped
    volumes:
      - db_data:/app/data
    environment:
      - DATABASE_URL=sqlite+aiosqlite:////app/data/joblin.db
      - GROQ_API_KEY=${GROQ_API_KEY}
      - CEREBRAS_API_KEY=${CEREBRAS_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - BASIC_AUTH_PASSWORD=${BASIC_AUTH_PASSWORD}
      - DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL}
    expose:
      - "8000"

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    environment:
      - PUBLIC_HOSTNAME=${PUBLIC_HOSTNAME}
      - CADDY_HASHED_PASSWORD=${CADDY_HASHED_PASSWORD}

volumes:
  db_data:
  caddy_data:
  caddy_config:
```

- [ ] **Step 2: Write `Caddyfile`**

```
{$PUBLIC_HOSTNAME} {
    basicauth /* {
        joblin {$CADDY_HASHED_PASSWORD}
    }
    reverse_proxy app:8000
}
```

- [ ] **Step 3: Verify compose config is valid**

```powershell
docker compose config
```

Expected: prints resolved YAML with no errors.

- [ ] **Step 4: Commit**

```powershell
git add docker-compose.yml Caddyfile
git commit -m "feat: docker-compose with Caddy reverse proxy and basic auth"
```

---

## Task 34: .env.example

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Write `.env.example`**

```dotenv
# === Required ===

# Your server's public domain name (used by Caddy for TLS)
PUBLIC_HOSTNAME=joblin.example.com

# Bcrypt hash of your chosen password. Generate with:
#   docker run --rm caddy:2-alpine caddy hash-password
CADDY_HASHED_PASSWORD=$2a$14$...

# Shared password stored in plain text for the app (same value, unhashed)
BASIC_AUTH_PASSWORD=changeme

# LLM provider API keys (at least one of Groq or Cerebras required)
GROQ_API_KEY=
CEREBRAS_API_KEY=
GEMINI_API_KEY=

# === Optional ===

# Override the SQLite path (default: ./joblin.db in development, /app/data/joblin.db in Docker)
# DATABASE_URL=sqlite+aiosqlite:///./joblin.db

# Discord webhook URL (can also be set from the Settings UI after first login)
DISCORD_WEBHOOK_URL=
```

- [ ] **Step 2: Confirm `.env.example` is committed but `.env` is gitignored**

Check `.gitignore` contains `.env`. If not, add it.

```powershell
Select-String -Path .gitignore -Pattern "^\.env$"
```

If no match, append the line:

```powershell
Add-Content -Path .gitignore -Value "`n.env"
```

- [ ] **Step 3: Commit**

```powershell
git add .env.example .gitignore
git commit -m "chore: add .env.example and ensure .env is gitignored"
```

---

## Task 35: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# Joblin

Self-hosted job tracker. Scrapes company career pages, filters with LLMs, and notifies you on Discord when a strong match appears.

---

## Quick start (Docker)

### 1. Clone the repo

\`\`\`bash
git clone https://github.com/yourname/joblin.git
cd joblin
\`\`\`

### 2. Create your .env file

\`\`\`bash
cp .env.example .env
\`\`\`

Edit `.env` and fill in:

- `PUBLIC_HOSTNAME` -- your server's public domain (e.g. `joblin.example.com`)
- `CADDY_HASHED_PASSWORD` -- generate with:

  \`\`\`bash
  docker run --rm caddy:2-alpine caddy hash-password
  \`\`\`

  Paste the output (starting with `$2a$`) as the value.

- `BASIC_AUTH_PASSWORD` -- the plain-text version of the same password (used by the app internally)
- `GROQ_API_KEY` and/or `CEREBRAS_API_KEY` -- at least one required for LLM filtering

### 3. Point your DNS

Create an A record for `PUBLIC_HOSTNAME` pointing to your server's IP. Caddy handles TLS automatically via Let's Encrypt.

### 4. Start the stack

\`\`\`bash
docker compose up -d
\`\`\`

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

\`\`\`bash
python -m venv .venv
.venv/Scripts/activate   # Windows
# or: source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
playwright install chromium

alembic upgrade head
uvicorn backend.main:app --reload
\`\`\`

Backend runs at http://localhost:8000.

### Frontend

\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

Frontend dev server runs at http://localhost:5173 and proxies `/api` to the backend.

### Tests

\`\`\`bash
pytest tests/ -v
\`\`\`

---

## Architecture overview

\`\`\`
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
\`\`\`

**LLM pipeline:**

1. Heuristics pre-filter -- title regex, location, seniority, exclusion keywords
2. Groq llama-3.1-8b-instant -- LLM filter pass (score 0.0-1.0)
3. Cerebras gpt-oss-120b -- summarize confirmed matches (score >= 0.40)
4. Discord -- post embeds (green = strong >= 0.70, yellow = borderline)

**ATS adapters (auto-detected by probing):**

Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday. Falls back to Crawl4AI + Playwright for custom career pages.

---

## License

MIT
```

- [ ] **Step 2: Commit**

```powershell
git add README.md
git commit -m "docs: add README with quick start, config reference, and architecture overview"
```

---

## Task 36: End-to-end smoke test

- [ ] **Step 1: Build the full Docker image**

```powershell
docker build -t joblin:smoke .
```

Expected: build succeeds, frontend assets copied into image.

- [ ] **Step 2: Run the image standalone (no Caddy) to verify startup**

```powershell
docker run --rm -p 8000:8000 `
  -e DATABASE_URL="sqlite+aiosqlite:////tmp/joblin-smoke.db" `
  -e BASIC_AUTH_PASSWORD="testpass" `
  -e GROQ_API_KEY="placeholder" `
  joblin:smoke
```

Expected: Alembic migration runs, Uvicorn starts, `GET http://localhost:8000/api/health` returns `{"status": "ok"}`.

- [ ] **Step 3: Verify the React SPA is served at root**

```powershell
curl http://localhost:8000/
```

Expected: HTML response containing `<div id="root">`.

- [ ] **Step 4: Final commit**

```powershell
git add .
git commit -m "chore: phase 7 complete -- Docker, Caddy, README"
```

---

**Phase 7 complete.** Joblin is fully packaged for production. All seven phases done.
