# BYOK Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate the onboarding flow on users supplying their own Groq and Cerebras API keys, with live validation against provider APIs before saving.

**Architecture:** New `POST /api/settings/validate-keys` endpoint runs 1-token completions against each provider SDK in parallel and returns per-provider pass/fail. `GET /api/onboarding-status` gains a second condition: returns `needs_onboarding: true` if either required key row is absent from the user's settings. A new Step 1 in `Onboarding.tsx` collects and validates keys before allowing the user to proceed; saving is deferred to the "Next" click.

**Tech Stack:** Python/FastAPI (groq, cerebras.cloud.sdk, google.genai SDKs), React/TypeScript, @tanstack/react-query, Axios, Tailwind CSS.

## Global Constraints

- No database schema changes — keys are stored in the existing `settings` key-value table via `PATCH /api/settings`.
- Groq and Cerebras keys are required; Gemini is optional.
- Do NOT use `get_setting()` / `DEFAULTS` for the onboarding gate — `DEFAULTS` falls back to env values, which would bypass the gate for all users. Query `Setting` rows directly.
- No Co-Authored-By trailers in commits.
- No em dashes in any prose.

---

## File Map

| File | Change |
|------|--------|
| `backend/routers/settings.py` | Add `POST /api/settings/validate-keys` endpoint + helper functions |
| `backend/routers/system.py` | Add direct Setting row checks to `onboarding_status` |
| `tests/test_validate_keys.py` | New: tests for the validate-keys endpoint |
| `tests/test_health.py` | Add three new onboarding-status gate tests |
| `frontend/src/api/settings.ts` | Add `validateKeys` function + response types |
| `frontend/src/pages/Onboarding.tsx` | Renumber steps 1-4 → 2-5; insert new Step 1 (API Keys) |

---

## Task 1: POST /api/settings/validate-keys endpoint

**Files:**
- Modify: `backend/routers/settings.py`
- Create: `tests/test_validate_keys.py`

**Interfaces:**
- Produces: `POST /api/settings/validate-keys` — accepts `{groq_api_key?, cerebras_api_key?, gemini_api_key?}`, returns `{groq?: {valid, error}, cerebras?: {valid, error}, gemini?: {valid, error}}` with HTTP 200 (all pass) or 422 (any fail).

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validate_keys.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch


