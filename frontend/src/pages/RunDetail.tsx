import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { runsApi } from "@/api/runs";
import { useSseRun } from "@/hooks/useSseRun";

export function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const runId = id ? parseInt(id) : null;
  const { events, done } = useSseRun(runId);
  const { data: run } = useQuery({ queryKey: ["run", runId], queryFn: () => runsApi.get(runId!), enabled: !!runId });

  return (
    <div>
      <h2 className="text-sm font-semibold mb-4">Run #{runId}</h2>
      {run && <div className="text-xs text-[#666] mb-4">Status: <span className="text-[#e5e5e5]">{run.status}</span></div>}
      <div className="border border-[#1e1e1e] rounded-lg p-4 bg-[#0a0a0a] font-mono text-xs space-y-1 max-h-96 overflow-auto">
        {events.length === 0 && !done && <div className="text-[#555]">Waiting for events...</div>}
        {events.map((e, i) => (
          <div key={i} className="text-[#888]">
            <span className="text-[#4e9eff]">{e.type}</span>{" "}{JSON.stringify(e.data)}
          </div>
        ))}
        {done && <div className="text-emerald-500">Run complete.</div>}
      </div>
    </div>
  );
}
