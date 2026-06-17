# Criteria Editor in Onboarding — Design Spec

## Overview

Add a criteria customization sub-step to onboarding step 2, so users can tune their job matching filters immediately after selecting a preset. Also add the two currently-missing criteria fields (`seniority_allowlist`, `exclusion_keywords`) to the Settings criteria tab so users can edit them later.

---

## Motivation

Match quality depends on two layers:

- **Heuristic filters** (`title_allowlist`, `title_denylist`, `seniority_allowlist`, `location_*`, `exclusion_keywords`) — fast pre-AI rules. A job that fails any of these is dropped immediately, before the AI ever scores it. Overly strict patterns silently discard good matches.
- **AI scoring** (`profile_description`) — contextual, forgiving. The richer and more specific the profile, the better the relevance scores.

Preset defaults are a reasonable starting point but will miss or include the wrong jobs for most users. The editor surfaces these fields during onboarding with enough explanation for users to tune them confidently.

---

## Onboarding Flow Change

### Before

```
Sub-step A: Stage picker
Sub-step B: Preset picker → "Apply and continue" → Step 3
```

### After

```
Sub-step A: Stage picker
Sub-step B: Preset picker → "Customize and continue"
Sub-step C: Criteria editor → "Apply and continue" or "Skip customisation" → Step 3
```

Clicking a preset in sub-step B immediately copies that preset's `criteria` object into local `criteria` state. "Customize and continue" is disabled until a preset is selected. It advances to sub-step C once a preset is chosen.

The existing "Skip" link on sub-step B remains — it bypasses criteria entirely (no preset applied, no editor shown) and advances directly to step 3.

The `applyPreset` mutation is removed; both paths out of sub-step C call `settingsApi.update({ criteria })`.

---

## New State

Inside the `Onboarding` component, add:

```ts
interface CriteriaValues {
  title_allowlist: string;
  title_denylist: string;
  location_allowlist: string;
  location_denylist: string;
  seniority_allowlist: string[];
  exclusion_keywords: string[];
  profile_description: string;
}

const [criteria, setCriteria] = useState<CriteriaValues | null>(null);
const [showAdvanced, setShowAdvanced] = useState(false);
```

`criteria` is initialized (from the selected preset's criteria object) when the user clicks a preset in sub-step B. It is `null` until a preset is selected.

---

## Sub-step C: Criteria Editor

### Header

Back arrow resets to sub-step B and clears `criteria` (same pattern as existing back button). Breadcrumb shows preset label.

### Importance banner

```
⚡ How Joblin filters jobs — two layers

  Layer 1 — Heuristic filters (title, seniority, location, exclusions)
  Fast, non-AI rules. A job that fails is dropped immediately — the AI
  never sees it. If your patterns are too strict, you'll miss good
  matches with no warning.

  Layer 2 — AI scoring (profile description)
  Jobs that pass heuristics are scored by AI using your profile.
  Contextual and forgiving. A richer, more specific profile gives
  better, more relevant scores.
```

### High-impact fields (always visible)

Each field shows a `heuristic` (amber) or `AI scored` (green) badge.

**Title must match** — `heuristic` badge
- `<input>` bound to `criteria.title_allowlist`
- Helper: "Regex patterns, pipe-separated. Jobs whose title doesn't match any of these are discarded before AI scoring. Keep patterns broad — `'react'` alone would miss `'Frontend Engineer at Stripe'`."

**Title must NOT match** — `heuristic` badge
- `<input>` bound to `criteria.title_denylist`
- Helper: "Jobs whose title matches any of these are discarded. Be precise — `'design'` would also block `'design systems engineer'`."

**Seniority levels** — `heuristic` badge
- `<TagChips value={criteria.seniority_allowlist} onChange={...} suggestions={SENIORITY_SUGGESTIONS} color="blue" />`
- `SENIORITY_SUGGESTIONS = ["Senior", "Staff", "Principal", "Lead", "Mid", "Junior", "Intern", "New Grad", "Associate", "Entry Level"]`
- Helper: "Inferred from the job title. If seniority can't be inferred, the job passes through. Leave all unchecked to skip this filter entirely."

**Your profile** — `AI scored` badge + "← most impactful" label
- `<textarea>` bound to `criteria.profile_description`
- Helper: "The AI reads this to score job relevance — it understands context, not just keywords. Include your tech stack, years of experience, what kind of company you want, and what you want to avoid. The more specific, the better your scores."

### Advanced section (collapsed by default)

Toggle: "▶ Advanced — location filters & exclusion phrases"
Sub-label: "These are also heuristic filters. Use them if you have specific geographic or content requirements."

When expanded:

**Location must match** — `<input>` bound to `criteria.location_allowlist`
Helper: "Regex patterns. Leave blank to accept any location."

**Location must NOT match** — `<input>` bound to `criteria.location_denylist`
Helper: "Jobs in matching locations are discarded."

**Exclusion keywords** — `heuristic` badge
- `<TagChips value={criteria.exclusion_keywords} onChange={...} color="red" />`
- Helper: "Jobs containing any of these exact phrases are discarded. Useful for filtering out visa-restricted or on-site-only postings."

### Actions

- **"Apply and continue"** — calls `settingsApi.update({ criteria })`, on success `setStep(3)`. Disabled while mutation is pending.
- **"Skip customisation"** — calls `settingsApi.update({ criteria })` with the unmodified preset defaults (same call, no edits), then `setStep(3)`.

---

## TagChips Component

**File:** `frontend/src/components/TagChips.tsx`

```ts
interface TagChipsProps {
  value: string[];
  onChange: (v: string[]) => void;
  suggestions?: string[];  // pre-defined toggleable chips
  color?: "blue" | "red";
}
```

Behaviour:
- Active chips (in `value`): solid border, colored text, `✕` removes them
- Inactive suggestion chips (in `suggestions` but not in `value`): dashed border, muted — clicking adds to `value`
- `+ Add` chip: clicking shows a small inline text input; pressing Enter or comma commits the new value and dismisses the input
- Duplicate values are silently ignored

Used in: onboarding sub-step C and Settings criteria tab.

---

## Settings Criteria Tab Changes

**File:** `frontend/src/pages/Settings.tsx`

Add two fields to the existing Criteria tab, after the existing `title_denylist` input and before `profile_description`:

1. **Seniority levels** — `<TagChips>` with `color="blue"`, `suggestions={SENIORITY_SUGGESTIONS}` (same constant, shared or duplicated — no shared module needed)
2. **Exclusion keywords** — `<TagChips>` with `color="red"`, no `suggestions`

Settings already saves via `settingsApi.update(...)` on a Save button. `seniority_allowlist` and `exclusion_keywords` are included in that save call alongside the existing fields.

---

## File Checklist

- [ ] `frontend/src/components/TagChips.tsx` — new component
- [ ] `frontend/src/pages/Onboarding.tsx` — add `CriteriaValues` interface, `criteria` + `showAdvanced` state, sub-step C, remove `applyPreset` mutation
- [ ] `frontend/src/pages/Settings.tsx` — add `seniority_allowlist` and `exclusion_keywords` to criteria tab
