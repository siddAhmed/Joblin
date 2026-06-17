import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { statsApi } from "@/api/stats";
import { matchesApi } from "@/api/matches";
import type { Match } from "@/api/matches";
import { formatDate, formatScore } from "@/lib/utils";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border border-[#1e1e1e] rounded-lg p-3 bg-[#111]">
      <div className="font-mono text-xl font-bold text-[#e5e5e5]">{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-[#555] mt-0.5">{label}</div>
    </div>
  );
}

function MatchRow({ match }: { match: Match }) {
  const isStrong = match.tier === "strong";
  return (
    <Link to="/matches" className="flex items-center gap-3 px-4 py-2.5 border border-[#1e1e1e] rounded-lg mb-2 hover:bg-[#111] block">
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
      <div className="text-right shrink-0">
        <div className="font-mono text-xs text-[#888]">{formatScore(match.score)}</div>
        <div className="text-[10px] text-[#444] font-mono">{formatDate(match.created_at)}</div>
      </div>
    </Link>
  );
}

export function Dashboard() {
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: statsApi.get });
  const { data: matches } = useQuery({ queryKey: ["matches", "recent"], queryFn: () => matchesApi.list({ limit: 10 }) });

  return (
    <div>
      {stats && stats.quarantine_count > 0 && (
        <div className="mb-4 border border-orange-900 bg-orange-950/30 rounded-lg px-4 py-2 text-xs text-orange-400 flex items-center gap-2">
          <span>{stats.quarantine_count} {stats.quarantine_count === 1 ? "company" : "companies"} quarantined.</span>
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
      {matches?.length === 0 && <p className="text-[#555] text-sm">No matches yet. Add companies and run a scrape.</p>}
      <div>{matches?.map((m) => <MatchRow key={m.id} match={m} />)}</div>
    </div>
  );
}
