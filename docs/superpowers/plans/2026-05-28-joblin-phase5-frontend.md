# Joblin Phase 5 -- Full UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete React SPA: all six screens (Dashboard, Matches, Jobs, Companies, Runs, Settings), the collapsible sidebar shell, and TanStack Query wiring to the backend API.

**Prerequisite:** Phase 4 complete and all tests passing.

**Tech Stack:** Vite 6, React 18, TypeScript, Tailwind CSS 3, shadcn/ui, TanStack Query v5, React Router v6, axios.

---

## File Map

| File | Responsibility |
|---|---|
| `frontend/package.json` | Dependencies |
| `frontend/vite.config.ts` | Vite config with API proxy |
| `frontend/tailwind.config.ts` | Tailwind config |
| `frontend/src/main.tsx` | React root + QueryClientProvider |
| `frontend/src/App.tsx` | Router setup |
| `frontend/src/api/client.ts` | axios instance |
| `frontend/src/api/companies.ts` | Companies API functions |
| `frontend/src/api/jobs.ts` | Jobs API functions |
| `frontend/src/api/matches.ts` | Matches API functions |
| `frontend/src/api/runs.ts` | Runs API functions |
| `frontend/src/api/settings.ts` | Settings API functions |
| `frontend/src/api/stats.ts` | Stats API function |
| `frontend/src/components/Layout.tsx` | Shell with sidebar + topbar |
| `frontend/src/components/Sidebar.tsx` | Nav, collapse state (localStorage) |
| `frontend/src/components/Topbar.tsx` | Screen title + Run now / Preview buttons |
| `frontend/src/hooks/useSseRun.ts` | EventSource hook for SSE stream |
| `frontend/src/pages/Dashboard.tsx` | Dashboard screen |
| `frontend/src/pages/Matches.tsx` | Matches screen |
| `frontend/src/pages/Jobs.tsx` | All Jobs screen |
| `frontend/src/pages/Companies.tsx` | Companies screen + Add modal |
| `frontend/src/pages/Runs.tsx` | Runs history screen |
| `frontend/src/pages/RunDetail.tsx` | Live SSE progress view |
| `frontend/src/pages/Settings.tsx` | Settings (5 tabs) |
| `frontend/src/lib/utils.ts` | cn() helper, formatters |

---

## Task 24: Vite + React scaffold + Tailwind + shadcn/ui

- [ ] **Step 1: Scaffold Vite project**

```powershell
cd C:\dev\joblin
npm create vite@latest frontend -- --template react-ts
cd frontend
```

- [ ] **Step 2: Install dependencies**

```powershell
npm install @tanstack/react-query axios react-router-dom
npm install -D tailwindcss postcss autoprefixer @tailwindcss/forms
npx tailwindcss init -p
```

- [ ] **Step 3: Write `frontend/tailwind.config.ts`**

```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 4: Update `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color-scheme: dark;
}

body {
  background-color: #0d0d0d;
  color: #e5e5e5;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
```

- [ ] **Step 5: Initialize shadcn/ui**

```powershell
npx shadcn@latest init
```

When prompted:
- Style: Default
- Base color: Neutral
- CSS variables: yes

Then add the components you will use:

```powershell
npx shadcn@latest add button badge table tabs dialog input select textarea toast
```

- [ ] **Step 6: Write `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
```

- [ ] **Step 7: Verify dev server starts**

```powershell
npm run dev
```

Expected: Vite dev server starts at http://localhost:5173 with the default React template page. Stop with Ctrl+C.

- [ ] **Step 8: Commit**

```powershell
cd C:\dev\joblin
git add frontend/
git commit -m "chore: Vite React TypeScript scaffold with Tailwind and shadcn/ui"
```

---

## Task 25: API client layer

**Files:**
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/companies.ts`
- Create: `frontend/src/api/jobs.ts`
- Create: `frontend/src/api/matches.ts`
- Create: `frontend/src/api/runs.ts`
- Create: `frontend/src/api/settings.ts`
- Create: `frontend/src/api/stats.ts`

- [ ] **Step 1: Write `frontend/src/lib/utils.ts`**

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "Never";
  return new Date(iso).toLocaleString();
}

export function formatScore(score: number): string {
  return (score * 100).toFixed(0) + "%";
}
```

Install clsx and tailwind-merge:
```powershell
cd C:\dev\joblin\frontend
npm install clsx tailwind-merge
```

- [ ] **Step 2: Write `frontend/src/api/client.ts`**

```ts
import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});
```

- [ ] **Step 3: Write `frontend/src/api/companies.ts`**

```ts
import { api } from "./client";

export interface Company {
  id: number;
  name: string;
  careers_url: string;
  ats_type: string;
  is_active: boolean;
  quarantine_count: number;
  quarantined_at: string | null;
  quarantine_reason: string | null;
}

export interface ProbeResult {
  ats_type: string;
  identifier: string | null;
  probe_attempts: Array<{ url: string; status_code: number | null; error: string | null }>;
}

