# Joblin

Self-hosted job tracker that scrapes company career pages, filters postings against your personal criteria using LLMs, and notifies you on Discord when a strong match appears. No SaaS, no subscriptions — runs on a single server or locally in Docker.

---

## 📖 Full Documentation

**[→ docs/DOCUMENTATION.md](docs/DOCUMENTATION.md)**

The full documentation covers everything: architecture, authentication, scraping pipeline, LLM filtering, scheduled runs, criteria configuration (allowlists/denylists/profile), Discord setup, the applications tracker, resume tailoring, insights, presets, API reference, data model, and deployment.

---

## Features at a glance

- **Company tracking** — ATS auto-detection for Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday; Playwright fallback for custom pages. Discover companies by name only using an agentic web-search + LLM pipeline.
- **LLM filtering pipeline** — heuristic pre-filter (regex allowlist/denylist, location, seniority, exclusion keywords) followed by a scored LLM filter (0.0–1.0) and a structured LLM summary for confirmed matches.
- **Scheduled runs** — standard 5-field cron expression, per-timezone, per-user. Configurable from the UI without restart.
- **Preview mode** — run the full pipeline without sending Discord notifications; promote to real run later.
- **Discord notifications** — rich embed per match with score, tier, summary, and configurable @here / @role mentions.
- **Applications tracker** — pipeline from "interested" → applied → rejected/offer, with stats and daily activity chart.
- **Resume tailoring** — LLM-powered LaTeX resume tailoring per job (analyze → select → tailor), with in-browser PDF compilation via Tectonic.
- **Insights** — skill frequency analysis across your matched jobs, with per-skill job citations.
- **Usage tracking** — LLM token consumption per provider per run, with all-time / 7-day / 30-day windows.

---

## Quick start (Docker)

```bash
git clone https://github.com/yourname/joblin.git
cd joblin
cp .env.example .env
# Edit .env: set ADMIN_USERNAME, at least one LLM API key
docker compose up -d
```

See [docs/DOCUMENTATION.md#deployment](docs/DOCUMENTATION.md#deployment) for full deployment instructions, production TLS setup, and WSL2 tips.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ADMIN_USERNAME` | **Yes** | Your Authentik username (case-sensitive). Seeds the admin user on first run. |
| `GROQ_API_KEY` | One of three | Filter LLM. Get from [console.groq.com](https://console.groq.com). |
| `CEREBRAS_API_KEY` | One of three | Summarize LLM. Get from [cloud.cerebras.ai](https://cloud.cerebras.ai). |
| `GEMINI_API_KEY` | No | Fallback LLM. Get from [aistudio.google.com](https://aistudio.google.com). |
| `DISCORD_WEBHOOK_URL` | No | Also configurable from Settings UI after login. |
| `DATABASE_URL` | No | Defaults to `/app/data/joblin.db` in Docker. |

API keys set in `.env` are overridden by keys saved in **Settings → LLM Keys** (stored in the database per user).

---

## Development setup

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
playwright install chromium
alembic upgrade head
uvicorn backend.main:app --reload   # → http://localhost:8000/api

# Frontend (separate terminal)
cd frontend && npm install && npm run dev   # → http://localhost:5173

# Tests
pytest tests/ -v
```

---

## License

MIT
