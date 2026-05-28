import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { runsApi } from "@/api/runs";
import type { Run } from "@/api/runs";
import { formatDate } from "@/lib/utils";

export function Runs() {
  const { data: runs = [], isLoading } = useQuery({ queryKey: ["runs"], queryFn: runsApi.list });

  return (
    <div>
      {isLoading && <p className="text-[#555] text-sm">Loading...</p>}
      <table className="w-full text-xs">
        <thead><tr className="border-b border-[#1e1e1e] text-[#555] text-left"><th className="py-2 pr-4">Started</th><th className="py-2 pr-4">Status</th><th className="py-2 pr-4">Found</th><th className="py-2 pr-4">Confirmed</th><th className="py-2">Preview</th></tr></thead>
        <tbody>
          {runs.map((r: Run) => (
            <tr key={r.id} className="border-b border-[#111] hover:bg-[#0f0f0f]">
              <td className="py-2 pr-4"><Link to={`/runs/${r.id}`} className="text-[#4e9eff] hover:underline">{formatDate(r.started_at)}</Link></td>
              <td className="py-2 pr-4"><span className={r.status === "completed" ? "text-emerald-500" : r.status === "running" ? "text-yellow-400" : "text-red-400"}>{r.status}</span></td>
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