export const companiesApi = {
  list: () => api.get<Company[]>("/companies").then((r) => r.data),
  probe: (name: string, careers_url: string) =>
    api.post<ProbeResult>("/companies/probe", { name, careers_url }).then((r) => r.data),
  add: (name: string, careers_url: string) =>
    api.post("/companies", { name, careers_url }).then((r) => r.data),
  update: (id: number, data: Partial<{ css_selector: string; is_active: boolean; ats_type: string; ats_identifier: string }>) =>
    api.patch(`/companies/${id}`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/companies/${id}`),
  retry: (id: number) => api.post(`/companies/${id}/retry`).then((r) => r.data),
  importCsv: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/companies/import", form, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
  },
};
```

- [ ] **Step 4: Write `frontend/src/api/jobs.ts`**

```ts
import { api } from "./client";

export interface Job {
  id: number;
  company_id: number;
  title: string;
  location: string | null;
  url: string;
  first_seen_at: string;
  is_active: boolean;
}

export interface JobDetail extends Job {
  raw_description: string;
  match: { score: number; tier: string; summary: string } | null;
}

export const jobsApi = {
  list: (params?: { company_id?: number; search?: string; limit?: number; offset?: number }) =>
    api.get<Job[]>("/jobs", { params }).then((r) => r.data),
  get: (id: number) => api.get<JobDetail>(`/jobs/${id}`).then((r) => r.data),
  dismiss: (id: number) => api.post(`/jobs/${id}/dismiss`).then((r) => r.data),
};
```

- [ ] **Step 5: Write `frontend/src/api/matches.ts`**

```ts
import { api } from "./client";

export interface Match {
  id: number;
  job_id: number;
  score: number;
  tier: "strong" | "borderline";
  summary: string;
  is_preview: boolean;
  notified_at: string | null;
  not_interested_at: string | null;
  created_at: string;
}

export const matchesApi = {
  list: (params?: { tier?: string; limit?: number; offset?: number }) =>
    api.get<Match[]>("/matches", { params }).then((r) => r.data),
  notify: (match_ids: number[]) => api.post("/matches/notify", { match_ids }).then((r) => r.data),
};
```

- [ ] **Step 6: Write `frontend/src/api/runs.ts`**

```ts
import { api } from "./client";

export interface Run {
  id: number;
  status: "running" | "completed" | "failed";
  is_preview: boolean;
  started_at: string;
  completed_at: string | null;
  total_jobs_found: number;
  total_confirmed: number;
  total_notified: number;
}

export const runsApi = {
  list: () => api.get<Run[]>("/runs").then((r) => r.data),
  get: (id: number) => api.get(`/runs/${id}`).then((r) => r.data),
  start: (params: { company_ids?: number[]; preview?: boolean }) =>
    api.post<{ id: number; status: string }>("/runs", params).then((r) => r.data),
};
```

- [ ] **Step 7: Write `frontend/src/api/settings.ts`**

```ts
import { api } from "./client";

export const settingsApi = {
  get: () => api.get("/settings").then((r) => r.data),
  update: (data: Record<string, unknown>) => api.patch("/settings", data).then((r) => r.data),
  testDiscord: () => api.post("/settings/discord/test").then((r) => r.data),
  testCriteria: (description: string) =>
    api.post("/settings/criteria/test", { description }).then((r) => r.data),
  listPresets: () => api.get("/presets").then((r) => r.data),
  applyPreset: (name: string) => api.post(`/presets/${name}/apply`).then((r) => r.data),
};
```

- [ ] **Step 8: Write `frontend/src/api/stats.ts`**

```ts
import { api } from "./client";

export interface Stats {
  total_companies: number;
  total_jobs_in_db: number;
  todays_matches: number;
  strong_today: number;
  quarantine_count: number;
  last_run_completed_at: string | null;
}

export const statsApi = {
  get: () => api.get<Stats>("/stats").then((r) => r.data),
};
```

- [ ] **Step 9: Commit**

```powershell
cd C:\dev\joblin
git add frontend/src/api/ frontend/src/lib/
git commit -m "feat: typed API client layer for all endpoints"
```

---

## Task 26: App shell + collapsible sidebar

**Files:**
- Create: `frontend/src/hooks/useSseRun.ts`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/Topbar.tsx`
- Create: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write `frontend/src/hooks/useSseRun.ts`**

```ts
import { useEffect, useState } from "react";

export interface SseEvent {
  type: string;
  data: Record<string, unknown>;
}

export function useSseRun(runId: number | null) {
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!runId) return;
    setEvents([]);
    setDone(false);

    const es = new EventSource(`/api/runs/${runId}/stream`);

    const handleMessage = (e: MessageEvent, type: string) => {
      const data = JSON.parse(e.data || "{}");
      setEvents((prev) => [...prev, { type, data }]);
      if (type === "run_done") {
        setDone(true);
        es.close();
      }
    };

    ["run_started", "company_scraping", "company_done", "company_failed", "discord_posted", "run_done"].forEach(
      (eventType) => {
        es.addEventListener(eventType, (e) => handleMessage(e as MessageEvent, eventType));
      }
    );

    es.onerror = () => es.close();

    return () => es.close();
  }, [runId]);

  return { events, done };
}
```

- [ ] **Step 2: Write `frontend/src/components/Sidebar.tsx`**

```tsx
import { useState, useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

const NAV = [
  { label: "Dashboard", icon: "◼", path: "/", badge: null },
  { label: "Matches", icon: "★", path: "/matches", badge: null },
  { label: "All Jobs", icon: "≡", path: "/jobs", badge: null },
  { label: "Companies", icon: "⊞", path: "/companies", badge: null, warn: true },
  { label: "Runs", icon: "▶", path: "/runs", badge: null },
  { label: "Settings", icon: "⚙", path: "/settings", badge: null },
];

export function Sidebar({ quarantineCount = 0 }: { quarantineCount?: number }) {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem("sidebar_collapsed") === "true";
  });

  useEffect(() => {
    localStorage.setItem("sidebar_collapsed", String(collapsed));
  }, [collapsed]);

  if (collapsed) {
    return (
      <aside className="flex flex-col items-center w-11 bg-[#111] border-r border-[#1e1e1e] shrink-0 py-3">
        <div className="font-black text-[#4e9eff] text-sm pb-3 border-b border-[#1e1e1e] w-full text-center mb-2">J</div>
        {NAV.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            title={item.label}
            className={({ isActive }) =>
              cn("w-8 h-7 flex items-center justify-center rounded text-sm mb-0.5 relative",
                isActive ? "bg-[#1a1a1a] text-[#e5e5e5]" : "text-[#555] hover:text-[#888]")
            }
          >
            {item.icon}
            {item.warn && quarantineCount > 0 && (
              <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-orange-500" />
            )}
          </NavLink>
        ))}
        <button
          onClick={() => setCollapsed(false)}
          className="mt-auto text-[#555] hover:text-[#888] text-xs border border-[#2a2a2a] rounded w-7 h-6 flex items-center justify-center"
        >
          &rsaquo;
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex flex-col w-44 bg-[#111] border-r border-[#1e1e1e] shrink-0 py-3">
      <div className="flex items-center justify-between px-3 pb-3 border-b border-[#1e1e1e] mb-2">
        <span className="font-bold text-sm text-[#e5e5e5]">
          Job<span className="text-[#4e9eff]">lin</span>
        </span>
        <button
          onClick={() => setCollapsed(true)}
          className="text-[#555] hover:text-[#888] text-xs border border-[#2a2a2a] rounded w-5 h-5 flex items-center justify-center"
        >
          &lsaquo;
        </button>
      </div>
      {NAV.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          end={item.path === "/"}
          className={({ isActive }) =>
            cn("flex items-center gap-2 px-3 py-1.5 text-xs",
              isActive
                ? "text-[#e5e5e5] bg-[#1a1a1a] border-l-2 border-[#4e9eff] pl-[10px]"
                : "text-[#666] hover:text-[#999]")
          }
        >
          <span className="w-3.5 text-center">{item.icon}</span>
          {item.label}
          {item.warn && quarantineCount > 0 && (
            <span className="ml-auto bg-orange-900/50 text-orange-400 text-[10px] px-1 rounded-full">
              {quarantineCount}
            </span>
          )}
        </NavLink>
      ))}
      <div className="mt-auto px-3 pt-2 border-t border-[#1a1a1a] text-[9px] text-[#444]">
        Joblin
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Write `frontend/src/components/Topbar.tsx`**

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { runsApi } from "@/api/runs";

