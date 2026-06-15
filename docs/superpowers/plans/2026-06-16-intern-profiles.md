# Intern / New Grad Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 6 new presets (5 intern/new-grad + 1 VLSI experienced) and replace the hardcoded step-2 preset picker in onboarding with a dynamic two-step wizard (pick stage → pick preset).

**Architecture:** All preset data lives in `presets/*.json`. A new `group` field and `label` field are added to every preset JSON; `GET /presets` returns them automatically (the router already passes all JSON fields through). The frontend fetches presets via the existing `settingsApi.listPresets()`, groups by `group`, and renders a stage picker (sub-step A) followed by a filtered preset list (sub-step B).

**Tech Stack:** Python/FastAPI (backend, no router changes needed), React/TypeScript/TanStack Query (frontend), pytest/httpx (tests).

---

## File Map

| Action | Path | Purpose |
|---|---|---|
| Modify | `presets/backend-generalist.json` | Add `group` + `label` |
| Modify | `presets/frontend.json` | Add `group` + `label` |
| Modify | `presets/python-ml.json` | Add `group` + `label` |
| Create | `presets/vlsi.json` | VLSI/hardware experienced preset |
| Create | `presets/intern-generalist.json` | Any intern/new grad SWE role |
| Create | `presets/intern-backend.json` | Backend intern/new grad |
| Create | `presets/intern-frontend.json` | Frontend intern/new grad |
| Create | `presets/intern-ml.json` | ML/data science intern/new grad |
| Create | `presets/intern-fullstack.json` | Fullstack intern/new grad |
| Create | `tests/test_presets.py` | API tests for group/label fields |
| Modify | `frontend/src/pages/Onboarding.tsx` | Two-step wizard for step 2 |

---

## Task 1: Add `group` and `label` to existing preset JSONs

**Files:**
- Modify: `presets/backend-generalist.json`
- Modify: `presets/frontend.json`
- Modify: `presets/python-ml.json`

- [ ] **Step 1: Update `presets/backend-generalist.json`**

Replace the file contents with:

```json
{
  "group": "experienced",
  "label": "Backend generalist",
  "description": "Python, distributed systems, infrastructure",
  "criteria": {
    "title_allowlist": "backend|platform|infrastructure|systems|distributed|data engineer|api",
    "title_denylist": "intern|contract|marketing|sales|design|front.?end",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["senior", "staff", "principal", "lead"],
    "exclusion_keywords": ["clearance required", "on-site only"],
    "profile_description": "Experienced backend engineer skilled in Python, distributed systems, and API design. Seeking senior or staff-level roles at product companies."
  }
}
```

- [ ] **Step 2: Update `presets/frontend.json`**

```json
{
  "group": "experienced",
  "label": "Frontend engineer",
  "description": "React, TypeScript, product UI",
  "criteria": {
    "title_allowlist": "front.?end|ui engineer|react|web engineer|javascript|typescript",
    "title_denylist": "intern|contract|backend|mobile",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["senior", "staff", "principal", "lead"],
    "exclusion_keywords": ["clearance required"],
    "profile_description": "Senior frontend engineer specializing in React, TypeScript, and design systems at product-focused companies."
  }
}
```

- [ ] **Step 3: Update `presets/python-ml.json`**

```json
{
  "group": "experienced",
  "label": "Python ML engineer",
  "description": "ML platform, MLOps, data science",
  "criteria": {
    "title_allowlist": "machine learning|ml engineer|ml platform|mlops|data scientist|ai engineer|research engineer",
    "title_denylist": "intern|contract|front.?end|mobile",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["senior", "staff", "principal", "lead", "mid"],
    "exclusion_keywords": ["clearance required"],
    "profile_description": "ML engineer with Python expertise seeking roles in ML platform engineering, MLOps, or applied ML at product companies."
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add presets/backend-generalist.json presets/frontend.json presets/python-ml.json
git commit -m "feat: add group and label fields to existing presets"
```

---

## Task 2: Create VLSI preset

**Files:**
- Create: `presets/vlsi.json`

- [ ] **Step 1: Create `presets/vlsi.json`**

