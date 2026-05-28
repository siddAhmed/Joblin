# Joblin Phase 6 -- Onboarding Wizard + SSE Live View + Preview Mode + Presets

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the four-step onboarding wizard (shown on empty DB), wire live SSE into RunDetail, add the preview badge to Matches, and confirm presets apply correctly end-to-end.

**Prerequisite:** Phase 5 complete and all tests passing.

---

## File Map

| File | Responsibility |
|---|---|
| `frontend/src/pages/Onboarding.tsx` | Four-step wizard component |
| `frontend/src/App.tsx` | Show Onboarding when companies list is empty |
| `frontend/src/pages/RunDetail.tsx` | Already written in Phase 5; verify SSE events render live |
| `backend/routers/system.py` | Add `GET /api/onboarding-status` endpoint |

---

## Task 29: Onboarding status endpoint

**Files:**
- Modify: `backend/routers/system.py`

- [ ] **Step 1: Add onboarding status endpoint to `backend/routers/system.py`**

```python
@router.get("/onboarding-status")
async def onboarding_status(session: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    from backend.models.company import Company

    company_count = (await session.execute(select(func.count()).select_from(Company))).scalar_one()
    return {"needs_onboarding": company_count == 0}
```

- [ ] **Step 2: Run tests**

```powershell
.venv/Scripts/pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```powershell
git add backend/routers/system.py
git commit -m "feat: onboarding status endpoint"
```

---

## Task 30: Onboarding wizard

**Files:**
- Create: `frontend/src/pages/Onboarding.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write `frontend/src/pages/Onboarding.tsx`**

```tsx
import { useState } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { settingsApi } from "@/api/settings";
import { companiesApi } from "@/api/companies";
import { runsApi } from "@/api/runs";

type Step = 1 | 2 | 3 | 4;

export function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState<Step>(1);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [companyCsv, setCompanyCsv] = useState("");
  const [testRunId, setTestRunId] = useState<number | null>(null);
  const qc = useQueryClient();

  const saveWebhook = useMutation({
    mutationFn: () => settingsApi.update({ discord_webhook_url: webhookUrl }),
    onSuccess: () => setStep(2),
  });

  const applyPreset = useMutation({
    mutationFn: () => settingsApi.applyPreset(selectedPreset!),
    onSuccess: () => setStep(3),
  });

  const importCompanies = useMutation({
    mutationFn: async () => {
      const lines = companyCsv.trim().split("\n").filter(Boolean);
      for (const line of lines) {
        const [name, url] = line.split(",").map((s) => s.trim());
        if (name && url) await companiesApi.add(name, url);
      }
    },
    onSuccess: () => setStep(4),
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

  const stepLabels = ["Discord", "Criteria", "Companies", "Test run"];

  return (
    <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[#e5e5e5]">
            Welcome to Job<span className="text-[#4e9eff]">lin</span>
          </h1>
          <p className="text-sm text-[#666] mt-1">Let's get you set up in 4 steps.</p>
        </div>

        <div className="flex gap-1 mb-6">
          {stepLabels.map((label, i) => (
            <div key={label} className="flex-1 text-center">
              <div className={`h-1 rounded mb-1 ${i + 1 <= step ? "bg-[#4e9eff]" : "bg-[#222]"}`} />
              <span className={`text-[10px] ${i + 1 === step ? "text-[#4e9eff]" : "text-[#555]"}`}>{label}</span>
            </div>
          ))}
        </div>

        <div className="border border-[#2a2a2a] rounded-xl p-6 bg-[#111]">
          {step === 1 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 1: Discord webhook</h2>
              <p className="text-xs text-[#666] mb-3">
                Create a webhook in your Discord server settings and paste the URL below.
                Joblin will notify you when strong matches are found.
              </p>
              <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://discord.com/api/webhooks/..."
                className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] mb-3" />
              <div className="flex gap-2">
                <button onClick={() => saveWebhook.mutate()} disabled={saveWebhook.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040]">
                  {saveWebhook.isPending ? "Saving..." : "Save and continue"}
                </button>
                <button onClick={() => setStep(2)} className="text-xs text-[#555] hover:text-[#888]">
                  Skip for now
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 2: Choose a job criteria preset</h2>
              <div className="space-y-2 mb-4">
                {[
                  { name: "backend-generalist", label: "Backend generalist", desc: "Python, distributed systems, infrastructure" },
                  { name: "python-ml", label: "Python ML engineer", desc: "ML platform, MLOps, data science" },
                  { name: "frontend", label: "Frontend engineer", desc: "React, TypeScript, product UI" },
                ].map((p) => (
                  <button key={p.name} onClick={() => setSelectedPreset(p.name)}
                    className={`w-full text-left border rounded-lg px-4 py-3 transition-colors ${
                      selectedPreset === p.name ? "border-[#4e9eff] bg-[#0e2040]" : "border-[#2a2a2a] bg-[#0a0a0a] hover:bg-[#111]"
                    }`}>
                    <div className="text-sm text-[#e5e5e5]">{p.label}</div>
                    <div className="text-[11px] text-[#666]">{p.desc}</div>
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <button onClick={() => applyPreset.mutate()} disabled={!selectedPreset || applyPreset.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40">
                  {applyPreset.isPending ? "Applying..." : "Apply and continue"}
                </button>
                <button onClick={() => setStep(3)} className="text-xs text-[#555] hover:text-[#888]">
                  Skip
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 3: Add companies</h2>
              <p className="text-xs text-[#666] mb-3">
                Paste one company per line as: <code className="text-[#4e9eff]">Name, Careers URL</code>
              </p>
              <textarea value={companyCsv} onChange={(e) => setCompanyCsv(e.target.value)}
                rows={6} placeholder={"Stripe, https://stripe.com/jobs\nLinear, https://linear.app/careers"}
                className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] font-mono mb-3" />
              <div className="flex gap-2">
                <button onClick={() => importCompanies.mutate()} disabled={!companyCsv.trim() || importCompanies.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40">
                  {importCompanies.isPending ? "Importing..." : "Import and continue"}
                </button>
              </div>
            </div>
          )}

          {step === 4 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 4: Test run</h2>
              <p className="text-xs text-[#666] mb-4">
                Run a preview scrape to see results before enabling the scheduler. No Discord messages will be sent.
              </p>
              {!testRunId ? (
                <button onClick={() => startTestRun.mutate()} disabled={startTestRun.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040]">
                  {startTestRun.isPending ? "Starting..." : "Start preview run"}
                </button>
              ) : (
                <div className="text-xs text-[#888] mb-4">
                  Preview run #{testRunId} started. Check the Runs screen for results.
                </div>
              )}
              <div className="mt-4">
                <button onClick={finish}
                  className="text-xs border border-[#34d399] rounded px-4 py-2 text-[#34d399] bg-[#0d2018]">
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

- [ ] **Step 2: Update `frontend/src/App.tsx` to show wizard when no companies exist**

```tsx
import { useQuery } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Matches } from "./pages/Matches";
import { Jobs } from "./pages/Jobs";
import { Companies } from "./pages/Companies";
import { Runs } from "./pages/Runs";
import { RunDetail } from "./pages/RunDetail";
import { Settings } from "./pages/Settings";
import { Onboarding } from "./pages/Onboarding";
import { api } from "./api/client";

