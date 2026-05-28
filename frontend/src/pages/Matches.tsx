import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { matchesApi } from "@/api/matches";
import type { Match } from "@/api/matches";
import { jobsApi } from "@/api/jobs";
import { formatScore } from "@/lib/utils";

function MatchRow({ match, selected, onSelect }: { match: Match; selected: boolean; onSelect: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const { data: job } = useQuery({ queryKey: ["job", match.job_id], queryFn: () => jobsApi.get(match.job_id), enabled: expanded });
  const qc = useQueryClient();
  const applyUrl = match.job_url || job?.url;
  const dismiss = useMutation({ mutationFn: () => jobsApi.dismiss(match.job_id), onSuccess: () => qc.invalidateQueries({ queryKey: ["matches"] }) });

  const isStrong = match.tier === "strong";
  return (
    <div className="border border-[#1e1e1e] rounded-lg mb-2 overflow-hidden">
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
            <button onClick={() => dismiss.mutate()} className="text-[11px] border border-[#2a2a2a] rounded px-2 py-1 text-[#888] hover:text-[#ccc]">Not interested</button>
            {applyUrl && <a href={applyUrl} target="_blank" rel="noreferrer" className="text-[11px] border border-[#4e9eff] rounded px-2 py-1 text-[#4e9eff] hover:bg-[#0e2040]">Apply</a>}
          </div>
        </div>
      )}
    </div>
  );
}

export function Matches() {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [tier, setTier] = useState("");
  const qc = useQueryClient();
  const { data: matches = [], isLoading } = useQuery({ queryKey: ["matches", tier], queryFn: () => matchesApi.list({ tier: tier || undefined }) });
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
          <button onClick={() => bulkNotify.mutate()} className="text-xs border border-[#4e9eff] rounded px-3 py-1 text-[#4e9eff] bg-[#0e2040]">
            Re-notify {selected.size} selected
          </button>
        )}
      </div>
      {isLoading && <p className="text-[#555] text-sm">Loading...</p>}
      {matches.map((m) => <MatchRow key={m.id} match={m} selected={selected.has(m.id)} onSelect={() => toggle(m.id)} />)}
    </div>
  );
}