```json
{
  "group": "experienced",
  "label": "VLSI / Hardware engineer",
  "description": "RTL design, ASIC verification, FPGA",
  "criteria": {
    "title_allowlist": "vlsi|rtl|fpga|verilog|vhdl|system.?verilog|asic|chip design|physical design|verification engineer|dft|mixed.?signal",
    "title_denylist": "intern|contract|marketing|sales|frontend|backend|data science",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["senior", "staff", "principal", "lead"],
    "exclusion_keywords": ["clearance required", "on-site only"],
    "profile_description": "Experienced hardware engineer skilled in RTL design, ASIC verification, and FPGA development. Seeking senior roles at semiconductor companies and silicon teams."
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add presets/vlsi.json
git commit -m "feat: add VLSI/hardware engineer preset"
```

---

## Task 3: Create 5 intern/new-grad presets

**Files:**
- Create: `presets/intern-generalist.json`
- Create: `presets/intern-backend.json`
- Create: `presets/intern-frontend.json`
- Create: `presets/intern-ml.json`
- Create: `presets/intern-fullstack.json`

- [ ] **Step 1: Create `presets/intern-generalist.json`**

```json
{
  "group": "intern",
  "label": "Generalist",
  "description": "Any intern or new grad SWE role",
  "criteria": {
    "title_allowlist": "intern|co.?op|new.?grad|entry.?level|junior|associate",
    "title_denylist": "contract|marketing|sales|design",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["intern", "new grad", "entry level", "junior", "associate"],
    "exclusion_keywords": ["clearance required", "on-site only"],
    "profile_description": "New grad or intern seeking entry-level software engineering roles across any discipline."
  }
}
```

- [ ] **Step 2: Create `presets/intern-backend.json`**

```json
{
  "group": "intern",
  "label": "Backend",
  "description": "Systems, infra, APIs, platform",
  "criteria": {
    "title_allowlist": "intern|co.?op|new.?grad|entry.?level|junior|associate|backend|platform|infrastructure|systems|api",
    "title_denylist": "contract|marketing|sales|design",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["intern", "new grad", "entry level", "junior", "associate"],
    "exclusion_keywords": ["clearance required", "on-site only"],
    "profile_description": "New grad or intern interested in backend systems, platform engineering, and API development."
  }
}
```

- [ ] **Step 3: Create `presets/intern-frontend.json`**

```json
{
  "group": "intern",
  "label": "Frontend",
  "description": "React, TypeScript, web UI",
  "criteria": {
    "title_allowlist": "intern|co.?op|new.?grad|entry.?level|junior|associate|front.?end|ui engineer|react|web",
    "title_denylist": "contract|marketing|sales|design",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["intern", "new grad", "entry level", "junior", "associate"],
    "exclusion_keywords": ["clearance required", "on-site only"],
    "profile_description": "New grad or intern interested in frontend development with React, TypeScript, and modern web UI."
  }
}
```

- [ ] **Step 4: Create `presets/intern-ml.json`**

```json
{
  "group": "intern",
  "label": "ML / Data Science",
  "description": "ML platform, MLOps, data science",
  "criteria": {
    "title_allowlist": "intern|co.?op|new.?grad|entry.?level|junior|associate|ml|machine learning|data science|ai|mlops",
    "title_denylist": "contract|marketing|sales|design",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["intern", "new grad", "entry level", "junior", "associate"],
    "exclusion_keywords": ["clearance required", "on-site only"],
    "profile_description": "New grad or intern interested in machine learning, data science, and AI engineering roles."
  }
}
```

- [ ] **Step 5: Create `presets/intern-fullstack.json`**

```json
{
  "group": "intern",
  "label": "Fullstack",
  "description": "Frontend + backend, software engineer roles",
  "criteria": {
    "title_allowlist": "intern|co.?op|new.?grad|entry.?level|junior|associate|fullstack|full.?stack|software engineer",
    "title_denylist": "contract|marketing|sales|design",
    "location_allowlist": "",
    "location_denylist": "",
    "seniority_allowlist": ["intern", "new grad", "entry level", "junior", "associate"],
    "exclusion_keywords": ["clearance required", "on-site only"],
    "profile_description": "New grad or intern seeking fullstack or general software engineering roles."
  }
}
```

- [ ] **Step 6: Commit**

```bash
git add presets/intern-generalist.json presets/intern-backend.json presets/intern-frontend.json presets/intern-ml.json presets/intern-fullstack.json
git commit -m "feat: add intern and new grad preset profiles"
```

---

## Task 4: Test `GET /presets` returns group and label fields