export function Topbar({ title }: { title: string }) {
  const qc = useQueryClient();

  const runMutation = useMutation({
    mutationFn: (preview: boolean) => runsApi.start({ preview }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });

  return (
    <header className="flex items-center justify-between px-5 py-2.5 border-b border-[#1a1a1a] bg-[#0d0d0d] shrink-0">
      <h1 className="font-semibold text-sm text-[#e5e5e5]">{title}</h1>
      <div className="flex gap-2">
        <button
          onClick={() => runMutation.mutate(true)}
          disabled={runMutation.isPending}
          className="border border-[#2a2a2a] rounded px-2.5 py-1 text-[11px] text-[#aaa] bg-[#161616] hover:bg-[#1f1f1f]"
        >
          Preview run
        </button>
        <button
          onClick={() => runMutation.mutate(false)}
          disabled={runMutation.isPending}
          className="border border-[#4e9eff] rounded px-2.5 py-1 text-[11px] text-[#4e9eff] bg-[#0e2040] hover:bg-[#0d2850]"
        >
          {runMutation.isPending ? "Starting..." : "Run now"}
        </button>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Write `frontend/src/components/Layout.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { statsApi } from "@/api/stats";

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/matches": "Matches",
  "/jobs": "All Jobs",
  "/companies": "Companies",
  "/runs": "Runs",
  "/settings": "Settings",
};

export function Layout() {
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: statsApi.get,
    refetchInterval: 30000,
  });

  const path = window.location.pathname;
  const title = Object.entries(TITLES).find(([k]) => path === k || path.startsWith(k + "/"))?.[1] ?? "Joblin";

  return (
    <div className="flex h-screen overflow-hidden bg-[#0d0d0d]">
      <Sidebar quarantineCount={stats?.quarantine_count ?? 0} />
      <main className="flex flex-col flex-1 overflow-hidden">
        <Topbar title={title} />
        <div className="flex-1 overflow-auto p-5">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Write `frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Matches } from "./pages/Matches";
import { Jobs } from "./pages/Jobs";
import { Companies } from "./pages/Companies";
import { Runs } from "./pages/Runs";
import { RunDetail } from "./pages/RunDetail";
import { Settings } from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
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
    </BrowserRouter>
  );
}
```

- [ ] **Step 6: Write `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, retry: 1 } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
```

- [ ] **Step 7: Verify dev server shows the layout**

Start the FastAPI backend in one terminal:
```powershell
cd C:\dev\joblin && .venv/Scripts/uvicorn backend.main:app --port 8000 --reload
```

Start the Vite dev server in another:
```powershell
cd C:\dev\joblin\frontend && npm run dev
```

Open http://localhost:5173. Expected: dark shell with sidebar, topbar, no page errors.

- [ ] **Step 8: Commit**

```powershell
cd C:\dev\joblin
git add frontend/src/
git commit -m "feat: app shell with collapsible sidebar, topbar, and router"
```

---

## Task 27: Dashboard, Matches, and Jobs screens

**Files:**
- Create: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/pages/Matches.tsx`
- Create: `frontend/src/pages/Jobs.tsx`

