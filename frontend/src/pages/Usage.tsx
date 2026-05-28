import { useQuery } from "@tanstack/react-query";
import { usageApi } from "@/api/usage";
import type { ProviderStats } from "@/api/usage";

const PROVIDER_LABELS: Record<string, { name: string; dashboard: string }> = {
  groq: { name: "Groq", dashboard: "https://console.groq.com/usage" },
  cerebras: { name: "Cerebras", dashboard: "https://cloud.cerebras.ai" },
  gemini: { name: "Gemini", dashboard: "https://aistudio.google.com/app/usage" },
};

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function ProviderCard({ provider, stats }: { provider: string; stats: ProviderStats }) {
  const label = PROVIDER_LABELS[provider];
  const totalCalls = stats.filter_calls + stats.summarize_calls;

  return (
    <div className="border border-[#1e1e1e] rounded-lg p-4 bg-[#0a0a0a]">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-[#e5e5e5]">{label.name}</span>
        <a
          href={label.dashboard}
          target="_blank"
          rel="noreferrer"
          className="text-[10px] text-[#4e9eff] hover:underline"
        >
          Live quota &rsaquo;
        </a>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <div>
          <div className="text-[10px] text-[#555] mb-1">All time</div>
          <div className="font-mono text-base text-[#e5e5e5]">{fmt(stats.total_tokens_all_time)}</div>
          <div className="text-[10px] text-[#444]">tokens</div>
        </div>
        <div>
          <div className="text-[10px] text-[#555] mb-1">Last 7 days</div>
          <div className="font-mono text-base text-[#e5e5e5]">{fmt(stats.total_tokens_7d)}</div>
          <div className="text-[10px] text-[#444]">tokens</div>
        </div>
        <div>
          <div className="text-[10px] text-[#555] mb-1">Last 30 days</div>
          <div className="font-mono text-base text-[#e5e5e5]">{fmt(stats.total_tokens_30d)}</div>
          <div className="text-[10px] text-[#444]">tokens</div>
        </div>
      </div>

      <div className="border-t border-[#1e1e1e] pt-3 grid grid-cols-3 gap-3 text-[11px] text-[#666]">
        <div>
          <span className="block text-[#888]">{stats.filter_calls}</span>
          filter calls
        </div>
        <div>
          <span className="block text-[#888]">{stats.summarize_calls}</span>
          summarize calls
        </div>
        <div>
          <span className="block text-[#888]">{totalCalls}</span>
          total calls
        </div>
      </div>

      {totalCalls > 0 && (
        <div className="mt-3 text-[10px] text-[#444]">
          avg {fmt(Math.round(stats.total_tokens_all_time / totalCalls))} tokens/call
        </div>
      )}
    </div>
  );
}

export function Usage() {
  const { data, isLoading } = useQuery({
    queryKey: ["usage"],
    queryFn: usageApi.get,
    refetchInterval: 30_000,
  });

  if (isLoading) return <p className="text-[#555] text-sm">Loading...</p>;
  if (!data) return null;

  const hasAnyData = Object.values(data.providers).some((p) => p.total_tokens_all_time > 0);

  return (
    <div className="max-w-3xl">
      {!hasAnyData && (
        <div className="border border-[#1e1e1e] rounded-lg p-4 bg-[#0a0a0a] text-[#555] text-sm mb-6">
          No token usage recorded yet. Run a scrape to start tracking.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {(["groq", "cerebras", "gemini"] as const).map((p) => (
          <ProviderCard key={p} provider={p} stats={data.providers[p]} />
        ))}
      </div>

      {data.recent_runs.length > 0 && (
        <>
          <h3 className="text-xs font-semibold text-[#888] uppercase tracking-wider mb-3">Per-run breakdown</h3>
          <div className="border border-[#1e1e1e] rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#1e1e1e] text-[#555]">
                  <th className="px-4 py-2 text-left">Run</th>
                  <th className="px-4 py-2 text-right">Groq</th>
                  <th className="px-4 py-2 text-right">Cerebras</th>
                  <th className="px-4 py-2 text-right">Gemini</th>
                  <th className="px-4 py-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_runs.map((row) => (
                  <tr key={row.run_id} className="border-b border-[#111] hover:bg-[#111]">
                    <td className="px-4 py-2 text-[#4e9eff]">
                      <a href={`/runs/${row.run_id}`}>#{row.run_id}</a>
                    </td>
                    <td className="px-4 py-2 text-right text-[#888] font-mono">{fmt(row.groq)}</td>
                    <td className="px-4 py-2 text-right text-[#888] font-mono">{fmt(row.cerebras)}</td>
                    <td className="px-4 py-2 text-right text-[#888] font-mono">{fmt(row.gemini)}</td>
                    <td className="px-4 py-2 text-right text-[#e5e5e5] font-mono">
                      {fmt(row.groq + row.cerebras + row.gemini)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