**Files:**
- Create: `tests/test_presets.py`

The `GET /presets` router at `backend/routers/presets.py` reads all JSON keys and returns them. No router changes are needed — this test verifies the preset files are correct and the API passes the new fields through.

- [ ] **Step 1: Create `tests/test_presets.py`**

```python
async def test_list_presets_returns_group_and_label(client):
    response = await client.get("/api/presets")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    for preset in data:
        assert "group" in preset, f"preset {preset['name']} missing 'group'"
        assert preset["group"] in ("experienced", "intern"), f"preset {preset['name']} has invalid group: {preset['group']}"
        assert "label" in preset, f"preset {preset['name']} missing 'label'"
        assert isinstance(preset["label"], str) and len(preset["label"]) > 0


async def test_list_presets_has_both_groups(client):
    response = await client.get("/api/presets")
    data = response.json()
    groups = {p["group"] for p in data}
    assert "experienced" in groups
    assert "intern" in groups


async def test_list_presets_intern_count(client):
    response = await client.get("/api/presets")
    data = response.json()
    intern_presets = [p for p in data if p["group"] == "intern"]
    assert len(intern_presets) == 5


async def test_list_presets_experienced_count(client):
    response = await client.get("/api/presets")
    data = response.json()
    experienced_presets = [p for p in data if p["group"] == "experienced"]
    assert len(experienced_presets) == 4  # backend-generalist, frontend, python-ml, vlsi
```

- [ ] **Step 2: Run the tests**

```bash
pytest tests/test_presets.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_presets.py
git commit -m "test: verify GET /presets returns group and label fields"
```

---

## Task 5: Update Onboarding step 2 to two-step wizard

**Files:**
- Modify: `frontend/src/pages/Onboarding.tsx`

The existing `settingsApi.listPresets()` at `frontend/src/api/settings.ts:9` already calls `GET /presets` — no API client changes needed.

- [ ] **Step 1: Add `Preset` interface and `stage` state**

At the top of `Onboarding.tsx`, add the interface before the component function:

```ts
interface Preset {
  name: string;
  label: string;
  description: string;
  group: "experienced" | "intern";
  criteria: Record<string, unknown>;
}
```

Inside the `Onboarding` component, add `stage` state after the existing state declarations (after line 16, `const [deselected, ...]`):

```ts
const [stage, setStage] = useState<"experienced" | "intern" | null>(null);
```

- [ ] **Step 2: Add `useQuery` for presets**

Add this query after the existing `defaultCompanies` query (after line 23):

```ts
const { data: presets = [] } = useQuery<Preset[]>({
  queryKey: ["presets"],
  queryFn: settingsApi.listPresets,
  enabled: step === 2,
});
```

- [ ] **Step 3: Replace step 2 JSX**

Replace the entire `{step === 2 && ( ... )}` block (lines 125–161 in current file) with:

```tsx
{step === 2 && (
  <div>
    <h2 className="text-sm font-semibold mb-3">Step 2: Choose a job criteria preset</h2>

    {stage === null ? (
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
        <button onClick={() => setStep(3)} className="text-xs text-[#555] hover:text-[#888]">
          Skip
        </button>
      </>
    ) : (
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
          {presets
            .filter((p) => p.group === stage)
            .map((p) => (
              <button
                key={p.name}
                onClick={() => setSelectedPreset(p.name)}
                className={`w-full text-left border rounded-lg px-4 py-3 transition-colors ${
                  selectedPreset === p.name
                    ? "border-[#4e9eff] bg-[#0e2040]"
                    : "border-[#2a2a2a] bg-[#0a0a0a] hover:bg-[#111]"
                }`}
              >
                <div className="text-sm text-[#e5e5e5]">{p.label}</div>
                <div className="text-[11px] text-[#666]">{p.description}</div>
              </button>
            ))}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => applyPreset.mutate()}
            disabled={!selectedPreset || applyPreset.isPending}
            className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
          >
            {applyPreset.isPending ? "Applying..." : "Apply and continue"}
          </button>
          <button onClick={() => setStep(3)} className="text-xs text-[#555] hover:text-[#888]">
            Skip
          </button>
        </div>
      </>
    )}
  </div>
)}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Onboarding.tsx
git commit -m "feat: replace hardcoded preset list with two-step stage/preset wizard"
```