- [ ] **Step 1: Write `frontend/src/pages/Dashboard.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { statsApi } from "@/api/stats";
import { matchesApi, Match } from "@/api/matches";
import { formatDate } from "@/lib/utils";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="border border-[#1e1e1e] rounded-lg p-3 bg-[#111]">
      <div className="font-mono text-xl font-bold text-[#e5e5e5]">{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-[#555] mt-0.5">{label}</div>
      {sub && <div className="text-[10px] text-emerald-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function MatchRow({ match }: { match: Match }) {
  const isStrong = match.tier === "strong";
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-[#161616] text-xs">
      <span className={`w-2 h-2 rounded-full shrink-0 ${isStrong ? "bg-emerald-500" : "bg-yellow-500"}`} />
      <Link to={`/matches`} className="flex-1 text-[#ccc] hover:text-white truncate">
        {match.tier === "strong" ? "Strong match" : "Borderline"} -- score {(match.score * 100).toFixed(0)}%
      </Link>
      <span className="text-[#555] font-mono">{formatDate(match.created_at)}</span>
    </div>
  );
}

export function Dashboard() {
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: statsApi.get });
  const { data: matches } = useQuery({ queryKey: ["matches", "recent"], queryFn: () => matchesApi.list({ limit: 10 }) });

  return (
    <div>
      {stats && stats.quarantine_count > 0 && (
        <div className="mb-4 border border-orange-900 bg-orange-950/30 rounded-lg px-4 py-2 text-xs text-orange-400 flex items-center gap-2">
          <span>Warning:</span>
          <span>{stats.quarantine_count} {stats.quarantine_count === 1 ? "company" : "companies"} quarantined due to repeated failures.</span>
          <Link to="/companies" className="underline ml-1">Review</Link>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-6">
        <StatCard label="Today's matches" value={stats?.todays_matches ?? 0} />
        <StatCard label="Strong matches" value={stats?.strong_today ?? 0} />
        <StatCard label="Companies" value={stats?.total_companies ?? 0} />
        <StatCard label="Jobs in DB" value={stats?.total_jobs_in_db ?? 0} />
      </div>

      <div className="text-[10px] uppercase tracking-wider text-[#555] mb-2">Recent matches</div>
      {matches?.length === 0 && (
        <p className="text-[#555] text-sm">No matches yet. Add companies and run a scrape.</p>
      )}
      {matches?.map((m) => <MatchRow key={m.id} match={m} />)}
    </div>
  );
}
```

- [ ] **Step 2: Write `frontend/src/pages/Matches.tsx`**

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { matchesApi, Match } from "@/api/matches";
import { jobsApi } from "@/api/jobs";
import { formatScore, formatDate } from "@/lib/utils";

