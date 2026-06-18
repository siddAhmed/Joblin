# BYOK Onboarding — Design Spec

**Date:** 2026-06-18
**Status:** Approved

## Overview

New users must provide their own Groq and Cerebras API keys during onboarding before they can use the app. A new Step 1 gates the rest of the onboarding flow on validated key entry. Gemini is optional and can be supplied at this step or later in Settings > LLM Keys.

Keys are stored in the existing `settings` table (key-value per user) — no schema changes required. The `PATCH /api/settings` endpoint already handles writing these values.

---

## Onboarding Step Order (Updated)

| # | Step | Required |
|---|------|----------|
| 1 | **API Keys** (new) | Yes |
| 2 | Discord webhook | No |
| 3 | Criteria configuration | No |
| 4 | Company selection | Yes |
| 5 | Test run | No |

---

## Backend Changes

### 1. `GET /api/onboarding-status` (modified)

Currently returns `needs_onboarding: true` if `company_count == 0`. Updated to also return `true` if either `groq_api_key` or `cerebras_api_key` is absent from the user's settings rows.

```python
has_groq = await get_setting(session, "groq_api_key", current_user.id)
has_cerebras = await get_setting(session, "cerebras_api_key", current_user.id)
needs_onboarding = company_count == 0 or not has_groq or not has_cerebras
return {"needs_onboarding": needs_onboarding}
```

This means a user with companies but missing keys (degraded state) is also sent back through full onboarding starting at Step 1.

The admin user (user 1) is unaffected because `seed_defaults` writes keys from env on startup.

### 2. `POST /api/settings/validate-keys` (new)

Validates raw key values against live provider APIs without persisting them. Added to `backend/routers/settings.py`.

**Request body:**
```json
{
  "groq_api_key": "gsk_...",
  "cerebras_api_key": "csk_...",
  "gemini_api_key": "AIza..."
}
```
All fields optional; only non-empty provided keys are tested.

**Response (200 — all tested keys valid):**
```json
{
  "groq":     { "valid": true,  "error": null },
  "cerebras": { "valid": true,  "error": null }
}
```

**Response (422 — any tested key fails):**
```json
{
  "groq":     { "valid": false, "error": "Invalid API key" },
  "cerebras": { "valid": true,  "error": null }
}
```

HTTP 200 only when all provided keys pass. HTTP 422 if any provided key fails. Per-provider detail is always in the body.

**Validation implementation:** Instantiate the provider SDK client with the given key and call `chat.completions.create` with `max_tokens=1` and a minimal prompt. Models used:
- Groq: `llama-3.1-8b-instant`
- Cerebras: `gpt-oss-120b`
- Gemini: `gemini-2.0-flash-lite`

Auth errors from the SDK → `valid: false, error: <SDK message>`. Network/timeout errors → `valid: false, error: "Could not reach provider"`.

---

## Frontend Changes

### 1. `frontend/src/api/settings.ts`

Add:
```ts
validateKeys: (keys: { groq_api_key?: string; cerebras_api_key?: string; gemini_api_key?: string }) =>
  axios.post('/api/settings/validate-keys', keys)
```

### 2. `frontend/src/pages/Onboarding.tsx`

- Shift all existing step indices up by 1.
- Insert new Step 1: **API Keys**.

**Step 1 UI layout:**
- Heading: "Connect your AI providers"
- Subheading: "Joblin uses Groq and Cerebras to filter and summarize job listings. Paste your API keys below."
- Two required provider cards (Groq, Cerebras) + one optional card (Gemini), each containing:
  - Provider name
  - Password `<input>` for the key
  - A "Get your key" external link:
    - Groq: `https://console.groq.com/keys`
    - Cerebras: `https://cloud.cerebras.ai/` with tooltip "API Keys in the sidebar"
    - Gemini: `https://aistudio.google.com/apikey`
  - Inline validation indicator: idle → loading spinner → green check (valid) → red error message
- Single **"Test keys"** button that validates all non-empty fields in parallel via `POST /api/settings/validate-keys`
- **"Next"** button: disabled until both Groq and Cerebras show `valid: true`

**Interaction flow:**
1. User pastes keys into fields.
2. Clicks "Test keys" — `validateKeys()` mutation fires with current field values.
3. Per-provider `valid`/`error` state drives inline indicators.
4. Once Groq + Cerebras are both valid, "Next" becomes active.
5. Clicking "Next" calls `settingsApi.update({ groq_api_key, cerebras_api_key, gemini_api_key? })` then advances to Step 2.

Keys are not persisted until "Next" is clicked, preventing partial writes on abandonment.

**State shape for this step:**
```ts
type KeyState = { value: string; status: 'idle' | 'loading' | 'valid' | 'error'; error: string | null }

const [groq, setGroq]         = useState<KeyState>({ value: '', status: 'idle', error: null })
const [cerebras, setCerebras] = useState<KeyState>({ value: '', status: 'idle', error: null })
const [gemini, setGemini]     = useState<KeyState>({ value: '', status: 'idle', error: null })
```

Changing a key field after a successful validation resets its status to `idle` (forces re-test before Next).

---

## Out of Scope

- Groq/Cerebras free-tier rate limit warnings
- Key rotation or re-validation after initial onboarding (handled by Settings > LLM Keys)
- Showing masked existing keys when re-entering onboarding (existing keys are not pre-filled for security)