async def test_validate_keys_all_valid(client):
    mock_resp = MagicMock()
    with patch("backend.routers.settings.AsyncGroq") as mock_groq, \
         patch("backend.routers.settings.AsyncCerebras") as mock_cerebras:
        mock_groq.return_value.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_cerebras.return_value.chat.completions.create = AsyncMock(return_value=mock_resp)
        response = await client.post("/api/settings/validate-keys", json={
            "groq_api_key": "gsk_valid",
            "cerebras_api_key": "csk_valid",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["groq"]["valid"] is True
    assert data["groq"]["error"] is None
    assert data["cerebras"]["valid"] is True
    assert data["cerebras"]["error"] is None
    assert "gemini" not in data


async def test_validate_keys_invalid_groq_returns_422(client):
    mock_resp = MagicMock()
    with patch("backend.routers.settings.AsyncGroq") as mock_groq, \
         patch("backend.routers.settings.AsyncCerebras") as mock_cerebras:
        mock_groq.return_value.chat.completions.create = AsyncMock(
            side_effect=Exception("Invalid API key")
        )
        mock_cerebras.return_value.chat.completions.create = AsyncMock(return_value=mock_resp)
        response = await client.post("/api/settings/validate-keys", json={
            "groq_api_key": "gsk_bad",
            "cerebras_api_key": "csk_valid",
        })
    assert response.status_code == 422
    data = response.json()
    assert data["groq"]["valid"] is False
    assert "Invalid API key" in data["groq"]["error"]
    assert data["cerebras"]["valid"] is True


async def test_validate_keys_empty_fields_skipped(client):
    response = await client.post("/api/settings/validate-keys", json={
        "groq_api_key": "",
        "cerebras_api_key": "",
    })
    assert response.status_code == 200
    assert response.json() == {}


async def test_validate_keys_optional_gemini_included_when_provided(client):
    mock_resp = MagicMock()
    with patch("backend.routers.settings.AsyncGroq") as mock_groq, \
         patch("backend.routers.settings.AsyncCerebras") as mock_cerebras, \
         patch("backend.routers.settings.genai") as mock_genai:
        mock_groq.return_value.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_cerebras.return_value.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        response = await client.post("/api/settings/validate-keys", json={
            "groq_api_key": "gsk_valid",
            "cerebras_api_key": "csk_valid",
            "gemini_api_key": "AIza_valid",
        })
    assert response.status_code == 200
    data = response.json()
    assert "gemini" in data
    assert data["gemini"]["valid"] is True
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_validate_keys.py -v
```

Expected: all 4 tests fail with `404 Not Found` or `ImportError`.

- [ ] **Step 3: Add the endpoint to backend/routers/settings.py**

Add these imports at the top of `backend/routers/settings.py` (after the existing imports):

```python
import asyncio
from typing import Optional

from fastapi.responses import JSONResponse
from groq import AsyncGroq
from cerebras.cloud.sdk import AsyncCerebras
from google import genai
```

Add this Pydantic model after the existing `CriteriaTestRequest` class:

```python
class ValidateKeysRequest(BaseModel):
    groq_api_key: str = ""
    cerebras_api_key: str = ""
    gemini_api_key: str = ""


class KeyResult(BaseModel):
    valid: bool
    error: Optional[str] = None
```

Add these private helpers and the new route at the bottom of `backend/routers/settings.py`:

```python
async def _check_groq(api_key: str) -> KeyResult:
    try:
        client = AsyncGroq(api_key=api_key)
        await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        return KeyResult(valid=True)
    except Exception as exc:
        return KeyResult(valid=False, error=(str(exc) or "Could not reach provider")[:200])


async def _check_cerebras(api_key: str) -> KeyResult:
    try:
        client = AsyncCerebras(api_key=api_key)
        await client.chat.completions.create(
            model="gpt-oss-120b",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        return KeyResult(valid=True)
    except Exception as exc:
        return KeyResult(valid=False, error=(str(exc) or "Could not reach provider")[:200])


async def _check_gemini(api_key: str) -> KeyResult:
    try:
        client = genai.Client(api_key=api_key)
        await client.aio.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents="hi",
        )
        return KeyResult(valid=True)
    except Exception as exc:
        return KeyResult(valid=False, error=(str(exc) or "Could not reach provider")[:200])


@router.post("/validate-keys")
async def validate_keys(body: ValidateKeysRequest, current_user: CurrentUser):
    checks: dict[str, object] = {}
    if body.groq_api_key:
        checks["groq"] = _check_groq(body.groq_api_key)
    if body.cerebras_api_key:
        checks["cerebras"] = _check_cerebras(body.cerebras_api_key)
    if body.gemini_api_key:
        checks["gemini"] = _check_gemini(body.gemini_api_key)

    if not checks:
        return JSONResponse(content={}, status_code=200)

    results_list = await asyncio.gather(*checks.values())
    results: dict[str, KeyResult] = dict(zip(checks.keys(), results_list))

    any_invalid = any(not r.valid for r in results.values())
    return JSONResponse(
        content={k: v.model_dump() for k, v in results.items()},
        status_code=422 if any_invalid else 200,
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/test_validate_keys.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```
git add backend/routers/settings.py tests/test_validate_keys.py
git commit -m "feat: add POST /api/settings/validate-keys endpoint"
```

---

## Task 2: Onboarding-status key gate

**Files:**
- Modify: `backend/routers/system.py`
- Modify: `tests/test_health.py`

**Interfaces:**
- Consumes: `Setting` model (direct DB rows, bypassing DEFAULTS env fallback)
- Produces: `GET /api/onboarding-status` now returns `needs_onboarding: true` if either `groq_api_key` or `cerebras_api_key` row is missing or empty for the current user.

---

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_health.py`:

```python
from unittest.mock import patch
from backend.scrapers.probe import ProbeResult


async def test_onboarding_needed_on_fresh_user(client):
    response = await client.get("/api/onboarding-status")
    assert response.status_code == 200
    assert response.json()["needs_onboarding"] is True


async def test_onboarding_needed_when_keys_missing_but_has_companies(client):
    mock_probe = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        await client.post("/api/companies", json={"name": "Acme", "careers_url": "https://acme.com/jobs"})

    response = await client.get("/api/onboarding-status")
    assert response.status_code == 200
    assert response.json()["needs_onboarding"] is True


async def test_onboarding_not_needed_when_keys_and_companies_exist(client):
    mock_probe = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])
    with patch("backend.routers.companies.probe_ats", return_value=mock_probe):
        await client.post("/api/companies", json={"name": "Acme", "careers_url": "https://acme.com/jobs"})
    await client.patch("/api/settings", json={
        "groq_api_key": "gsk_test",
        "cerebras_api_key": "csk_test",
    })

    response = await client.get("/api/onboarding-status")
    assert response.status_code == 200
    assert response.json()["needs_onboarding"] is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_health.py -v
```

Expected: the two new tests that check for key gates fail (the current endpoint only checks company count).

- [ ] **Step 3: Update backend/routers/system.py**

Add `Setting` to the imports at the top of `backend/routers/system.py`:

```python
from backend.models.setting import Setting
```

Replace the `onboarding_status` function body:

```python
@router.get("/onboarding-status")
async def onboarding_status(session: Session, current_user: CurrentUser):
    company_count = (await session.execute(
        select(func.count()).select_from(Company).where(Company.user_id == current_user.id)
    )).scalar_one()

    groq_row = (await session.execute(
        select(Setting).where(Setting.user_id == current_user.id, Setting.key == "groq_api_key")
    )).scalar_one_or_none()
    cerebras_row = (await session.execute(
        select(Setting).where(Setting.user_id == current_user.id, Setting.key == "cerebras_api_key")
    )).scalar_one_or_none()

    has_groq = bool(groq_row and groq_row.value)
    has_cerebras = bool(cerebras_row and cerebras_row.value)

    return {"needs_onboarding": company_count == 0 or not has_groq or not has_cerebras}
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/test_health.py -v
```

Expected: all 5 tests pass (2 pre-existing + 3 new).

- [ ] **Step 5: Run the full test suite to catch regressions**

```
pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```
git add backend/routers/system.py tests/test_health.py
git commit -m "feat: gate onboarding-status on groq + cerebras key presence"
```

---

## Task 3: Frontend - API client + new onboarding Step 1

**Files:**
- Modify: `frontend/src/api/settings.ts`
- Modify: `frontend/src/pages/Onboarding.tsx`

**Interfaces:**
- Consumes: `POST /api/settings/validate-keys` (Task 1), `PATCH /api/settings` (existing)
- Produces: New Step 1 UI in onboarding; existing steps renumbered 2-5.

**Note:** There are no frontend tests in this project. Verify this task by starting the dev server.

---

- [ ] **Step 1: Add validateKeys to frontend/src/api/settings.ts**

Replace the entire file content with:

```typescript
import { api } from "./client";

export type KeyValidationResult = { valid: boolean; error: string | null }
export type ValidateKeysResponse = {
  groq?: KeyValidationResult
  cerebras?: KeyValidationResult
  gemini?: KeyValidationResult
}

export const settingsApi = {
  get: () => api.get("/settings").then((r) => r.data),
  update: (data: Record<string, unknown>) => api.patch("/settings", data).then((r) => r.data),
  testDiscord: () => api.post("/settings/discord/test").then((r) => r.data),
  testCriteria: (description: string) =>
    api.post("/settings/criteria/test", { description }).then((r) => r.data),
  listPresets: () => api.get("/presets").then((r) => r.data),
  applyPreset: (name: string) => api.post(`/presets/${name}/apply`).then((r) => r.data),
  validateKeys: (keys: { groq_api_key?: string; cerebras_api_key?: string; gemini_api_key?: string }) =>
    api
      .post<ValidateKeysResponse>("/settings/validate-keys", keys)
      .then((r) => r.data)
      .catch((err) => {
        if (err.response?.status === 422) return err.response.data as ValidateKeysResponse;
        throw err;
      }),
};
```

- [ ] **Step 2: Replace frontend/src/pages/Onboarding.tsx**

Replace the entire file with the following. The key changes from the original are:
- `type Step = 1 | 2 | 3 | 4 | 5`
- `KeyState` type + three key state variables
- `validateKeysMutation` and `saveKeys` mutations
- `stepLabels` gains "API Keys" at index 0
- All `step === 1/2/3/4` and `setStep(...)` references shifted up by 1
- New `{step === 1 && ...}` block added before the old step 1

```typescript
import { useState } from "react";
import { useQueryClient, useMutation, useQuery } from "@tanstack/react-query";
import { settingsApi } from "@/api/settings";
import type { ValidateKeysResponse } from "@/api/settings";
import { companiesApi } from "@/api/companies";
import type { DefaultCompany } from "@/api/companies";
import { runsApi } from "@/api/runs";
import { TagChips } from "@/components/TagChips";

type Step = 1 | 2 | 3 | 4 | 5;
type KeyState = { value: string; status: "idle" | "loading" | "valid" | "error"; error: string | null };

interface Preset {
  name: string;
  label: string;
  description: string;
  group: "experienced" | "intern";
  criteria: Record<string, unknown>;
}

interface CriteriaValues {
  title_allowlist: string;
  title_denylist: string;
  location_allowlist: string;
  location_denylist: string;
  seniority_allowlist: string[];
  exclusion_keywords: string[];
  profile_description: string;
}

const SENIORITY_SUGGESTIONS = [
  "Senior", "Staff", "Principal", "Lead", "Mid",
  "Junior", "Intern", "New Grad", "Associate", "Entry Level",
];

function toCriteriaValues(raw: Record<string, unknown>): CriteriaValues {
  return {
    title_allowlist: (raw.title_allowlist as string) ?? "",
    title_denylist: (raw.title_denylist as string) ?? "",
    location_allowlist: (raw.location_allowlist as string) ?? "",
    location_denylist: (raw.location_denylist as string) ?? "",
    seniority_allowlist: Array.isArray(raw.seniority_allowlist) ? (raw.seniority_allowlist as string[]) : [],
    exclusion_keywords: Array.isArray(raw.exclusion_keywords) ? (raw.exclusion_keywords as string[]) : [],
    profile_description: (raw.profile_description as string) ?? "",
  };
}

export function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState<Step>(1);

  // Step 1 state
  const [groq, setGroq] = useState<KeyState>({ value: "", status: "idle", error: null });
  const [cerebras, setCerebras] = useState<KeyState>({ value: "", status: "idle", error: null });
  const [gemini, setGemini] = useState<KeyState>({ value: "", status: "idle", error: null });

  // Step 2+ state
  const [webhookUrl, setWebhookUrl] = useState("");
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [testRunId, setTestRunId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [deselected, setDeselected] = useState<Set<string>>(new Set());
  const [stage, setStage] = useState<"experienced" | "intern" | null>(null);
  const [criteria, setCriteria] = useState<CriteriaValues | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const qc = useQueryClient();

  const { data: defaultCompanies = [] } = useQuery<DefaultCompany[]>({
    queryKey: ["companies-defaults"],
    queryFn: companiesApi.defaults,
    enabled: step === 4,
  });

  const { data: presets = [], isPending: presetsLoading, isError: presetsError } = useQuery<Preset[]>({
    queryKey: ["presets"],
    queryFn: settingsApi.listPresets,
    enabled: step === 3,
  });

  const filteredCompanies = defaultCompanies.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  const selectedCount = defaultCompanies.length - deselected.size;

  const toggleCompany = (name: string) => {
    setDeselected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const selectAll = () => setDeselected(new Set());
  const deselectAll = () =>
    setDeselected(new Set(defaultCompanies.map((c) => c.name)));

  // Step 1 mutations
  const validateKeysMutation = useMutation({
    mutationFn: (keys: { groq_api_key?: string; cerebras_api_key?: string; gemini_api_key?: string }) =>
      settingsApi.validateKeys(keys),
    onMutate: (keys) => {
      if (keys.groq_api_key) setGroq((g) => ({ ...g, status: "loading" }));
      if (keys.cerebras_api_key) setCerebras((c) => ({ ...c, status: "loading" }));
      if (keys.gemini_api_key) setGemini((g) => ({ ...g, status: "loading" }));
    },
    onSuccess: (data: ValidateKeysResponse) => {
      if (data.groq) setGroq((g) => ({ ...g, status: data.groq!.valid ? "valid" : "error", error: data.groq!.error }));
      if (data.cerebras) setCerebras((c) => ({ ...c, status: data.cerebras!.valid ? "valid" : "error", error: data.cerebras!.error }));
      if (data.gemini) setGemini((g) => ({ ...g, status: data.gemini!.valid ? "valid" : "error", error: data.gemini!.error }));
    },
  });

  const saveKeys = useMutation({
    mutationFn: () => {
      const payload: Record<string, string> = {
        groq_api_key: groq.value,
        cerebras_api_key: cerebras.value,
      };
      if (gemini.value) payload.gemini_api_key = gemini.value;
      return settingsApi.update(payload);
    },
    onSuccess: () => setStep(2),
  });

  // Step 2 mutations
  const saveWebhook = useMutation({
    mutationFn: () => settingsApi.update({ discord_webhook_url: webhookUrl }),
    onSuccess: () => setStep(3),
  });

  const saveCriteria = useMutation({
    mutationFn: (c: CriteriaValues) => settingsApi.update({ criteria: c }),
    onSuccess: () => setStep(4),
  });

  const importCompanies = useMutation({
    mutationFn: async () => {
      const selected = defaultCompanies.filter((c) => !deselected.has(c.name));
      await companiesApi.bulk(selected);
    },
    onSuccess: () => setStep(5),
  });

  const startTestRun = useMutation({
    mutationFn: () => runsApi.start({ preview: true }),
    onSuccess: (data) => setTestRunId(data.id),
  });

  const finish = () => {
    qc.invalidateQueries({ queryKey: ["companies"] });
    qc.invalidateQueries({ queryKey: ["onboarding-status"] });
    onComplete();
  };

  const stepLabels = ["API Keys", "Discord", "Criteria", "Companies", "Test run"];

  return (
    <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[#e5e5e5]">
            Welcome to Job<span className="text-[#4e9eff]">lin</span>
          </h1>
          <p className="text-sm text-[#666] mt-1">Let's get you set up in 5 steps.</p>
        </div>

        <div className="flex gap-1 mb-6">
          {stepLabels.map((label, i) => (
            <div key={label} className="flex-1 text-center">
              <div className={`h-1 rounded mb-1 ${i + 1 <= step ? "bg-[#4e9eff]" : "bg-[#222]"}`} />
              <span className={`text-[10px] ${i + 1 === step ? "text-[#4e9eff]" : "text-[#555]"}`}>
                {label}
              </span>
            </div>
          ))}
        </div>

        <div className="border border-[#2a2a2a] rounded-xl p-6 bg-[#111]">
          {step === 1 && (
            <div>
              <h2 className="text-sm font-semibold mb-2">Step 1: Connect your AI providers</h2>
              <p className="text-xs text-[#666] mb-4">
                Joblin uses Groq and Cerebras to filter and summarize job listings. Paste your API keys below.
              </p>

              {/* Groq card */}
              <div className="border border-[#2a2a2a] rounded-lg p-4 mb-3 bg-[#0a0a0a]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[#e5e5e5]">
                    Groq
                    <span className="text-[#f87171] text-[10px] ml-2">required</span>
                  </span>
                  <a
                    href="https://console.groq.com/keys"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] text-[#4e9eff] hover:underline"
                  >
                    Get your key →
                  </a>
                </div>
                <input
                  type="password"
                  value={groq.value}
                  onChange={(e) => setGroq({ value: e.target.value, status: "idle", error: null })}
                  placeholder="gsk_..."
                  className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                />
                {groq.status === "valid" && (
                  <p className="text-[10px] text-[#34d399] mt-1">Valid</p>
                )}
                {groq.status === "error" && (
                  <p className="text-[10px] text-[#f87171] mt-1">{groq.error}</p>
                )}
              </div>

              {/* Cerebras card */}
              <div className="border border-[#2a2a2a] rounded-lg p-4 mb-3 bg-[#0a0a0a]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[#e5e5e5]">
                    Cerebras
                    <span className="text-[#f87171] text-[10px] ml-2">required</span>
                  </span>
                  <a
                    href="https://cloud.cerebras.ai/"
                    target="_blank"
                    rel="noopener noreferrer"
                    title="API Keys in the sidebar"
                    className="text-[10px] text-[#4e9eff] hover:underline"
                  >
                    Get your key →
                  </a>
                </div>
                <input
                  type="password"
                  value={cerebras.value}
                  onChange={(e) => setCerebras({ value: e.target.value, status: "idle", error: null })}
                  placeholder="csk_..."
                  className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                />
                {cerebras.status === "valid" && (
                  <p className="text-[10px] text-[#34d399] mt-1">Valid</p>
                )}
                {cerebras.status === "error" && (
                  <p className="text-[10px] text-[#f87171] mt-1">{cerebras.error}</p>
                )}
              </div>

              {/* Gemini card */}
              <div className="border border-[#2a2a2a] rounded-lg p-4 mb-4 bg-[#0a0a0a]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[#e5e5e5]">
                    Gemini
                    <span className="text-[#555] text-[10px] ml-2">optional</span>
                  </span>
                  <a
                    href="https://aistudio.google.com/apikey"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] text-[#4e9eff] hover:underline"
                  >
                    Get your key →
                  </a>
                </div>
                <input
                  type="password"
                  value={gemini.value}
                  onChange={(e) => setGemini({ value: e.target.value, status: "idle", error: null })}
                  placeholder="AIza..."
                  className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                />
                {gemini.status === "valid" && (
                  <p className="text-[10px] text-[#34d399] mt-1">Valid</p>
                )}
                {gemini.status === "error" && (
                  <p className="text-[10px] text-[#f87171] mt-1">{gemini.error}</p>
                )}
              </div>

              <div className="flex gap-2 items-center">
                <button
                  onClick={() => {
                    const keys: { groq_api_key?: string; cerebras_api_key?: string; gemini_api_key?: string } = {};
                    if (groq.value) keys.groq_api_key = groq.value;
                    if (cerebras.value) keys.cerebras_api_key = cerebras.value;
                    if (gemini.value) keys.gemini_api_key = gemini.value;
                    validateKeysMutation.mutate(keys);
                  }}
                  disabled={validateKeysMutation.isPending || (!groq.value && !cerebras.value && !gemini.value)}
                  className="text-xs border border-[#2a2a2a] rounded px-4 py-2 text-[#888] bg-[#0a0a0a] disabled:opacity-40"
                >
                  {validateKeysMutation.isPending ? "Testing..." : "Test keys"}
                </button>
                <button
                  onClick={() => saveKeys.mutate()}
                  disabled={groq.status !== "valid" || cerebras.status !== "valid" || saveKeys.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                >
                  {saveKeys.isPending ? "Saving..." : "Next"}
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 2: Discord webhook</h2>
              <p className="text-xs text-[#666] mb-3">
                Create a webhook in your Discord server settings and paste the URL below.
                Joblin will notify you when strong matches are found.
              </p>
              <input
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://discord.com/api/webhooks/..."
                className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] mb-3"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => saveWebhook.mutate()}
                  disabled={saveWebhook.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040]"
                >
                  {saveWebhook.isPending ? "Saving..." : "Save and continue"}
                </button>
                <button onClick={() => setStep(3)} className="text-xs text-[#555] hover:text-[#888]">
                  Skip for now
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 3: Choose a job criteria preset</h2>

              {editorOpen && criteria ? (
                /* Sub-step C: Criteria editor */
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <button
                      onClick={() => { setEditorOpen(false); setShowAdvanced(false); }}
                      className="text-xs text-[#4e9eff] hover:underline"
                    >
                      ← Back
                    </button>
                    <span className="text-xs text-[#555]">
                      {presets.find((p) => p.name === selectedPreset)?.label}
                    </span>
                  </div>

                  <div className="bg-[#0e2040] border border-[#1e3a5f] rounded-lg p-3 mb-4">
                    <div className="text-xs text-[#90c4ff] font-semibold mb-2">⚡ How Joblin filters jobs — two layers</div>
                    <div className="space-y-2">
                      <div className="bg-[#0a1a30] rounded p-2">
                        <div className="text-[10px] text-[#f59e0b] font-semibold mb-1">Layer 1 — Heuristic filters (title, seniority, location, exclusions)</div>
                        <div className="text-[10px] text-[#7aa3cc] leading-relaxed">Fast, non-AI rules. A job that fails is <span className="text-[#fbbf24]">dropped immediately</span> — the AI never sees it. If your patterns are too strict, you'll miss good matches with no warning.</div>
                      </div>
                      <div className="bg-[#0a1a30] rounded p-2">
                        <div className="text-[10px] text-[#34d399] font-semibold mb-1">Layer 2 — AI scoring (profile description)</div>
                        <div className="text-[10px] text-[#7aa3cc] leading-relaxed">Jobs that pass heuristics are scored by AI using your profile. Contextual and forgiving — a richer, more specific profile gives better, more relevant scores.</div>
                      </div>
                    </div>
                  </div>

                  <div className="mb-3">
                    <div className="flex items-baseline gap-2 mb-1">
                      <label className="text-[10px] text-[#888] uppercase tracking-wider">Title must match</label>
                      <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                    </div>
                    <input
                      value={criteria.title_allowlist}
                      onChange={(e) => setCriteria({ ...criteria, title_allowlist: e.target.value })}
                      className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                    />
                    <p className="text-[9px] text-[#555] mt-1 leading-relaxed">Regex patterns, pipe-separated. Jobs whose title doesn't match any of these are discarded before AI scoring. Keep patterns broad — <span className="text-[#888]">"react" alone would miss "Frontend Engineer at Stripe"</span>.</p>
                  </div>

                  <div className="mb-3">
                    <div className="flex items-baseline gap-2 mb-1">
                      <label className="text-[10px] text-[#888] uppercase tracking-wider">Title must NOT match</label>
                      <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                    </div>
                    <input
                      value={criteria.title_denylist}
                      onChange={(e) => setCriteria({ ...criteria, title_denylist: e.target.value })}
                      className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                    />
                    <p className="text-[9px] text-[#555] mt-1 leading-relaxed">Jobs whose title matches any of these are discarded. Be precise — <span className="text-[#888]">"design" would also block "design systems engineer"</span>.</p>
                  </div>

                  <div className="mb-3">
                    <div className="flex items-baseline gap-2 mb-2">
                      <label className="text-[10px] text-[#888] uppercase tracking-wider">Seniority levels</label>
                      <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                    </div>
                    <TagChips
                      value={criteria.seniority_allowlist}
                      onChange={(v) => setCriteria({ ...criteria, seniority_allowlist: v })}
                      suggestions={SENIORITY_SUGGESTIONS}
                      color="blue"
                    />
                    <p className="text-[9px] text-[#555] mt-1 leading-relaxed">Inferred from the job title. <span className="text-[#888]">If seniority can't be inferred, the job passes through.</span> Leave all unchecked to skip this filter entirely.</p>
                  </div>

                  <div className="mb-3">
                    <div className="flex items-baseline gap-2 mb-1">
                      <label className="text-[10px] text-[#888] uppercase tracking-wider">Your profile</label>
                      <span className="text-[9px] bg-[#0a2010] border border-[#1a4a20] rounded px-1 py-px text-[#34d399]">AI scored</span>
                      <span className="text-[9px] text-[#34d399]">most impactful</span>
                    </div>
                    <textarea
                      value={criteria.profile_description}
                      onChange={(e) => setCriteria({ ...criteria, profile_description: e.target.value })}
                      rows={3}
                      className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                    />
                    <p className="text-[9px] text-[#555] mt-1 leading-relaxed">The AI reads this to score job relevance — it understands context, not just keywords. Include your tech stack, years of experience, what kind of company you want, and what you want to avoid. The more specific, the better your scores.</p>
                  </div>

                  <div className="border-t border-[#1a1a1a] pt-2 mb-2">
                    <button
                      type="button"
                      onClick={() => setShowAdvanced(!showAdvanced)}
                      className="text-[10px] text-[#555] hover:text-[#888]"
                    >
                      {showAdvanced ? "▼" : "▶"} Advanced — location filters &amp; exclusion phrases
                    </button>
                    <p className="text-[9px] text-[#444] mt-1">These are also heuristic filters. Use them if you have specific geographic or content requirements.</p>
                  </div>

                  {showAdvanced && (
                    <div className="space-y-3 mb-3">
                      <div>
                        <div className="flex items-baseline gap-2 mb-1">
                          <label className="text-[10px] text-[#888] uppercase tracking-wider">Location must match</label>
                          <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                        </div>
                        <input
                          value={criteria.location_allowlist}
                          onChange={(e) => setCriteria({ ...criteria, location_allowlist: e.target.value })}
                          placeholder="e.g. remote|new york|london"
                          className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                        />
                        <p className="text-[9px] text-[#555] mt-1">Regex patterns. Leave blank to accept any location.</p>
                      </div>
                      <div>
                        <div className="flex items-baseline gap-2 mb-1">
                          <label className="text-[10px] text-[#888] uppercase tracking-wider">Location must NOT match</label>
                          <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                        </div>
                        <input
                          value={criteria.location_denylist}
                          onChange={(e) => setCriteria({ ...criteria, location_denylist: e.target.value })}
                          className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                        />
                        <p className="text-[9px] text-[#555] mt-1">Jobs in matching locations are discarded.</p>
                      </div>
                      <div>
                        <div className="flex items-baseline gap-2 mb-2">
                          <label className="text-[10px] text-[#888] uppercase tracking-wider">Exclusion keywords</label>
                          <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                        </div>
                        <TagChips
                          value={criteria.exclusion_keywords}
                          onChange={(v) => setCriteria({ ...criteria, exclusion_keywords: v })}
                          color="red"
                        />
                        <p className="text-[9px] text-[#555] mt-1">Jobs containing any of these exact phrases are discarded. Useful for filtering out visa-restricted or on-site-only postings.</p>
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2 items-center">
                    <button
                      onClick={() => saveCriteria.mutate(criteria)}
                      disabled={saveCriteria.isPending}
                      className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                    >
                      {saveCriteria.isPending ? "Saving..." : "Apply and continue"}
                    </button>
                    <button
                      onClick={() => setStep(4)}
                      className="text-xs text-[#555] hover:text-[#888]"
                    >
                      Skip customisation
                    </button>
                  </div>
                </div>

              ) : stage === null ? (
                /* Sub-step A: Stage picker */
                <>
                  <p className="text-xs text-[#666] mb-3">What stage are you at?</p>
                  <div className="space-y-2 mb-4">
                    {(
                      [
                        { value: "experienced", label: "💼 Experienced", desc: "Senior, staff, or lead-level roles" },
                        { value: "intern", label: "🎓 Intern / New Grad", desc: "Internships, co-ops, entry-level & new grad roles" },
                      ] as const
                    ).map((s) => (
                      <button
                        key={s.value}
                        onClick={() => setStage(s.value)}
                        className="w-full text-left border border-[#2a2a2a] rounded-lg px-4 py-3 bg-[#0a0a0a] hover:bg-[#111] transition-colors"
                      >
                        <div className="text-sm text-[#e5e5e5]">{s.label}</div>
                        <div className="text-[11px] text-[#666]">{s.desc}</div>
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => { setStage(null); setSelectedPreset(null); setStep(4); }}
                    className="text-xs text-[#555] hover:text-[#888]"
                  >
                    Skip
                  </button>
                </>

              ) : (
                /* Sub-step B: Preset picker */
                <>
                  <div className="flex items-center gap-2 mb-3">
                    <button
                      onClick={() => { setStage(null); setSelectedPreset(null); }}
                      className="text-xs text-[#4e9eff] hover:underline"
                    >
                      ← Back
                    </button>
                    <span className="text-xs text-[#555]">
                      {stage === "experienced" ? "Experienced" : "Intern / New Grad"}
                    </span>
                  </div>
                  <div className="space-y-2 mb-4">
                    {presetsLoading ? (
                      <p className="text-xs text-[#555] py-4 text-center">Loading presets...</p>
                    ) : presetsError ? (
                      <p className="text-xs text-[#f87171] py-4 text-center">Failed to load presets. Please try again.</p>
                    ) : presets.filter((p) => p.group === stage).length === 0 ? (
                      <p className="text-xs text-[#555] py-4 text-center">No presets available.</p>
                    ) : (
                      presets
                        .filter((p) => p.group === stage)
                        .map((p) => (
                          <button
                            key={p.name}
                            onClick={() => {
                              setSelectedPreset(p.name);
                              setCriteria(toCriteriaValues(p.criteria as Record<string, unknown>));
                            }}
                            className={`w-full text-left border rounded-lg px-4 py-3 transition-colors ${
                              selectedPreset === p.name
                                ? "border-[#4e9eff] bg-[#0e2040]"
                                : "border-[#2a2a2a] bg-[#0a0a0a] hover:bg-[#111]"
                            }`}
                          >
                            <div className="text-sm text-[#e5e5e5]">{p.label}</div>
                            <div className="text-[11px] text-[#666]">{p.description}</div>
                          </button>
                        ))
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setEditorOpen(true)}
                      disabled={!selectedPreset}
                      className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                    >
                      Customize and continue
                    </button>
                    <button
                      onClick={() => { setStage(null); setSelectedPreset(null); setStep(4); }}
                      className="text-xs text-[#555] hover:text-[#888]"
                    >
                      Skip
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {step === 4 && (
            <div>
              <h2 className="text-sm font-semibold mb-1">Step 4: Choose companies to track</h2>
              <p className="text-xs text-[#666] mb-3">
                All companies are pre-selected. Deselect any you don't want.
              </p>

              <div className="flex items-center gap-2 mb-2">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filter companies..."
                  className="flex-1 bg-[#0d0d0d] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]"
                />
                <span className="text-[10px] text-[#555]">{selectedCount} selected</span>
                <button onClick={selectAll} className="text-[10px] text-[#4e9eff] hover:underline">
                  All
                </button>
                <button onClick={deselectAll} className="text-[10px] text-[#555] hover:underline">
                  None
                </button>
              </div>

              <div className="h-64 overflow-y-auto border border-[#1e1e1e] rounded bg-[#0a0a0a] p-2 mb-3">
                {defaultCompanies.length === 0 ? (
                  <p className="text-[#555] text-xs text-center mt-8">Loading...</p>
                ) : filteredCompanies.length === 0 ? (
                  <p className="text-[#555] text-xs text-center mt-8">No matches</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {filteredCompanies.map((c) => {
                      const selected = !deselected.has(c.name);
                      return (
                        <button
                          key={c.name}
                          onClick={() => toggleCompany(c.name)}
                          className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                            selected
                              ? "border-[#4e9eff] bg-[#0e2040] text-[#4e9eff]"
                              : "border-[#2a2a2a] bg-transparent text-[#555]"
                          }`}
                        >
                          {c.name}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => importCompanies.mutate()}
                  disabled={selectedCount === 0 || importCompanies.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                >
                  {importCompanies.isPending
                    ? "Adding companies..."
                    : `Add ${selectedCount} companies and continue`}
                </button>
                <button onClick={() => setStep(5)} className="text-xs text-[#555] hover:text-[#888]">
                  Skip
                </button>
              </div>
            </div>
          )}

          {step === 5 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 5: Test run</h2>
              <p className="text-xs text-[#666] mb-4">
                Run a preview scrape to see results before enabling the scheduler. No Discord
                messages will be sent.
              </p>
              {!testRunId ? (
                <button
                  onClick={() => startTestRun.mutate()}
                  disabled={startTestRun.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040]"
                >
                  {startTestRun.isPending ? "Starting..." : "Start preview run"}
                </button>
              ) : (
                <div className="text-xs text-[#888] mb-4">
                  Preview run #{testRunId} started. Check the Runs screen for results.
                </div>
              )}
              <div className="mt-4">
                <button
                  onClick={finish}
                  className="text-xs border border-[#34d399] rounded px-4 py-2 text-[#34d399] bg-[#0d2018]"
                >
                  Finish setup and go to Dashboard
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Start the dev server and verify the new step renders**

```
cd frontend && npm run dev
```

Open `http://localhost:5173` in a browser. If the backend redirects to onboarding, you should see the 5-step progress bar with "API Keys" as the active step. Confirm:
- Three provider cards render (Groq, Cerebras, Gemini)
- "required" / "optional" labels appear correctly
- "Get your key" links point to the correct URLs
- "Next" button is disabled until both Groq and Cerebras show "valid"
- Changing a field after validation resets its indicator to idle

- [ ] **Step 4: Commit**

```
git add frontend/src/api/settings.ts frontend/src/pages/Onboarding.tsx
git commit -m "feat: add BYOK onboarding step with live key validation"
```