function MatchRow({ match, selected, onSelect }: { match: Match; selected: boolean; onSelect: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const { data: job } = useQuery({
    queryKey: ["job", match.job_id],
    queryFn: () => jobsApi.get(match.job_id),
    enabled: expanded,
  });
  const qc = useQueryClient();
  const dismiss = useMutation({
    mutationFn: () => jobsApi.dismiss(match.job_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["matches"] }),
  });

  const isStrong = match.tier === "strong";

  return (
    <div className="border border-[#1e1e1e] rounded-lg mb-2 overflow-hidden">
      <div
        className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-[#111]"
        onClick={() => setExpanded(!expanded)}
      >
        <input type="checkbox" checked={selected} onChange={onSelect} onClick={(e) => e.stopPropagation()} />
        <span className={`w-2 h-2 rounded-full shrink-0 ${isStrong ? "bg-emerald-500" : "bg-yellow-500"}`} />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-[#e5e5e5] truncate">Job #{match.job_id}</div>
          <div className="text-[11px] text-[#666]">{formatDate(match.created_at)}</div>
        </div>
        <span className="font-mono text-xs text-[#888]">{formatScore(match.score)}</span>
        {match.is_preview && (
          <span className="bg-purple-900/40 text-purple-400 text-[10px] px-1.5 rounded">preview</span>
        )}
      </div>
      {expanded && (
        <div className="px-4 pb-4 border-t border-[#1e1e1e] bg-[#0a0a0a]">
          {match.summary && <pre className="text-xs text-[#ccc] whitespace-pre-wrap mt-3 font-sans">{match.summary}</pre>}
          {job?.raw_description && (
            <details className="mt-3">
              <summary className="text-[11px] text-[#555] cursor-pointer">Full job description</summary>
              <pre className="text-[11px] text-[#777] whitespace-pre-wrap mt-2 max-h-60 overflow-auto">{job.raw_description}</pre>
            </details>
          )}
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => dismiss.mutate()}
              className="text-[11px] border border-[#2a2a2a] rounded px-2 py-1 text-[#888] hover:text-[#ccc]"
            >
              Not interested
            </button>
            {job?.url && (
              <a href={job.url} target="_blank" rel="noreferrer"
                className="text-[11px] border border-[#4e9eff] rounded px-2 py-1 text-[#4e9eff] hover:bg-[#0e2040]">
                Apply
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function Matches() {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [tier, setTier] = useState<string>("");
  const qc = useQueryClient();

  const { data: matches = [], isLoading } = useQuery({
    queryKey: ["matches", tier],
    queryFn: () => matchesApi.list({ tier: tier || undefined }),
  });

  const bulkNotify = useMutation({
    mutationFn: () => matchesApi.notify(Array.from(selected)),
    onSuccess: () => { setSelected(new Set()); qc.invalidateQueries({ queryKey: ["matches"] }); },
  });

  const toggle = (id: number) =>
    setSelected((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <select value={tier} onChange={(e) => setTier(e.target.value)}
          className="bg-[#111] border border-[#2a2a2a] rounded px-2 py-1 text-xs text-[#ccc]">
          <option value="">All tiers</option>
          <option value="strong">Strong</option>
          <option value="borderline">Borderline</option>
        </select>
        {selected.size > 0 && (
          <button onClick={() => bulkNotify.mutate()}
            className="text-xs border border-[#4e9eff] rounded px-3 py-1 text-[#4e9eff] bg-[#0e2040]">
            Re-notify {selected.size} selected
          </button>
        )}
      </div>
      {isLoading && <p className="text-[#555] text-sm">Loading...</p>}
      {matches.map((m) => (
        <MatchRow key={m.id} match={m} selected={selected.has(m.id)} onSelect={() => toggle(m.id)} />
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/src/pages/Jobs.tsx`**

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { jobsApi, Job } from "@/api/jobs";
import { formatDate } from "@/lib/utils";

function JobRow({ job }: { job: Job }) {
  const [expanded, setExpanded] = useState(false);
  const { data: detail } = useQuery({
    queryKey: ["job", job.id],
    queryFn: () => jobsApi.get(job.id),
    enabled: expanded,
  });
  const qc = useQueryClient();
  const dismiss = useMutation({
    mutationFn: () => jobsApi.dismiss(job.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });

  return (
    <div className="border border-[#1e1e1e] rounded-lg mb-1.5 overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-[#111]"
        onClick={() => setExpanded(!expanded)}>
        <div className="flex-1 min-w-0">
          <div className="text-sm text-[#e5e5e5] truncate">{job.title}</div>
          <div className="text-[11px] text-[#555]">{job.location} &bull; {formatDate(job.first_seen_at)}</div>
        </div>
      </div>
      {expanded && detail && (
        <div className="px-4 pb-3 border-t border-[#1e1e1e] bg-[#0a0a0a]">
          {detail.match && (
            <div className="mt-2 text-xs text-[#888]">
              Score: <span className="font-mono">{(detail.match.score * 100).toFixed(0)}%</span> | {detail.match.tier}
              {detail.match.summary && <pre className="mt-1 whitespace-pre-wrap font-sans text-[#bbb]">{detail.match.summary}</pre>}
            </div>
          )}
          <div className="flex gap-2 mt-2">
            <button onClick={() => dismiss.mutate()}
              disabled={dismiss.isPending || !!detail.match?.not_interested_at}
              className="text-[11px] border border-[#2a2a2a] rounded px-2 py-1 text-[#888] hover:text-[#ccc] disabled:opacity-40">
              Not interested
            </button>
            <a href={detail.url} target="_blank" rel="noreferrer"
              className="text-[11px] border border-[#2a2a2a] rounded px-2 py-1 text-[#888] hover:text-[#ccc]">
              Open
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

export function Jobs() {
  const [search, setSearch] = useState("");
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ["jobs", search],
    queryFn: () => jobsApi.list({ search: search || undefined }),
  });

  return (
    <div>
      <div className="mb-4">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search job titles..."
          className="bg-[#111] border border-[#2a2a2a] rounded px-3 py-1.5 text-xs text-[#ccc] w-64"
        />
      </div>
      {isLoading && <p className="text-[#555] text-sm">Loading...</p>}
      {jobs.map((j) => <JobRow key={j.id} job={j} />)}
    </div>
  );
}
```

- [ ] **Step 4: Verify screens render in the browser at http://localhost:5173**

Start both backend (port 8000) and frontend dev server (port 5173). Navigate to `/`, `/matches`, `/jobs`. Expected: no console errors, data loads from API.

- [ ] **Step 5: Commit**

```powershell
cd C:\dev\joblin
git add frontend/src/pages/Dashboard.tsx frontend/src/pages/Matches.tsx frontend/src/pages/Jobs.tsx
git commit -m "feat: Dashboard, Matches, and Jobs screens"
```

---

## Task 28: Companies, Runs, and Settings screens

**Files:**
- Create: `frontend/src/pages/Companies.tsx`
- Create: `frontend/src/pages/Runs.tsx`
- Create: `frontend/src/pages/RunDetail.tsx`
- Create: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: Write `frontend/src/pages/Companies.tsx`**

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { companiesApi, Company, ProbeResult } from "@/api/companies";
import { formatDate } from "@/lib/utils";

function AddModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [probing, setProbing] = useState(false);
  const qc = useQueryClient();

  const add = useMutation({
    mutationFn: () => companiesApi.add(name, url),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["companies"] }); onClose(); },
  });

  const handleProbe = async () => {
    setProbing(true);
    try { setProbe(await companiesApi.probe(name, url)); }
    finally { setProbing(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-[#111] border border-[#2a2a2a] rounded-xl p-6 w-full max-w-md">
        <h2 className="text-sm font-semibold mb-4">Add Company</h2>
        <input value={name} onChange={(e) => setName(e.target.value)}
          placeholder="Company name" className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm mb-2 text-[#e5e5e5]" />
        <input value={url} onChange={(e) => setUrl(e.target.value)}
          placeholder="Careers URL" className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm mb-3 text-[#e5e5e5]" />
        {probe && (
          <div className="mb-3 text-xs border border-[#2a2a2a] rounded p-2 bg-[#0a0a0a]">
            <div className="text-[#888]">Detected: <span className="text-[#4e9eff]">{probe.ats_type}</span></div>
            {probe.probe_attempts.map((a, i) => (
              <div key={i} className="text-[#555] mt-0.5">{a.url} -- {a.status_code ?? a.error}</div>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <button onClick={handleProbe} disabled={!name || !url || probing}
            className="text-xs border border-[#2a2a2a] rounded px-3 py-1.5 text-[#888]">
            {probing ? "Probing..." : "Probe ATS"}
          </button>
          <button onClick={() => add.mutate()} disabled={!name || !url || add.isPending}
            className="text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040]">
            {add.isPending ? "Adding..." : "Add"}
          </button>
          <button onClick={onClose} className="text-xs border border-[#2a2a2a] rounded px-3 py-1.5 text-[#888] ml-auto">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export function Companies() {
  const [showAdd, setShowAdd] = useState(false);
  const qc = useQueryClient();
  const { data: companies = [], isLoading } = useQuery({ queryKey: ["companies"], queryFn: companiesApi.list });

  const remove = useMutation({
    mutationFn: (id: number) => companiesApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
  const retry = useMutation({
    mutationFn: (id: number) => companiesApi.retry(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });

  return (
    <div>
      {showAdd && <AddModal onClose={() => setShowAdd(false)} />}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => setShowAdd(true)}
          className="text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040]">
          Add company
        </button>
      </div>
      {isLoading && <p className="text-[#555] text-sm">Loading...</p>}
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[#1e1e1e] text-[#555] text-left">
            <th className="py-2 pr-4">Company</th>
            <th className="py-2 pr-4">ATS</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {companies.map((c) => (
            <tr key={c.id} className="border-b border-[#111] hover:bg-[#0f0f0f]">
              <td className="py-2 pr-4 text-[#e5e5e5]">{c.name}</td>
              <td className="py-2 pr-4">
                <span className="bg-[#1e2a3a] text-[#4e9eff] px-1.5 rounded text-[10px]">{c.ats_type}</span>
              </td>
              <td className="py-2 pr-4">
                {c.quarantined_at
                  ? <span className="text-orange-400">Quarantined</span>
                  : <span className="text-emerald-500">Active</span>}
              </td>
              <td className="py-2 flex gap-2">
                {c.quarantined_at && (
                  <button onClick={() => retry.mutate(c.id)} className="text-[#4e9eff] hover:underline">Retry</button>
                )}
                <button onClick={() => remove.mutate(c.id)} className="text-red-500 hover:underline">Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Write `frontend/src/pages/Runs.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { runsApi, Run } from "@/api/runs";
import { formatDate } from "@/lib/utils";

export function Runs() {
  const { data: runs = [], isLoading } = useQuery({ queryKey: ["runs"], queryFn: runsApi.list });

  return (
    <div>
      {isLoading && <p className="text-[#555] text-sm">Loading...</p>}
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[#1e1e1e] text-[#555] text-left">
            <th className="py-2 pr-4">Started</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2 pr-4">Found</th>
            <th className="py-2 pr-4">Confirmed</th>
            <th className="py-2">Preview</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} className="border-b border-[#111] hover:bg-[#0f0f0f]">
              <td className="py-2 pr-4">
                <Link to={`/runs/${r.id}`} className="text-[#4e9eff] hover:underline">{formatDate(r.started_at)}</Link>
              </td>
              <td className="py-2 pr-4">
                <span className={r.status === "completed" ? "text-emerald-500" : r.status === "running" ? "text-yellow-400" : "text-red-400"}>
                  {r.status}
                </span>
              </td>
              <td className="py-2 pr-4 font-mono">{r.total_jobs_found}</td>
              <td className="py-2 pr-4 font-mono">{r.total_confirmed}</td>
              <td className="py-2">{r.is_preview ? "Yes" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/src/pages/RunDetail.tsx`**

```tsx
import { useParams } from "react-router-dom";
import { useSseRun } from "@/hooks/useSseRun";
import { useQuery } from "@tanstack/react-query";
import { runsApi } from "@/api/runs";

export function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const runId = id ? parseInt(id) : null;
  const { events, done } = useSseRun(runId);
  const { data: run } = useQuery({ queryKey: ["run", runId], queryFn: () => runsApi.get(runId!), enabled: !!runId });

  return (
    <div>
      <h2 className="text-sm font-semibold mb-4">Run #{runId}</h2>
      {run && (
        <div className="text-xs text-[#666] mb-4">
          Status: <span className="text-[#e5e5e5]">{run.status}</span>
        </div>
      )}
      <div className="border border-[#1e1e1e] rounded-lg p-4 bg-[#0a0a0a] font-mono text-xs space-y-1 max-h-96 overflow-auto">
        {events.length === 0 && !done && <div className="text-[#555]">Waiting for events...</div>}
        {events.map((e, i) => (
          <div key={i} className="text-[#888]">
            <span className="text-[#4e9eff]">{e.type}</span>{" "}
            {JSON.stringify(e.data)}
          </div>
        ))}
        {done && <div className="text-emerald-500">Run complete.</div>}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Write `frontend/src/pages/Settings.tsx`**

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "@/api/settings";

type Tab = "discord" | "criteria" | "schedule" | "llm" | "presets";

export function Settings() {
  const [tab, setTab] = useState<Tab>("discord");
  const [testJd, setTestJd] = useState("");
  const [testResult, setTestResult] = useState<{ score?: number; reasoning?: string; error?: string } | null>(null);
  const qc = useQueryClient();

  const { data: settings = {} } = useQuery({ queryKey: ["settings"], queryFn: settingsApi.get });
  const { data: presets = [] } = useQuery({ queryKey: ["presets"], queryFn: settingsApi.listPresets });

  const update = useMutation({
    mutationFn: (data: Record<string, unknown>) => settingsApi.update(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  const applyPreset = useMutation({
    mutationFn: (name: string) => settingsApi.applyPreset(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  const testDiscord = useMutation({ mutationFn: settingsApi.testDiscord });

  const tabs: { key: Tab; label: string }[] = [
    { key: "discord", label: "Discord" },
    { key: "criteria", label: "Criteria" },
    { key: "schedule", label: "Schedule" },
    { key: "llm", label: "LLM Keys" },
    { key: "presets", label: "Presets" },
  ];

  return (
    <div>
      <div className="flex gap-1 mb-5 border-b border-[#1e1e1e]">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 text-xs border-b-2 -mb-px ${tab === t.key ? "border-[#4e9eff] text-[#4e9eff]" : "border-transparent text-[#666]"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "discord" && (
        <div className="space-y-3 max-w-md">
          <label className="block text-xs text-[#888]">Webhook URL</label>
          <input defaultValue={settings.discord_webhook_url || ""}
            onBlur={(e) => update.mutate({ discord_webhook_url: e.target.value })}
            className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]"
            placeholder="https://discord.com/api/webhooks/..." />
          <label className="block text-xs text-[#888] mt-3">Mention type</label>
          <select defaultValue={settings.discord_mention_type || "none"}
            onChange={(e) => update.mutate({ discord_mention_type: e.target.value })}
            className="bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]">
            <option value="none">None</option>
            <option value="user">User</option>
            <option value="role">Role</option>
          </select>
          {["user", "role"].includes(settings.discord_mention_type) && (
            <>
              <label className="block text-xs text-[#888]">Mention ID</label>
              <input defaultValue={settings.discord_mention_id || ""}
                onBlur={(e) => update.mutate({ discord_mention_id: e.target.value })}
                className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
            </>
          )}
          <button onClick={() => testDiscord.mutate()}
            className="text-xs border border-[#2a2a2a] rounded px-3 py-1.5 text-[#888] hover:text-[#ccc]">
            {testDiscord.isPending ? "Sending..." : "Send test notification"}
          </button>
          {testDiscord.data && <div className="text-xs text-emerald-500">Sent!</div>}
        </div>
      )}

      {tab === "criteria" && (
        <div className="space-y-3 max-w-lg">
          {["title_allowlist", "title_denylist", "location_allowlist", "location_denylist"].map((field) => (
            <div key={field}>
              <label className="block text-xs text-[#888] mb-1">{field.replace(/_/g, " ")}</label>
              <input defaultValue={(settings.criteria || {})[field] || ""}
                onBlur={(e) => update.mutate({ criteria: { ...(settings.criteria || {}), [field]: e.target.value } })}
                className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
            </div>
          ))}
          <label className="block text-xs text-[#888]">Profile description</label>
          <textarea defaultValue={(settings.criteria || {}).profile_description || ""}
            onBlur={(e) => update.mutate({ criteria: { ...(settings.criteria || {}), profile_description: e.target.value } })}
            rows={3}
            className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
          <div className="border-t border-[#1e1e1e] pt-3">
            <label className="block text-xs text-[#888] mb-1">Test against pasted JD</label>
            <textarea value={testJd} onChange={(e) => setTestJd(e.target.value)} rows={4}
              placeholder="Paste a job description here..."
              className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
            <button onClick={async () => setTestResult(await settingsApi.testCriteria(testJd))}
              className="mt-2 text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040]">
              Test criteria
            </button>
            {testResult && (
              <div className="mt-2 text-xs text-[#888]">
                {testResult.error ? <span className="text-red-400">{testResult.error}</span>
                  : <>Score: <span className="font-mono text-[#e5e5e5]">{((testResult.score ?? 0) * 100).toFixed(0)}%</span> -- {testResult.reasoning}</>}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "schedule" && (
        <div className="space-y-3 max-w-sm">
          <label className="block text-xs text-[#888]">Cron expression</label>
          <input defaultValue={settings.schedule_cron || "0 */4 * * *"}
            onBlur={(e) => update.mutate({ schedule_cron: e.target.value })}
            className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] font-mono" />
          <label className="block text-xs text-[#888]">Staleness threshold (hours)</label>
          <input type="number" defaultValue={settings.staleness_threshold_hours ?? 4}
            onBlur={(e) => update.mutate({ staleness_threshold_hours: parseFloat(e.target.value) })}
            className="w-32 bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
          <label className="flex items-center gap-2 text-xs text-[#888] cursor-pointer">
            <input type="checkbox" defaultChecked={!!settings.scheduler_enabled}
              onChange={(e) => update.mutate({ scheduler_enabled: e.target.checked })} />
            Enable scheduler
          </label>
        </div>
      )}

      {tab === "llm" && (
        <div className="space-y-3 max-w-md">
          {[
            { key: "groq_api_key", label: "Groq API Key" },
            { key: "cerebras_api_key", label: "Cerebras API Key" },
            { key: "gemini_api_key", label: "Gemini API Key" },
          ].map(({ key, label }) => (
            <div key={key}>
              <label className="block text-xs text-[#888] mb-1">{label}</label>
              <input type="password" defaultValue={settings[key] || ""}
                onBlur={(e) => update.mutate({ [key]: e.target.value })}
                className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
            </div>
          ))}
        </div>
      )}

      {tab === "presets" && (
        <div className="space-y-3">
          {(presets as Array<{ name: string; description: string }>).map((p) => (
            <div key={p.name} className="border border-[#1e1e1e] rounded-lg p-4 flex items-center justify-between">
              <div>
                <div className="text-sm text-[#e5e5e5] font-medium">{p.name}</div>
                <div className="text-xs text-[#666] mt-0.5">{p.description}</div>
              </div>
              <button onClick={() => applyPreset.mutate(p.name)}
                className="text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040]">
                Apply
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Verify all screens render without errors**

Visit each route: `/`, `/matches`, `/jobs`, `/companies`, `/runs`, `/settings`. Check browser console for errors.

- [ ] **Step 6: Commit**

```powershell
cd C:\dev\joblin
git add frontend/src/pages/ frontend/src/components/ frontend/src/hooks/
git commit -m "feat: all six UI screens implemented with TanStack Query"
```

---

**Phase 5 complete.** All screens are implemented and wired to the backend API. Proceed to Phase 6.
