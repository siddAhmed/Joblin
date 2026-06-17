import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { matchesApi } from "@/api/matches";
import type { Match } from "@/api/matches";
import { jobsApi } from "@/api/jobs";
import { formatScore } from "@/lib/utils";
import { applicationsApi } from "@/api/applications";
import type { ApplicationTracking, ApplicationStatus } from "@/api/applications";

function TrackButtons({
  match,
  trackerMap,
}: {
  match: Match;
  trackerMap: Map<number, ApplicationTracking>;
}) {
  const qc = useQueryClient();
  const tracked = trackerMap.get(match.job_id);

  const track = useMutation({
    mutationFn: (status: ApplicationStatus) =>
      applicationsApi.create({
        job_id: match.job_id,
        company_name: match.company_name,
        job_title: match.job_title,
        url: match.job_url ?? undefined,
        status,
        source: "joblin",
        score: match.score,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  const isInterested = tracked?.status === "interested";
  const isApplied =
    tracked?.status === "applied" ||
    tracked?.status === "rejected" ||
    tracked?.status === "offer";

  return (
    <>
      <button
        className={`text-xs px-3 py-1.5 border rounded-md transition-colors ${
          isInterested
            ? "bg-purple-900/40 border-purple-800/60 text-purple-400"
            : "border-[#1e1e1e] text-[#666] hover:text-purple-400 hover:border-purple-900/60"
        }`}
        onClick={() => { if (!isInterested) track.mutate("interested"); }}
        disabled={track.isPending}
      >
        ★ Interested
      </button>
      <button
        className={`text-xs px-3 py-1.5 border rounded-md transition-colors ${
          isApplied
            ? "bg-blue-900/40 border-blue-800/60 text-blue-400"
            : "border-[#1e1e1e] text-[#666] hover:text-blue-400 hover:border-blue-900/60"
        }`}
        onClick={() => { if (!isApplied) track.mutate("applied"); }}
        disabled={track.isPending}
      >
        ✓ Applied
      </button>
    </>
  );
}

function MatchRow({
  match,
  selected,
  onSelect,
  trackerMap,
  autoExpand,
}: {
  match: Match;
  selected: boolean;
  onSelect: () => void;
  trackerMap: Map<number, ApplicationTracking>;
  autoExpand?: boolean;
}) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(autoExpand ?? false);
  const rowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoExpand && rowRef.current) {
      rowRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [autoExpand]);
  const { data: job } = useQuery({ queryKey: ["job", match.job_id], queryFn: () => jobsApi.get(match.job_id), enabled: expanded });
  const qc = useQueryClient();
  const applyUrl = match.job_url || job?.url;
  const dismiss = useMutation({ mutationFn: () => jobsApi.dismiss(match.job_id), onSuccess: () => qc.invalidateQueries({ queryKey: ["matches"] }) });
  const hideMatch = useMutation({
    mutationFn: () => matchesApi.dismiss(match.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["matches"] }),
  });

  const isStrong = match.tier === "strong";
  return (
    <div ref={rowRef} className={`border rounded-lg mb-2 overflow-hidden transition-colors ${autoExpand ? "border-emerald-800/60" : "border-[#1e1e1e]"}`}>
      <div className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-[#111]" onClick={() => setExpanded(!expanded)}>
        <input type="checkbox" checked={selected} onChange={onSelect} onClick={(e) => e.stopPropagation()} />
        <span className={`w-2 h-2 rounded-full shrink-0 ${isStrong ? "bg-emerald-500" : "bg-yellow-500"}`} />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-[#e5e5e5] truncate">{match.job_title}</div>
          <div className="text-[11px] text-[#888] truncate">
            {match.company_name}{match.location ? ` · ${match.location}` : ""}
          </div>
          {match.summary && (
            <div className="text-[11px] text-[#555] truncate mt-0.5">{match.summary}</div>
          )}
        </div>
        <span className="font-mono text-xs text-[#888]">{formatScore(match.score)}</span>
        {match.is_preview && <span className="bg-purple-900/40 text-purple-400 text-[10px] px-1.5 rounded">preview</span>}
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
              onClick={() => hideMatch.mutate()}
              disabled={hideMatch.isPending}
              className="text-[11px] border border-[#2a2a2a] rounded px-2 py-1 text-[#888] hover:text-red-400"
            >
              Dismiss
            </button>
            <button onClick={() => dismiss.mutate()} className="text-[11px] border border-[#2a2a2a] rounded px-2 py-1 text-[#888] hover:text-[#ccc]">Not interested</button>
            {applyUrl && (
              <a
                href={applyUrl}
                target="_blank"
                rel="noreferrer"
                className="text-xs px-3 py-1.5 border border-[#1e1e1e] rounded-md text-[#4e9eff] hover:border-[#333]"
              >
                ↗ View JD
              </a>
            )}
            <TrackButtons match={match} trackerMap={trackerMap} />
            <button
              onClick={() => navigate(`/resume?jobId=${match.job_id}`)}
              className="text-[11px] border border-[#4e4e9f] rounded px-2 py-1 text-[#a78bfa] hover:bg-[#1a1a3a]"
            >
              ✦ Tailor Resume
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function Matches() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const expandId = searchParams.get("expand") ? Number(searchParams.get("expand")) : null;
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [tier, setTier] = useState("");
  const qc = useQueryClient();
  const { data: matches = [], isLoading } = useQuery({ queryKey: ["matches", tier], queryFn: () => matchesApi.list({ tier: tier || undefined }) });
  const { data: trackedApps = [] } = useQuery({
    queryKey: ["applications"],
    queryFn: () => applicationsApi.list(),
  });
  const trackerMap = new Map<number, ApplicationTracking>(
    trackedApps
      .filter((a): a is ApplicationTracking & { job_id: number } => a.job_id != null)
      .map((a) => [a.job_id, a])
  );
  const bulkNotify = useMutation({ mutationFn: () => matchesApi.notify(Array.from(selected)), onSuccess: () => { setSelected(new Set()); qc.invalidateQueries({ queryKey: ["matches"] }); } });
  const toggle = (id: number) => setSelected((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <select value={tier} onChange={(e) => setTier(e.target.value)} className="bg-[#111] border border-[#2a2a2a] rounded px-2 py-1 text-xs text-[#ccc]">
          <option value="">All tiers</option>
          <option value="strong">Strong</option>
          <option value="borderline">Borderline</option>
        </select>
        {selected.size > 0 && (
          <>
            <button
              className="text-xs px-3 py-1 border border-[#1e1e1e] rounded text-[#666] hover:text-purple-400 hover:border-purple-900/60"
              onClick={() => {
                const toTrack = matches.filter((m) => selected.has(m.id));
                Promise.all(
                  toTrack.map((m) =>
                    applicationsApi.create({
                      job_id: m.job_id,
                      company_name: m.company_name,
                      job_title: m.job_title,
                      url: m.job_url ?? undefined,
                      status: "interested",
                      source: "joblin",
                      score: m.score,
                    })
                  )
                ).then(() => qc.invalidateQueries({ queryKey: ["applications"] })).catch(() => {});
              }}
            >
              ★ Mark Interested
            </button>
            <button
              className="text-xs px-3 py-1 border border-[#1e1e1e] rounded text-[#666] hover:text-blue-400 hover:border-blue-900/60"
              onClick={() => {
                const toTrack = matches.filter((m) => selected.has(m.id));
                Promise.all(
                  toTrack.map((m) =>
                    applicationsApi.create({
                      job_id: m.job_id,
                      company_name: m.company_name,
                      job_title: m.job_title,
                      url: m.job_url ?? undefined,
                      status: "applied",
                      source: "joblin",
                      score: m.score,
                    })
                  )
                ).then(() => qc.invalidateQueries({ queryKey: ["applications"] })).catch(() => {});
              }}
            >
              ✓ Mark Applied
            </button>
            <button
              className="text-xs px-3 py-1 border border-[#1e1e1e] rounded text-[#666] hover:text-red-400 hover:border-red-900/60"
              onClick={() => {
                const toDismiss = matches.filter((m) => selected.has(m.id));
                Promise.all(toDismiss.map((m) => matchesApi.dismiss(m.id)))
                  .then(() => qc.invalidateQueries({ queryKey: ["matches"] }))
                  .catch(() => {});
              }}
            >
              ✕ Dismiss
            </button>
            <button onClick={() => bulkNotify.mutate()} className="text-xs border border-[#4e9eff] rounded px-3 py-1 text-[#4e9eff] bg-[#0e2040]">
              Re-notify {selected.size} selected
            </button>
            <button
              onClick={() => navigate(`/insights?analyze=${Array.from(selected).join(",")}`)}
              className="text-xs border border-[#2a2a2a] rounded px-3 py-1 text-[#888] hover:text-[#ccc]"
            >
              Analyze skills ({selected.size})
            </button>
          </>
        )}
      </div>
      {isLoading && <p className="text-[#555] text-sm">Loading...</p>}
      {matches.map((m) => <MatchRow key={m.id} match={m} selected={selected.has(m.id)} onSelect={() => toggle(m.id)} trackerMap={trackerMap} autoExpand={m.id === expandId} />)}
    </div>
  );
}
