# Intern / New Grad Profiles — Design Spec

## Overview

Add 5 intern/new-grad preset profiles alongside the existing 3 experienced presets. Update the onboarding step 2 UI to a two-step wizard: pick stage first (Experienced vs. Intern/New Grad), then pick specialty.

## Preset JSON Changes

### Existing presets — add `group` field

Add `"group": "experienced"` to all three existing preset files:
- `presets/backend-generalist.json`
- `presets/frontend.json`
- `presets/python-ml.json`

No other changes to existing presets. The `GET /presets` router already returns all JSON fields, so `group` appears in the response automatically — no backend router changes needed.

### New intern preset files

Five new files in `presets/`:

| File | Label | Specialty keywords added to title_allowlist |
|---|---|---|
| `intern-generalist.json` | Generalist | none — matches any intern/new grad SWE role |
| `intern-backend.json` | Backend | `backend\|platform\|infrastructure\|systems\|api` |
| `intern-frontend.json` | Frontend | `frontend\|ui engineer\|react\|web` |
| `intern-ml.json` | ML / Data Science | `ml\|machine learning\|data science\|ai\|mlops` |
| `intern-fullstack.json` | Fullstack | `fullstack\|full.?stack\|software engineer` |

All intern presets share:
- `"group": "intern"`
- `title_allowlist` base: `intern|co.?op|new.?grad|entry.?level|junior|associate` (plus specialty keywords per table above)
- `title_denylist`: `"contract|marketing|sales|design"` — "intern" removed from denylist (present in current experienced presets)
- `seniority_allowlist`: `["intern", "new grad", "entry level", "junior", "associate"]`
- `exclusion_keywords`: `["clearance required", "on-site only"]`
- `profile_description`: role-appropriate description string

## Frontend — Onboarding Step 2

### State additions

```ts
const [stage, setStage] = useState<"experienced" | "intern" | null>(null);
```

### Data fetching

Replace the hardcoded preset array (Onboarding.tsx lines 129–134) with a `useQuery` call:

```ts
const { data: presets = [] } = useQuery({
  queryKey: ["presets"],
  queryFn: presetsApi.list,
  enabled: step === 2,
});
```

Add `presetsApi.list` to the existing `frontend/src/api/settings.ts` (or a new `presets.ts` file — follow whichever pattern fits).

### UI flow

Step 2 renders two sub-steps based on `stage`:

**Sub-step A (`stage === null`) — Stage picker**
- Heading: "What stage are you at?"
- Two selectable cards: "💼 Experienced" / "🎓 Intern / New Grad"
- Clicking a card sets `stage` and immediately advances to sub-step B
- "Apply and continue" button disabled until a preset is selected (lives in sub-step B)
- "Skip" link advances to step 3

**Sub-step B (`stage !== null`) — Preset picker**
- "← Back" arrow resets `stage` to null (returns to sub-step A) and clears `selectedPreset`
- Breadcrumb label shows current stage ("Experienced" or "Intern / New Grad")
- Preset list filtered to `presets.filter(p => p.group === stage)`
- Same selection + button behavior as today
- "Apply and continue" calls `applyPreset.mutate()` then `setStep(3)`

### No changes to steps 1, 3, or 4.

## File Checklist

- [ ] `presets/backend-generalist.json` — add `group`
- [ ] `presets/frontend.json` — add `group`
- [ ] `presets/python-ml.json` — add `group`
- [ ] `presets/intern-generalist.json` — new
- [ ] `presets/intern-backend.json` — new
- [ ] `presets/intern-frontend.json` — new
- [ ] `presets/intern-ml.json` — new
- [ ] `presets/intern-fullstack.json` — new
- [ ] `frontend/src/api/presets.ts` (or settings.ts) — add `presetsApi.list`
- [ ] `frontend/src/pages/Onboarding.tsx` — step 2 rewrite with stage state + useQuery