function AppInner() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: () => api.get("/onboarding-status").then((r) => r.data),
  });

  if (isLoading) return null;
  if (data?.needs_onboarding) return <Onboarding onComplete={() => refetch()} />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/matches" element={<Matches />} />
        <Route path="/jobs" element={<Jobs />} />
        <Route path="/companies" element={<Companies />} />
        <Route path="/runs" element={<Runs />} />
        <Route path="/runs/:id" element={<RunDetail />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppInner />
    </BrowserRouter>
  );
}
```

- [ ] **Step 3: Verify onboarding wizard appears on fresh DB**

Delete `joblin.db`, restart the backend (migrations recreate it), open http://localhost:5173.

Expected: wizard shows, not the dashboard.

- [ ] **Step 4: Complete the wizard and confirm redirect to dashboard**

Fill in each step, click through. Expected: after step 4, dashboard appears.

- [ ] **Step 5: Commit**

```powershell
cd C:\dev\joblin
git add frontend/src/pages/Onboarding.tsx frontend/src/App.tsx backend/routers/system.py
git commit -m "feat: four-step onboarding wizard, shown on empty DB"
```

---

## Task 31: Preview badge + SSE live view verification

**Files:**
- Verify: `frontend/src/pages/Matches.tsx` (preview badge already coded in Phase 5)
- Verify: `frontend/src/pages/RunDetail.tsx` (SSE already coded in Phase 5)

- [ ] **Step 1: Start a preview run via the UI**

Click "Preview run" from the topbar. Expected: run created, navigate to `/runs`.

- [ ] **Step 2: Click the run row to navigate to RunDetail**

Expected: SSE events appear live as they are emitted by the backend (`run_started`, `company_scraping`, etc.).

- [ ] **Step 3: Verify preview badge in Matches screen**

Navigate to `/matches`. Any matches from the preview run should show a purple "preview" badge. Expected: badge visible.

- [ ] **Step 4: Verify "not interested" button writes to feedback_examples**

Expand a match row in `/matches`, click "Not interested". Expected: request to `POST /api/jobs/{id}/dismiss` returns 200, match shows `not_interested_at` set.

- [ ] **Step 5: Commit if any fixes were needed**

```powershell
git add frontend/src/pages/
git commit -m "fix: verify preview badge and SSE live view render correctly"
```

---

**Phase 6 complete.** Onboarding wizard, SSE live view, preview badges, and presets all verified end-to-end. Proceed to Phase 7.
