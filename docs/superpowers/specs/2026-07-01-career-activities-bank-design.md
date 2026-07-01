# Career Activities Bank + Tailoring Pipeline Redesign

**Date:** 2026-07-01
**Status:** Approved

## Problem

The reference `.tex` resume is a curated 1-2 page snapshot of a person's career. The existing single-step tailor pipeline can only rearrange and emphasise content already present in that file. There is no mechanism to surface relevant accomplishments that were deliberately left out of the baseline resume due to space constraints.

Additionally, the single-step prompt simultaneously handles job understanding, content selection, restructuring, and LaTeX formatting - too many concerns in one call, leading to unpredictable output quality.

## Goals

1. Give users a persistent freeform document to maintain a comprehensive record of all their professional activities.
2. Redesign the tailoring pipeline so the LLM selects the most relevant content before rewriting LaTeX, rather than doing both in one pass.
3. Provide real-time progress feedback during the multi-phase tailor operation.

## Out of Scope

- Structured/form-based activity entry (each entry has explicit fields).
- Activities-only tailoring (reference `.tex` remains required as the structural template).
- Separate model tier for cheaper phases (all phases use the user's configured LLM provider).
- Pre-filtering or chunking the activities document before sending to the LLM.

---

## Data Model

### Change: `resume` table

Add one nullable column to the existing `resume` table. No new table is needed - the activities document is per-user and resume-adjacent.

```
ALTER TABLE resume ADD COLUMN activities_content TEXT;
```

Delivered via an Alembic migration. `activities_content` is `NULL` until the user saves content for the first time.

No other model changes.

---

## API

Two new endpoints added to the existing `/resume` router (`backend/routers/resume.py`).

### `GET /resume/activities`

Returns the user's current activities document.

**Response**
```json
{
  "activities_content": "string | null",
  "updated_at": "ISO 8601 datetime | null"
}
```

### `PUT /resume/activities`

Saves (upserts) the activities document.

**Request body**
```json
{
  "activities_content": "string"
}
```

**Response**: same shape as GET.

`updated_at` on the `resume` row is refreshed on every PUT. Authentication and ownership checks follow the same pattern as the existing `PUT /resume` endpoint.

---

## Backend: 3-Phase Tailoring Pipeline

The existing `tailor_resume(tex_content, job_description)` method on the LLM protocol is replaced with a 3-phase pipeline. Each phase is a separate LLM call using the user's configured provider (selected via the existing `get_tailor_provider(settings)` factory).

### Phase 1 - Job Analysis

**Input:** `job_description: str`

**Output:** Structured JSON object:
```json
{
  "required_skills": ["..."],
  "preferred_skills": ["..."],
  "key_themes": ["..."],
  "seniority_signals": ["..."],
  "keywords": ["..."]
}
```

**Prompt intent:** Extract the concrete signals from the job description without any knowledge of the candidate. Small, focused output.

**New function:** `analyze_job(job_description: str) -> dict`

---

### Phase 2 - Activity Selection

**Input:**
- `requirements: dict` (Phase 1 output)
- `tex_content: str` (reference resume - so the LLM knows what is already covered)
- `activities_content: str | None` (the activities document)

**Output:** Plain-text list of the 6-8 most relevant items to emphasise, drawn from both sources. Each item is a short excerpt or paraphrase - not LaTeX.

**Prompt constraints (explicit in system prompt):**
- Do not surface everything. Select only items that genuinely strengthen this specific application.
- Reference resume is provided for context - do not duplicate content verbatim, but do note which existing bullets to prioritise.
- If `activities_content` is null or empty, select from the reference resume only.

**New function:** `select_activities(requirements: dict, tex_content: str, activities_content: str | None) -> str`

---

### Phase 3 - Tailor

**Input:**
- `tex_content: str` (reference resume, used as structural template)
- `selected_items: str` (Phase 2 output)

**Output:** Modified LaTeX string.

**Prompt intent:** Identical to the current tailor prompt but with a tight context - no raw job description, no activities dump. The LLM receives a concise brief of what to incorporate and rewrites accordingly.

**Updated function:** `tailor_resume(tex_content: str, selected_items: str) -> str`

The existing `build_tailor_prompt(tex_content, job_description)` in `backend/llm/prompts.py` is updated to accept `selected_items` instead of `job_description`.

---

### Graceful Degradation

| Condition | Behaviour |
|---|---|
| `activities_content` is null/empty | Phase 2 runs with reference resume only; pipeline continues normally |
| Phase 1 fails | Error propagated via SSE; no partial output applied to editor |
| Phase 2 fails | Same |
| Phase 3 fails | Same |
| No reference resume | Tailor button already disabled in UI; no backend change needed |

---

### SSE Progress Events

The existing `/resume/tailor` endpoint already returns a response. It is updated to stream SSE events mirroring the run-progress pattern already used in `backend/routers/runs.py`.

Three progress events emitted in sequence:

```
event: phase
data: {"phase": 1, "label": "Analyzing job requirements..."}

event: phase
data: {"phase": 2, "label": "Selecting relevant experiences..."}

event: phase
data: {"phase": 3, "label": "Tailoring resume..."}

event: done
data: {"tex_content": "...modified LaTeX..."}
```

On error:
```
event: error
data: {"detail": "..."}
```

---

## Frontend: Activities Page

### Route

`/activities` - new entry in the sidebar navigation, between Resume and Settings (or wherever it fits naturally in the nav order).

### Layout

Two-panel layout mirroring the Resume page:

- **Left panel:** Monaco Editor instance in `plaintext` or `markdown` language mode. Full-height, no toolbar beyond Save.
- **Right panel:** Live markdown preview rendered from the editor content. On by default.

A toggle button (e.g., top-right of the preview panel) collapses the preview so the editor expands to full width. State is local (not persisted).

### Toolbar

```
[Activities]                    [Last saved: 3 min ago]  [Save]
```

- Save button calls `PUT /resume/activities`.
- Last-saved timestamp updates on successful save.
- No compile, no tailor controls - those remain on the Resume page.

### Empty State

When `activities_content` is null, the editor shows placeholder text:

```
# Career Activities

Use this document to keep a running record of everything you've done professionally.
The AI uses this alongside your resume when tailoring for a specific job.

## Work Experience
- ...

## Projects
- ...

## Skills & Certifications
- ...
```

This placeholder is not saved - it disappears as soon as the user starts typing.

### API Integration

- `GET /resume/activities` on page load (via TanStack Query, same pattern as the Resume page).
- `PUT /resume/activities` on Save button click.
- Invalidate query on successful save to refresh `updated_at`.

---

## Frontend: Resume Page Changes

### Tailor button flow

The existing tailor button triggers `POST /resume/tailor` which now returns SSE. The frontend switches from a simple loading spinner to a 3-step progress indicator:

```
[ ] Analyzing job requirements...
[✓] Selecting relevant experiences...
[ ] Tailoring resume...
```

Steps check off as each `phase` SSE event arrives. On `done`, the editor content is replaced with the returned `tex_content` and the status bar updates to the current "Tailored for X @ Y" state. On `error`, the existing error display is used.

No other changes to the Resume page.

---

## File Change Summary

| File | Change |
|---|---|
| `backend/models/resume.py` | Add `activities_content: Mapped[str | None]` column |
| `backend/alembic/versions/<new>.py` | Migration: add `activities_content` to `resume` |
| `backend/routers/resume.py` | Add `GET/PUT /activities` endpoints; update `/tailor` to SSE + 3-phase |
| `backend/llm/protocol.py` | Add `analyze_job()`, `select_activities()`; update `tailor_resume()` signature |
| `backend/llm/prompts.py` | Add `build_job_analysis_prompt()`, `build_activity_selection_prompt()`; update `build_tailor_prompt()` |
| `backend/llm/{groq,cerebras,gemini}_adapter.py` | Implement new protocol methods |
| `frontend/src/api/resume.ts` | Add `getActivities()`, `saveActivities()` |
| `frontend/src/pages/Activities.tsx` | New page |
| `frontend/src/App.tsx` | Add `/activities` route |
| `frontend/src/components/Sidebar.tsx` | Add Activities nav item |
| `frontend/src/pages/Resume.tsx` | Update tailor flow to consume SSE + render 3-step progress |
