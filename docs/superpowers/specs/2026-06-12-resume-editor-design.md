# Resume Editor Design

**Date:** 2026-06-12
**Status:** Approved

## Overview

A full LaTeX resume editor embedded in Joblin. Users upload their existing `.tex` file (from Overleaf or elsewhere), store it as their reference resume, and can tailor it to any matched job with one click. The tailored result is shown in a two-panel Monaco + PDF preview layout. Everything runs locally - no resume content leaves the machine.

---

## Architecture

The feature is self-contained: a `resume` router on the backend, a `Resume` page on the frontend, and Tectonic (a lightweight Rust-based LaTeX engine) installed in the Docker image for compilation.

Data flow for one-click tailoring:
1. User clicks "Tailor Resume" on a match card - navigates to `/resume?jobId=<id>`
2. Resume page loads with their stored `.tex` in Monaco and that job pre-selected in the dropdown
3. User clicks **Tailor** - frontend sends `{job_id}` to `POST /api/resume/tailor`
4. Backend fetches the stored reference resume + the job's description from DB, calls LLM, returns modified `.tex`
5. Monaco editor updates with the tailored content; status bar shows "Tailored for [Job] @ [Company]"
6. User clicks **Compile** - frontend sends current `.tex` to `POST /api/resume/compile`, gets PDF back, renders in right panel
7. User can edit manually, save as new reference, or download the PDF

The tailor endpoint always operates on the **stored reference**, never the current editor state, so tailorings are always clean.

---

## Data Model

New `resume` table - single-row design (always upsert to `id=1`). No versioning in v1.

| column | type | notes |
|---|---|---|
| `id` | INTEGER PK | always 1 |
| `tex_content` | TEXT NOT NULL | full .tex source |
| `updated_at` | DATETIME NOT NULL | auto-updated on save |

One new Alembic migration. No foreign keys needed.

---

## Backend API

New `backend/routers/resume.py`, registered at `/api/resume`.

| method | path | description |
|---|---|---|
| `GET` | `/api/resume` | Returns `{tex_content, updated_at}`. 404 if no resume uploaded yet. |
| `PUT` | `/api/resume` | Body `{tex_content}`. Upserts and returns saved resume. This is the "Save as Reference" action. |
| `POST` | `/api/resume/compile` | Body `{tex_content}`. Writes to temp dir, runs Tectonic, returns `application/pdf`. Temp files cleaned up after. |
| `POST` | `/api/resume/tailor` | Body `{job_id}`. Fetches stored reference + job description from DB, calls LLM, returns `{tex_content}`. |

Compilation detail: backend writes `.tex` to a temp file, runs `tectonic <file>` via `asyncio.create_subprocess_exec`, reads the output `.pdf`, returns as a streaming response. If Tectonic exits non-zero, return a 422 with stderr as the error message. Frontend displays the error in a dismissible alert below the status bar; the PDF panel retains the last successful compile.

---

## LLM Tailoring

New `tailor_resume(tex_content: str, job_description: str) -> str` method added to `LlmAdapter` protocol and all three adapters (Groq, Cerebras, Gemini).

Uses the summarize-tier adapter (Cerebras llama-3.3-70b, Gemini fallback) since output quality matters.

**System prompt:** "You are a resume tailoring expert. Given a LaTeX resume and a job description, return ONLY the modified LaTeX source code. No explanation, no markdown code fences, no commentary of any kind - just the raw .tex content."

**User prompt:** Provides the full `.tex` source and job description. Instructs the LLM to emphasize relevant skills and experience, adjust bullet points to highlight matching technologies, and reorder content if beneficial - while preserving the original LaTeX template structure and commands.

---

## Docker / Tectonic

**Dockerfile:** Download the pre-built Tectonic musl binary (~10 MB, no Rust toolchain needed). Also install `libfontconfig1` for font rendering.

```dockerfile
RUN apt-get install -y libfontconfig1 libssl-dev && \
    curl -L "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-musl.tar.gz" \
    | tar xz -C /usr/local/bin
```

**docker-compose.yml:** Add a named volume for Tectonic's package cache so downloaded LaTeX packages survive container restarts:

```yaml
volumes:
  tectonic_cache:
    driver: local

services:
  app:
    volumes:
      - tectonic_cache:/root/.cache/Tectonic
```

---

## Frontend

### New files

**`frontend/src/api/resume.ts`** - API client with four functions:
- `getResume()` - GET /api/resume
- `saveResume(texContent)` - PUT /api/resume
- `compileResume(texContent)` - POST /api/resume/compile, returns `ArrayBuffer`
- `tailorResume(jobId)` - POST /api/resume/tailor, returns `{tex_content}`

**`frontend/src/pages/Resume.tsx`** - Two-panel layout:
- Left panel: Monaco editor with LaTeX syntax highlighting (`@monaco-editor/react`)
- Right panel: `<iframe>` displaying a blob URL from the compiled PDF
- Toolbar across the top (see below)
- Status bar below the toolbar

### Modified files

- **`App.tsx`** - add `/resume` route
- **`Sidebar.tsx`** - add Resume nav item (FileText icon), between Insights and Settings
- **`Matches.tsx`** - add "Tailor Resume" button on each match card, navigates to `/resume?jobId=<id>`

### Toolbar

```
[ Job: [dropdown ▾] ] [ ✦ Tailor ] [ ▶ Compile ] [ ↓ PDF ]    [ Upload .tex ]
```

- **Job dropdown:** populated from existing matches API. Pre-selected when `?jobId=` is in the URL.
- **Tailor:** disabled if no job selected or no reference resume saved.
- **Compile:** sends current editor content to compile endpoint, updates PDF panel.
- **↓ PDF:** downloads the most recently compiled PDF. Disabled until compiled.
- **Upload .tex:** file picker accepting `.tex` files. Loads content into editor. User must click "Save as Reference" to persist.

### Status bar

Shown below the toolbar, one line, context-sensitive:

| State | Display |
|---|---|
| No resume uploaded | "No resume yet - upload a .tex file to get started" |
| Clean (editor matches reference) | "Reference saved [relative time]" |
| Dirty (unsaved edits) | "Unsaved changes · [Save as Reference] [↩ Reset]" |
| Tailored | "✦ Tailored for [title] @ [company] · [Save as Reference] [↩ View Reference]" |

**"View Reference"** loads `referenceContent` back into the editor and clears `tailoredFor`.
**"Save as Reference"** calls `PUT /api/resume`, updates `referenceContent` and `updated_at`.

### Key frontend state (`Resume.tsx`)

```typescript
editorContent: string           // current Monaco content
referenceContent: string | null // last saved reference (for dirty check)
tailoredFor: { jobId: number; title: string; company: string } | null
pdfUrl: string | null           // blob URL, set after successful compile
isCompiling: boolean
isTailoring: boolean
```

On mount with `?jobId=`: pre-selects that job in the dropdown. Does **not** auto-trigger tailor - user clicks the button themselves.

### Package additions

- `@monaco-editor/react` - Monaco editor React wrapper

---

## Out of Scope (v1)

- Multiple resume versions / history
- Overleaf API sync (manual upload only)
- LaTeX error highlighting in the editor
- Auto-compile on keystroke
- Zip file import (Overleaf project export) - single `.tex` only
