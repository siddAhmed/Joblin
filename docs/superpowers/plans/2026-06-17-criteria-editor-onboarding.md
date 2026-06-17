# Criteria Editor in Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an inline criteria customization sub-step to onboarding (after preset selection) and add the two missing criteria fields — `seniority_allowlist` and `exclusion_keywords` — to the Settings criteria tab.

**Architecture:** A new `TagChips` component handles array-of-strings editing (seniority levels, exclusion keywords) and is shared between onboarding and Settings. Onboarding gains a third sub-step within step 2 (stage picker → preset picker → criteria editor); the `applyPreset` mutation is replaced by a `settingsApi.update({ criteria })` call. Settings adds two new fields to its existing criteria tab using the same `TagChips` component.

**Tech Stack:** React 18, TypeScript, TanStack Query v5, Tailwind CSS.

## Global Constraints

- No new backend changes — `PATCH /settings` already accepts the full criteria object.
- No shared constants module — `SENIORITY_SUGGESTIONS` is duplicated in Onboarding.tsx and Settings.tsx.
- Tailwind only — no inline `style` props, no new CSS files.
- TypeScript must compile with no errors after each task: `cd frontend && npx tsc --noEmit`.
- No co-author trailers in git commits.

---

## File Map

| Action | Path | Purpose |
|---|---|---|
| Create | `frontend/src/components/TagChips.tsx` | Reusable chip editor for string arrays |
| Modify | `frontend/src/pages/Onboarding.tsx` | Add CriteriaValues state, editorOpen state, sub-step C, replace applyPreset mutation |
| Modify | `frontend/src/pages/Settings.tsx` | Add seniority_allowlist and exclusion_keywords to criteria tab |

---

## Task 1: TagChips component

**Files:**
- Create: `frontend/src/components/TagChips.tsx`

**Interfaces:**
- Produces: `TagChips({ value, onChange, suggestions?, color? })` — used by Tasks 2 and 3.

- [ ] **Step 1: Create `frontend/src/components/TagChips.tsx`**

