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
        <button onClick={() => runMutation.mutate(true)} disabled={runMutation.isPending}
          className="border border-[#2a2a2a] rounded px-2.5 py-1 text-[11px] text-[#aaa] bg-[#161616] hover:bg-[#1f1f1f]">
          Preview run
        </button>
        <button onClick={() => runMutation.mutate(false)} disabled={runMutation.isPending}
          className="border border-[#4e9eff] rounded px-2.5 py-1 text-[11px] text-[#4e9eff] bg-[#0e2040] hover:bg-[#0d2850]">
          {runMutation.isPending ? "Starting..." : "Run now"}
        </button>
      </div>
    </header>
  );
}
