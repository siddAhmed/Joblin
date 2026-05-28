import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { jobsApi } from "@/api/jobs";
import type { Job } from "@/api/jobs";
import { formatDate } from "@/lib/utils";

function JobRow({ job }: { job: Job }) {
  const [expanded, setExpanded] = useState(false);
  const { data: detail } = useQuery({ queryKey: ["job", job.id], queryFn: () => jobsApi.get(job.id), enabled: expanded });
  const qc = useQueryClient();
  const dismiss = useMutation({ mutationFn: () => jobsApi.dismiss(job.id), onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }) });

  return (
    <div className="border border-[#1e1e1e] rounded-lg mb-1.5 overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-[#111]" onClick={() => setExpanded(!expanded)}>
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
            <button onClick={() => dismiss.mutate()} disabled={dismiss.isPending}
              className="text-[11px] border border-[#2a2a2a] rounded px-2 py-1 text-[#888] hover:text-[#ccc] disabled:opacity-40">Not interested</button>
            <a href={detail.url} target="_blank" rel="noreferrer" className="text-[11px] border border-[#2a2a2a] rounded px-2 py-1 text-[#888] hover:text-[#ccc]">Open</a>
          </div>
        </div>
      )}
    </div>
  );
}

export function Jobs() {
  const [search, setSearch] = useState("");
  const { data: jobs = [], isLoading } = useQuery({ queryKey: ["jobs", search], queryFn: () => jobsApi.list({ search: search || undefined }) });

  return (
    <div>
      <div className="mb-4">
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search job titles..."
          className="bg-[#111] border border-[#2a2a2a] rounded px-3 py-1.5 text-xs text-[#ccc] w-64" />
      </div>
      {isLoading && <p className="text-[#555] text-sm">Loading...</p>}
      {jobs.map((j) => <JobRow key={j.id} job={j} />)}
    </div>
  );
}