```tsx
import { useState } from "react";

export interface TagChipsProps {
  value: string[];
  onChange: (v: string[]) => void;
  suggestions?: string[];
  color?: "blue" | "red";
}

const ACTIVE: Record<"blue" | "red", string> = {
  blue: "border-[#4e9eff] bg-[#0e2040] text-[#4e9eff]",
  red: "border-[#4a1a1a] bg-[#1a0a0a] text-[#f87171]",
};
const INACTIVE = "border-[#2a2a2a] border-dashed text-[#555] bg-transparent";

export function TagChips({ value, onChange, suggestions = [], color = "blue" }: TagChipsProps) {
  const [adding, setAdding] = useState(false);
  const [input, setInput] = useState("");

  const remove = (tag: string) => onChange(value.filter((v) => v !== tag));

  const add = (tag: string) => {
    const t = tag.trim();
    if (t && !value.includes(t)) onChange([...value, t]);
  };

  const toggle = (tag: string) =>
    value.includes(tag) ? remove(tag) : add(tag);

  const commit = () => {
    input.split(",").map((s) => s.trim()).filter(Boolean).forEach(add);
    setInput("");
    setAdding(false);
  };

  const inactive = suggestions.filter((s) => !value.includes(s));

  return (
    <div className="flex flex-wrap gap-1.5">
      {value.map((tag) => (
        <button
          key={tag}
          type="button"
          onClick={() => remove(tag)}
          className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${ACTIVE[color]}`}
        >
          {tag} ✕
        </button>
      ))}
      {inactive.map((tag) => (
        <button
          key={tag}
          type="button"
          onClick={() => toggle(tag)}
          className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${INACTIVE}`}
        >
          {tag}
        </button>
      ))}
      {adding ? (
        <input
          autoFocus
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") { e.preventDefault(); commit(); }
            if (e.key === "Escape") { setInput(""); setAdding(false); }
          }}
          onBlur={commit}
          placeholder="type and press Enter"
          className="text-[11px] px-2.5 py-1 rounded-full border border-[#2a2a2a] bg-transparent text-[#e5e5e5] outline-none w-36"
        />
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${INACTIVE}`}
        >
          + Add
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TagChips.tsx
git commit -m "feat: add TagChips component for array-of-strings editing"
```

---

## Task 2: Onboarding sub-step C — criteria editor

**Files:**
- Modify: `frontend/src/pages/Onboarding.tsx`

**Interfaces:**
- Consumes: `TagChips` from `@/components/TagChips` (Task 1)
- Consumes: `settingsApi.update` from `@/api/settings` (already exists)

The current step 2 in `Onboarding.tsx` has sub-step A (stage picker, `stage === null`) and sub-step B (preset picker, `stage !== null`). This task adds sub-step C (criteria editor, `editorOpen === true`), adds `criteria` / `showAdvanced` / `editorOpen` state, replaces the `applyPreset` mutation with `saveCriteria`, and renames the sub-step B action button to "Customize and continue".

- [ ] **Step 1: Add import and module-level constants/helpers**

At the top of `frontend/src/pages/Onboarding.tsx`, add the `TagChips` import after the existing imports:

```ts
import { TagChips } from "@/components/TagChips";
```

After the existing `interface Preset { ... }` block (line 16), add:

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
    seniority_allowlist: (raw.seniority_allowlist as string[]) ?? [],
    exclusion_keywords: (raw.exclusion_keywords as string[]) ?? [],
    profile_description: (raw.profile_description as string) ?? "",
  };
}
```

- [ ] **Step 2: Add new state variables**

Inside the `Onboarding` component, after the existing `const [stage, setStage] = useState(...)` line (line 25), add:

```ts
const [criteria, setCriteria] = useState<CriteriaValues | null>(null);
const [showAdvanced, setShowAdvanced] = useState(false);
const [editorOpen, setEditorOpen] = useState(false);
```

- [ ] **Step 3: Replace applyPreset mutation with saveCriteria**

Remove the existing `applyPreset` mutation (lines 64–67):
```ts
// DELETE this block:
const applyPreset = useMutation({
  mutationFn: () => settingsApi.applyPreset(selectedPreset!),
  onSuccess: () => setStep(3),
});
```

Add in its place:
```ts
const saveCriteria = useMutation({
  mutationFn: (c: CriteriaValues) => settingsApi.update({ criteria: c }),
  onSuccess: () => setStep(3),
});
```

- [ ] **Step 4: Update sub-step B — set criteria on preset click and rename button**

In the sub-step B preset `.map()` (around line 192), change the preset button's `onClick` from:
```tsx
onClick={() => setSelectedPreset(p.name)}
```
to:
```tsx
onClick={() => {
  setSelectedPreset(p.name);
  setCriteria(toCriteriaValues(p.criteria as Record<string, unknown>));
}}
```

In the sub-step B actions (around line 207), replace the entire `<div className="flex gap-2">` block with:
```tsx
<div className="flex gap-2">
  <button
    onClick={() => setEditorOpen(true)}
    disabled={!selectedPreset}
    className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
  >
    Customize and continue
  </button>
  <button
    onClick={() => { setStage(null); setSelectedPreset(null); setStep(3); }}
    className="text-xs text-[#555] hover:text-[#888]"
  >
    Skip
  </button>
</div>
```

- [ ] **Step 5: Add sub-step C — wrap step 2 to handle editorOpen**

The `{step === 2 && (...)}` block currently uses a `{stage === null ? (...) : (...)}` ternary. Wrap the outermost ternary to also check `editorOpen`:

Replace the inner content of `{step === 2 && (...)}` with this structure:

```tsx
{step === 2 && (
  <div>
    <h2 className="text-sm font-semibold mb-3">Step 2: Choose a job criteria preset</h2>

    {editorOpen && criteria ? (
      /* ── Sub-step C: Criteria editor ── */
      <div>
        <div className="flex items-center gap-2 mb-3">
          <button
            onClick={() => setEditorOpen(false)}
            className="text-xs text-[#4e9eff] hover:underline"
          >
            ← Back
          </button>
          <span className="text-xs text-[#555]">
            {presets.find((p) => p.name === selectedPreset)?.label}
          </span>
        </div>

        {/* Importance banner */}
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

        {/* Title must match */}
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

        {/* Title must NOT match */}
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

        {/* Seniority levels */}
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

        {/* Your profile */}
        <div className="mb-3">
          <div className="flex items-baseline gap-2 mb-1">
            <label className="text-[10px] text-[#888] uppercase tracking-wider">Your profile</label>
            <span className="text-[9px] bg-[#0a2010] border border-[#1a4a20] rounded px-1 py-px text-[#34d399]">AI scored</span>
            <span className="text-[9px] text-[#34d399]">← most impactful</span>
          </div>
          <textarea
            value={criteria.profile_description}
            onChange={(e) => setCriteria({ ...criteria, profile_description: e.target.value })}
            rows={3}
            className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
          />
          <p className="text-[9px] text-[#555] mt-1 leading-relaxed">The AI reads this to score job relevance — it understands context, not just keywords. Include your tech stack, years of experience, what kind of company you want, and what you want to avoid. The more specific, the better your scores.</p>
        </div>

        {/* Advanced toggle */}
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

        {/* Actions */}
        <div className="flex gap-2 items-center">
          <button
            onClick={() => saveCriteria.mutate(criteria)}
            disabled={saveCriteria.isPending}
            className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
          >
            {saveCriteria.isPending ? "Saving..." : "Apply and continue"}
          </button>
          <button
            onClick={() => saveCriteria.mutate(criteria)}
            disabled={saveCriteria.isPending}
            className="text-xs text-[#555] hover:text-[#888]"
          >
            Skip customisation
          </button>
        </div>
      </div>

    ) : stage === null ? (
      /* ── Sub-step A: Stage picker (unchanged) ── */
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
          onClick={() => { setStage(null); setSelectedPreset(null); setStep(3); }}
          className="text-xs text-[#555] hover:text-[#888]"
        >
          Skip
        </button>
      </>

    ) : (
      /* ── Sub-step B: Preset picker ── */
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
            onClick={() => { setStage(null); setSelectedPreset(null); setStep(3); }}
            className="text-xs text-[#555] hover:text-[#888]"
          >
            Skip
          </button>
        </div>
      </>
    )}
  </div>
)}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Onboarding.tsx
git commit -m "feat: add criteria editor sub-step to onboarding"
```

---

## Task 3: Settings criteria tab — add seniority and exclusion fields

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

**Interfaces:**
- Consumes: `TagChips` from `@/components/TagChips` (Task 1)
- Consumes: `criteria` — `(s.criteria as Record<string, unknown>) || {}` — already defined at line 245

The existing criteria tab loops over `["title_allowlist", "title_denylist", "location_allowlist", "location_denylist"]` in a single `.map()`. Split this into two separate maps (title fields + location fields) and insert `seniority_allowlist` and `exclusion_keywords` between them.

- [ ] **Step 1: Add TagChips import and SENIORITY_SUGGESTIONS constant to Settings.tsx**

At the top of `frontend/src/pages/Settings.tsx`, add the import after the existing imports:

```ts
import { TagChips } from "@/components/TagChips";
```

After the `type Tab = ...` line (line 15), add:

```ts
const SENIORITY_SUGGESTIONS = [
  "Senior", "Staff", "Principal", "Lead", "Mid",
  "Junior", "Intern", "New Grad", "Associate", "Entry Level",
];
```

- [ ] **Step 2: Replace the criteria tab field loop**

Find and replace the entire `{tab === "criteria" && (...)}` block (lines 287–315). Replace:

```tsx
{tab === "criteria" && (
  <div className="space-y-3 max-w-lg">
    {["title_allowlist", "title_denylist", "location_allowlist", "location_denylist"].map((field) => (
      <div key={field}>
        <label className="block text-xs text-[#888] mb-1">{field.replace(/_/g, " ")}</label>
        <input defaultValue={(criteria[field] as string) || ""}
          onBlur={(e) => update.mutate({ criteria: { ...criteria, [field]: e.target.value } })}
          className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
      </div>
    ))}
    <label className="block text-xs text-[#888]">Profile description</label>
    <textarea defaultValue={(criteria.profile_description as string) || ""}
      onBlur={(e) => update.mutate({ criteria: { ...criteria, profile_description: e.target.value } })}
      rows={3} className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
```

with:

```tsx
{tab === "criteria" && (
  <div className="space-y-3 max-w-lg">
    {["title_allowlist", "title_denylist"].map((field) => (
      <div key={field}>
        <label className="block text-xs text-[#888] mb-1">{field.replace(/_/g, " ")}</label>
        <input defaultValue={(criteria[field] as string) || ""}
          onBlur={(e) => update.mutate({ criteria: { ...criteria, [field]: e.target.value } })}
          className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
      </div>
    ))}
    <div>
      <label className="block text-xs text-[#888] mb-2">seniority levels</label>
      <TagChips
        value={(criteria.seniority_allowlist as string[]) || []}
        onChange={(v) => update.mutate({ criteria: { ...criteria, seniority_allowlist: v } })}
        suggestions={SENIORITY_SUGGESTIONS}
        color="blue"
      />
    </div>
    <div>
      <label className="block text-xs text-[#888] mb-2">exclusion keywords</label>
      <TagChips
        value={(criteria.exclusion_keywords as string[]) || []}
        onChange={(v) => update.mutate({ criteria: { ...criteria, exclusion_keywords: v } })}
        color="red"
      />
    </div>
    {["location_allowlist", "location_denylist"].map((field) => (
      <div key={field}>
        <label className="block text-xs text-[#888] mb-1">{field.replace(/_/g, " ")}</label>
        <input defaultValue={(criteria[field] as string) || ""}
          onBlur={(e) => update.mutate({ criteria: { ...criteria, [field]: e.target.value } })}
          className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
      </div>
    ))}
    <label className="block text-xs text-[#888]">Profile description</label>
    <textarea defaultValue={(criteria.profile_description as string) || ""}
      onBlur={(e) => update.mutate({ criteria: { ...criteria, profile_description: e.target.value } })}
      rows={3} className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
```

(The rest of the block — test harness and closing tags — is unchanged.)

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "feat: add seniority and exclusion keyword editors to settings criteria tab"
```
