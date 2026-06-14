import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  applicationsApi,
  ApplicationTracking,
  ApplicationStatus,
} from "../api/applications";

// ── helpers ──────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<ApplicationStatus, string> = {
  interested: "Interested",
  applied: "Applied",
  rejected: "Rejected",
  offer: "Offer",
};

const STATUS_STYLE: Record<ApplicationStatus, { badge: string; dot: string }> = {
  interested: { badge: "bg-purple-900/40 text-purple-400", dot: "bg-purple-400" },
  applied:    { badge: "bg-blue-900/40 text-blue-400",     dot: "bg-blue-400" },
  rejected:   { badge: "bg-red-900/40 text-red-400",       dot: "bg-red-400" },
  offer:      { badge: "bg-emerald-900/40 text-emerald-400", dot: "bg-emerald-400" },
};

function StatusBadge({ status }: { status: ApplicationStatus }) {
  const s = STATUS_STYLE[status];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium ${s.badge}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {STATUS_LABEL[status]}
    </span>
  );
}

// ── stats section ─────────────────────────────────────────────────────────────

function StatsSection() {
  const { data: stats } = useQuery({
    queryKey: ["applications", "stats"],
    queryFn: applicationsApi.stats,
  });

  const cards = [
    { label: "Total",         value: stats?.total ?? 0,                    color: "text-[#e5e5e5]" },
    { label: "Interested",    value: stats?.by_status.interested ?? 0,     color: "text-purple-400" },
    { label: "Applied",       value: stats?.by_status.applied ?? 0,        color: "text-blue-400" },
    { label: "Rejected",      value: stats?.by_status.rejected ?? 0,       color: "text-red-400" },
    { label: "Offer",         value: stats?.by_status.offer ?? 0,          color: "text-emerald-400" },
    { label: "Response Rate", value: `${stats?.response_rate ?? 0}%`,      color: "text-yellow-400" },
  ];

  const series = stats?.daily_series ?? [];
  const maxVal = Math.max(1, ...series.map((d) => (d.applied ?? 0) + (d.interested ?? 0)));
  const joblin = stats?.by_source.joblin ?? 0;
  const external = stats?.by_source.external ?? 0;
  const sourceTotal = joblin + external || 1;

  return (
    <div className="mb-6">
      <div className="grid grid-cols-6 gap-3 mb-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-[#111] border border-[#1e1e1e] rounded-lg p-3">
            <div className="text-[10px] text-[#444] uppercase tracking-wider mb-1.5">{c.label}</div>
            <div className={`text-2xl font-bold leading-none ${c.color}`}>{c.value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-[1fr_260px] gap-3">
        {/* Bar chart */}
        <div className="bg-[#111] border border-[#1e1e1e] rounded-lg p-4">
          <div className="text-[10px] text-[#444] uppercase tracking-wider mb-3">Applications over time (30 days)</div>
          <div className="flex items-end gap-1 h-16">
            {series.length === 0 && <div className="text-xs text-[#333] m-auto">No data yet</div>}
            {series.map((d) => {
              const a = d.applied ?? 0;
              const i = d.interested ?? 0;
              return (
                <div key={d.date} className="flex-1 flex flex-col justify-end h-full gap-px" title={`${d.date}: ${a} applied, ${i} interested`}>
                  {i > 0 && <div className="w-full rounded-sm bg-purple-500/60" style={{ height: `${Math.round((i / maxVal) * 100)}%` }} />}
                  {a > 0 && <div className="w-full rounded-sm bg-blue-500/60" style={{ height: `${Math.round((a / maxVal) * 100)}%` }} />}
                </div>
              );
            })}
          </div>
          <div className="flex gap-4 mt-2">
            <span className="flex items-center gap-1.5 text-[10px] text-[#555]"><span className="w-2 h-2 rounded-sm bg-blue-500/60" />Applied</span>
            <span className="flex items-center gap-1.5 text-[10px] text-[#555]"><span className="w-2 h-2 rounded-sm bg-purple-500/60" />Interested</span>
          </div>
        </div>

        {/* Source split */}
        <div className="bg-[#111] border border-[#1e1e1e] rounded-lg p-4">
          <div className="text-[10px] text-[#444] uppercase tracking-wider mb-4">Joblin vs External</div>
          <div className="space-y-4">
            {[
              { label: "Joblin-sourced", value: joblin,    textColor: "text-emerald-400", barColor: "bg-emerald-500/60" },
              { label: "External",       value: external,  textColor: "text-indigo-400",  barColor: "bg-indigo-500/60" },
            ].map((s) => (
              <div key={s.label}>
                <div className="flex justify-between mb-1">
                  <span className={`text-xs font-medium ${s.textColor}`}>{s.label}</span>
                  <span className={`text-xs font-bold ${s.textColor}`}>{s.value}</span>
                </div>
                <div className="h-1.5 bg-[#1e1e1e] rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${s.barColor}`} style={{ width: `${Math.round((s.value / sourceTotal) * 100)}%` }} />
                </div>
              </div>
            ))}
            <div className="text-[10px] text-[#333] text-center mt-2">{Math.round((joblin / sourceTotal) * 100)}% discovered by Joblin</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── inline status dropdown ────────────────────────────────────────────────────

function StatusDropdown({ app }: { app: ApplicationTracking }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();
  const update = useMutation({
    mutationFn: (status: ApplicationStatus) => applicationsApi.update(app.id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)}><StatusBadge status={app.status} /></button>
      {open && (
        <div className="absolute left-0 top-full mt-1 z-20 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg overflow-hidden shadow-xl w-36">
          {(["interested", "applied", "rejected", "offer"] as ApplicationStatus[]).map((s) => (
            <button
              key={s}
              className="w-full text-left px-3 py-2 text-xs hover:bg-[#222] flex items-center gap-2"
              onClick={() => { update.mutate(s); setOpen(false); }}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${STATUS_STYLE[s].dot}`} />
              {STATUS_LABEL[s]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── add external job modal ────────────────────────────────────────────────────

function AddExternalJobModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    company_name: "", job_title: "", url: "",
    status: "applied" as ApplicationStatus,
    applied_date: "", notes: "",
  });
  const set = (key: string, value: string) => setForm((f) => ({ ...f, [key]: value }));

  const create = useMutation({
    mutationFn: () => applicationsApi.create({
      company_name: form.company_name,
      job_title: form.job_title,
      url: form.url || undefined,
      applied_date: form.applied_date || undefined,
      notes: form.notes || undefined,
      status: form.status,
      source: "external",
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["applications"] }); onClose(); },
  });

  const showDate = ["applied", "rejected", "offer"].includes(form.status);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-[#111] border border-[#1e1e1e] rounded-xl w-full max-w-md p-6">
        <h2 className="text-sm font-semibold text-[#e5e5e5] mb-4">Add External Job</h2>
        <div className="space-y-3">
          {[
            { label: "Company *", key: "company_name", type: "text", placeholder: "" },
            { label: "Job Title *", key: "job_title", type: "text", placeholder: "" },
            { label: "URL", key: "url", type: "text", placeholder: "https://..." },
          ].map((f) => (
            <div key={f.key}>
              <label className="block text-[10px] text-[#555] uppercase tracking-wider mb-1">{f.label}</label>
              <input
                type={f.type}
                placeholder={f.placeholder}
                className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm text-[#e5e5e5] outline-none focus:border-[#4e9eff]"
                value={(form as Record<string, string>)[f.key]}
                onChange={(e) => set(f.key, e.target.value)}
              />
            </div>
          ))}
          <div>
            <label className="block text-[10px] text-[#555] uppercase tracking-wider mb-1">Status</label>
            <select
              className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm text-[#e5e5e5] outline-none"
              value={form.status}
              onChange={(e) => set("status", e.target.value)}
            >
              <option value="interested">Interested</option>
              <option value="applied">Applied</option>
              <option value="rejected">Rejected</option>
              <option value="offer">Offer</option>
            </select>
          </div>
          {showDate && (
            <div>
              <label className="block text-[10px] text-[#555] uppercase tracking-wider mb-1">Date Applied</label>
              <input
                type="date"
                className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm text-[#e5e5e5] outline-none focus:border-[#4e9eff]"
                value={form.applied_date}
                onChange={(e) => set("applied_date", e.target.value)}
              />
            </div>
          )}
          <div>
            <label className="block text-[10px] text-[#555] uppercase tracking-wider mb-1">Notes</label>
            <textarea
              className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm text-[#e5e5e5] outline-none focus:border-[#4e9eff] resize-none"
              rows={3}
              value={form.notes}
              onChange={(e) => set("notes", e.target.value)}
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button className="px-4 py-2 text-xs text-[#666] hover:text-[#999] border border-[#1e1e1e] rounded-md" onClick={onClose}>Cancel</button>
          <button
            className="px-4 py-2 text-xs bg-[#1d4ed8] hover:bg-blue-600 text-white rounded-md disabled:opacity-50"
            disabled={!form.company_name || !form.job_title || create.isPending}
            onClick={() => create.mutate()}
          >
            Add Job
          </button>
        </div>
      </div>
    </div>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────

const ALL_STATUSES = ["interested", "applied", "rejected", "offer"] as ApplicationStatus[];

export function Applications() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | "all">("all");
  const [sourceFilter, setSourceFilter] = useState<"all" | "joblin" | "external">("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [showModal, setShowModal] = useState(false);

  const { data: apps = [], isLoading } = useQuery({
    queryKey: ["applications", statusFilter, sourceFilter, search],
    queryFn: () => applicationsApi.list({
      status: statusFilter === "all" ? undefined : statusFilter,
      source: sourceFilter === "all" ? undefined : sourceFilter,
      search: search || undefined,
    }),
  });

  const { data: stats } = useQuery({
    queryKey: ["applications", "stats"],
    queryFn: applicationsApi.stats,
  });

  const bulkMutation = useMutation({
    mutationFn: (data: { ids: number[]; action: "status_change" | "delete"; status?: ApplicationStatus }) =>
      applicationsApi.bulkAction(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["applications"] }); setSelected(new Set()); },
  });

  const deleteSingle = useMutation({
    mutationFn: (id: number) => applicationsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  const toggleSelect = (id: number) =>
    setSelected((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const tabCount = (s: ApplicationStatus | "all") =>
    s === "all" ? (stats?.total ?? 0) : (stats?.by_status[s] ?? 0);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-5">
        <h1 className="text-base font-semibold text-[#e5e5e5]">Applications</h1>
        <p className="text-xs text-[#555] mt-0.5">Track jobs you're interested in, applied to, or heard back from</p>
      </div>

      <StatsSection />

      {/* Tab + control row */}
      <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <div className="flex gap-0.5 bg-[#111] border border-[#1e1e1e] rounded-lg p-1">
          {(["all", ...ALL_STATUSES] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                statusFilter === s ? "bg-[#1a2233] text-[#4e9eff]" : "text-[#555] hover:text-[#888]"
              }`}
            >
              {s === "all" ? "All" : STATUS_LABEL[s]}{" "}
              <span className={statusFilter === s ? "text-[#4e9eff]" : "text-[#333]"}>{tabCount(s)}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <select
            className="bg-[#111] border border-[#1e1e1e] rounded-md px-3 py-1.5 text-xs text-[#666] outline-none"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value as typeof sourceFilter)}
          >
            <option value="all">All sources</option>
            <option value="joblin">Joblin</option>
            <option value="external">External</option>
          </select>
          <input
            className="bg-[#111] border border-[#1e1e1e] rounded-md px-3 py-1.5 text-xs text-[#999] placeholder-[#333] outline-none focus:border-[#333] w-48"
            placeholder="Search company or role..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button
            className="bg-[#1d4ed8] hover:bg-blue-600 text-white text-xs font-medium px-3 py-1.5 rounded-md"
            onClick={() => setShowModal(true)}
          >
            + Add External Job
          </button>
        </div>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-3 bg-[#111] border border-[#2a2a2a] rounded-lg px-4 py-2.5">
          <span className="text-xs text-[#888]">{selected.size} selected</span>
          <div className="flex gap-2 ml-auto flex-wrap">
            {ALL_STATUSES.map((s) => (
              <button
                key={s}
                className="text-xs px-3 py-1 border border-[#1e1e1e] rounded-md text-[#666] hover:text-[#999] hover:border-[#333]"
                onClick={() => bulkMutation.mutate({ ids: [...selected], action: "status_change", status: s })}
              >
                {STATUS_LABEL[s]}
              </button>
            ))}
            <button
              className="text-xs px-3 py-1 border border-red-900/40 text-red-500/60 hover:text-red-400 rounded-md"
              onClick={() => { if (confirm(`Delete ${selected.size} application(s)?`)) bulkMutation.mutate({ ids: [...selected], action: "delete" }); }}
            >
              Delete
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-[#111] border border-[#1e1e1e] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1e1e] bg-[#0a0a0a]">
              <th className="w-10 px-4 py-2.5">
                <input
                  type="checkbox"
                  className="accent-[#4e9eff]"
                  checked={apps.length > 0 && selected.size === apps.length}
                  onChange={() => setSelected(apps.length === selected.size ? new Set() : new Set(apps.map((a) => a.id)))}
                />
              </th>
              {["Status", "Company", "Role", "Applied", "Source", "Score", "Notes", ""].map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-[10px] text-[#444] uppercase tracking-wider font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-xs text-[#444]">Loading...</td></tr>
            )}
            {!isLoading && apps.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-xs text-[#444]">No applications yet</td></tr>
            )}
            {apps.map((app) => (
              <tr key={app.id} className="border-b border-[#141414] hover:bg-[#0d0d0d]">
                <td className="w-10 px-4 py-2.5">
                  <input type="checkbox" className="accent-[#4e9eff]" checked={selected.has(app.id)} onChange={() => toggleSelect(app.id)} />
                </td>
                <td className="px-4 py-2.5"><StatusDropdown app={app} /></td>
                <td className="px-4 py-2.5 text-[#e5e5e5] font-medium text-xs">{app.company_name}</td>
                <td className="px-4 py-2.5 text-[#888] text-xs">{app.job_title}</td>
                <td className="px-4 py-2.5 text-[#555] text-xs">{app.applied_date ?? "—"}</td>
                <td className="px-4 py-2.5">
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${app.source === "joblin" ? "bg-emerald-900/30 text-emerald-500" : "bg-indigo-900/30 text-indigo-400"}`}>
                    {app.source === "joblin" ? "Joblin" : "External"}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs">
                  {app.score != null
                    ? <span className="bg-blue-900/30 text-blue-400 px-1.5 py-0.5 rounded font-semibold">{app.score.toFixed(2)}</span>
                    : <span className="text-[#333]">—</span>}
                </td>
                <td className="px-4 py-2.5 text-[#444] text-xs max-w-[180px] truncate">{app.notes ?? ""}</td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-1.5">
                    {app.url && (
                      <a href={app.url} target="_blank" rel="noreferrer" className="text-[10px] px-2 py-1 border border-[#1e1e1e] rounded text-[#555] hover:text-[#4e9eff] hover:border-[#333]">↗</a>
                    )}
                    <button
                      className="text-[10px] px-2 py-1 border border-red-900/30 text-red-500/40 hover:text-red-400 rounded"
                      onClick={() => { if (confirm("Remove this application?")) deleteSingle.mutate(app.id); }}
                    >✕</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && <AddExternalJobModal onClose={() => setShowModal(false)} />}
    </div>
  );
}
