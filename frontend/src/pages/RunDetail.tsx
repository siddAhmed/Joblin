import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { runsApi } from "@/api/runs";
import { useSseRun } from "@/hooks/useSseRun";

export function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const runId = id ? parseInt(id) : null;
  const queryClient = useQueryClient();
  const { events, done } = useSseRun(runId);
  const { data: run, refetch } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => runsApi.get(runId!),
    enabled: !!runId,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 3000 : false),
  });

  const cancelMutation = useMutation({
    mutationFn: () => runsApi.cancel(runId!),
    onSuccess: () => {
      refetch();
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  const isRunning = run?.status === "running";

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold">Run #{runId}</h2>
        {isRunning && (
          <button
            onClick={() => cancelMutation.mutate()}
            disabled={cancelMutation.isPending}
            className="px-3 py-1 text-xs rounded border border-red-800 text-red-400 hover:bg-red-950 disabled:opacity-50 transition-colors"
          >
            {cancelMutation.isPending ? "Stopping..." : "Stop run"}
          </button>
        )}
      </div>
      {run && (
        <div className="text-xs text-[#666] mb-4">
          Status:{" "}
          <span className={
            run.status === "running" ? "text-yellow-400" :
            run.status === "completed" ? "text-emerald-400" :
            run.status === "cancelled" ? "text-orange-400" :
            "text-red-400"
          }>
            {run.status}
          </span>
        </div>
      )}
      <div className="border border-[#1e1e1e] rounded-lg p-4 bg-[#0a0a0a] font-mono text-xs space-y-1 max-h-96 overflow-auto">
        {events.length === 0 && !done && <div className="text-[#555]">Waiting for events...</div>}
        {events.map((e, i) => (
          <div key={i} className="text-[#888]">
            <span className="text-[#4e9eff]">{e.type}</span>{" "}{JSON.stringify(e.data)}
          </div>
        ))}
        {done && (
          <>
            <div className={run?.status === "cancelled" ? "text-orange-400" : "text-emerald-500"}>
              {run?.status === "cancelled" ? "Run cancelled." : "Run complete."}
            </div>
            {events.find((e) => e.type === "run_done")?.data?.seeding && (
              <div className="text-yellow-600 mt-1">Seeding run: jobs stored, Discord notifications skipped.</div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
