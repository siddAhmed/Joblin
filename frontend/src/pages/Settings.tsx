import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "@/api/settings";

type Tab = "discord" | "criteria" | "schedule" | "llm" | "presets";

export function Settings() {
  const [tab, setTab] = useState<Tab>("discord");
  const [testJd, setTestJd] = useState("");
  const [testResult, setTestResult] = useState<{ score?: number; reasoning?: string; error?: string } | null>(null);
  const qc = useQueryClient();
  const { data: settings = {} as Record<string, unknown> } = useQuery({ queryKey: ["settings"], queryFn: settingsApi.get });
  const { data: presets = [] } = useQuery({ queryKey: ["presets"], queryFn: settingsApi.listPresets });
  const update = useMutation({ mutationFn: (data: Record<string, unknown>) => settingsApi.update(data), onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }) });
  const applyPreset = useMutation({ mutationFn: (name: string) => settingsApi.applyPreset(name), onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }) });
  const testDiscord = useMutation({ mutationFn: settingsApi.testDiscord });

  const tabs: { key: Tab; label: string }[] = [
    { key: "discord", label: "Discord" },
    { key: "criteria", label: "Criteria" },
    { key: "schedule", label: "Schedule" },
    { key: "llm", label: "LLM Keys" },
    { key: "presets", label: "Presets" },
  ];

  const s = settings as Record<string, unknown>;
  const criteria = (s.criteria as Record<string, unknown>) || {};

  return (
    <div>
      <div className="flex gap-1 mb-5 border-b border-[#1e1e1e]">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 text-xs border-b-2 -mb-px ${tab === t.key ? "border-[#4e9eff] text-[#4e9eff]" : "border-transparent text-[#666]"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "discord" && (
        <div className="space-y-3 max-w-md">
          <label className="block text-xs text-[#888]">Webhook URL</label>
          <input defaultValue={(s.discord_webhook_url as string) || ""}
            onBlur={(e) => update.mutate({ discord_webhook_url: e.target.value })}
            className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]"
            placeholder="https://discord.com/api/webhooks/..." />
          <label className="block text-xs text-[#888] mt-3">Mention type</label>
          <select defaultValue={(s.discord_mention_type as string) || "none"}
            onChange={(e) => update.mutate({ discord_mention_type: e.target.value })}
            className="bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]">
            <option value="none">None</option>
            <option value="user">User</option>
            <option value="role">Role</option>
          </select>
          {["user", "role"].includes(s.discord_mention_type as string) && (
            <><label className="block text-xs text-[#888]">Mention ID</label>
            <input defaultValue={(s.discord_mention_id as string) || ""}
              onBlur={(e) => update.mutate({ discord_mention_id: e.target.value })}
              className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" /></>
          )}
          <button onClick={() => testDiscord.mutate()}
            className="text-xs border border-[#2a2a2a] rounded px-3 py-1.5 text-[#888] hover:text-[#ccc]">
            {testDiscord.isPending ? "Sending..." : "Send test notification"}
          </button>
          {testDiscord.isSuccess && <div className="text-xs text-emerald-500">Sent!</div>}
        </div>
      )}

      {tab === "criteria" && (
        <div className="space-y-3 max-w-lg">
          {["title_allowlist", "title_denylist", "location_allowlist", "location_denylist"].map((field) => (
            <div key={field}>
              <label className="block text-xs text-[#888] mb-1">{field.replace(/_/g, " ")}</label>
              <input defaultValue={(criteria[field] as string) || ""}
                onBlur={(e) => update.mutate({ criteria: { ...criteria, [field]: e.target.value } })}
                className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
            </div>
          ))}
          <label className="block text-xs text-[#888]">Profile description</label>
          <textarea defaultValue={(criteria.profile_description as string) || ""}
            onBlur={(e) => update.mutate({ criteria: { ...criteria, profile_description: e.target.value } })}
            rows={3} className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
          <div className="border-t border-[#1e1e1e] pt-3">
            <label className="block text-xs text-[#888] mb-1">Test against pasted JD</label>
            <textarea value={testJd} onChange={(e) => setTestJd(e.target.value)} rows={4} placeholder="Paste a job description here..."
              className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
            <button onClick={async () => setTestResult(await settingsApi.testCriteria(testJd))}
              className="mt-2 text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040]">Test criteria</button>
            {testResult && (
              <div className="mt-2 text-xs text-[#888]">
                {testResult.error ? <span className="text-red-400">{testResult.error}</span>
                  : <>Score: <span className="font-mono text-[#e5e5e5]">{((testResult.score ?? 0) * 100).toFixed(0)}%</span> -- {testResult.reasoning}</>}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "schedule" && (
        <div className="space-y-3 max-w-sm">
          <label className="block text-xs text-[#888]">Cron expression</label>
          <input defaultValue={(s.schedule_cron as string) || "0 */4 * * *"}
            onBlur={(e) => update.mutate({ schedule_cron: e.target.value })}
            className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] font-mono" />
          <label className="block text-xs text-[#888]">Staleness threshold (hours)</label>
          <input type="number" defaultValue={(s.staleness_threshold_hours as number) ?? 4}
            onBlur={(e) => update.mutate({ staleness_threshold_hours: parseFloat(e.target.value) })}
            className="w-32 bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
          <label className="flex items-center gap-2 text-xs text-[#888] cursor-pointer">
            <input type="checkbox" defaultChecked={!!s.scheduler_enabled} onChange={(e) => update.mutate({ scheduler_enabled: e.target.checked })} />
            Enable scheduler
          </label>
        </div>
      )}

      {tab === "llm" && (
        <div className="space-y-6 max-w-lg">
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-[#888] uppercase tracking-wider">Providers</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-[#888] mb-1">Filter provider</label>
                <select value={(s.llm_filter_provider as string) || "groq"}
                  onChange={(e) => update.mutate({ llm_filter_provider: e.target.value })}
                  className="w-full bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]">
                  <option value="groq">Groq</option>
                  <option value="cerebras">Cerebras</option>
                  <option value="gemini">Gemini</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-[#888] mb-1">Summarize provider</label>
                <select value={(s.llm_summarize_provider as string) || "cerebras"}
                  onChange={(e) => update.mutate({ llm_summarize_provider: e.target.value })}
                  className="w-full bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]">
                  <option value="groq">Groq</option>
                  <option value="cerebras">Cerebras</option>
                  <option value="gemini">Gemini</option>
                </select>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-[#888] uppercase tracking-wider">Groq</h3>
            <div>
              <label className="block text-xs text-[#888] mb-1">API Key</label>
              <input type="password" defaultValue={(s.groq_api_key as string) || ""}
                onBlur={(e) => update.mutate({ groq_api_key: e.target.value })}
                className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-[#888] mb-1">Filter model</label>
                <select value={(s.groq_filter_model as string) || "llama-3.1-8b-instant"}
                  onChange={(e) => update.mutate({ groq_filter_model: e.target.value })}
                  className="w-full bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]">
                  <option value="llama-3.1-8b-instant">llama-3.1-8b-instant — 14.4K RPD, fast</option>
                  <option value="meta-llama/llama-4-scout-17b-16e-instruct">llama-4-scout-17b — 1K RPD, 30K TPM</option>
                  <option value="qwen/qwen3-32b">qwen3-32b — 1K RPD, 60 RPM</option>
                  <option value="openai/gpt-oss-20b">gpt-oss-20b — 1K RPD</option>
                  <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile — 1K RPD, quality</option>
                  <option value="openai/gpt-oss-120b">gpt-oss-120b — 1K RPD, largest</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-[#888] mb-1">Summarize model</label>
                <select value={(s.groq_summarize_model as string) || "llama-3.3-70b-versatile"}
                  onChange={(e) => update.mutate({ groq_summarize_model: e.target.value })}
                  className="w-full bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]">
                  <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile — 1K RPD, quality</option>
                  <option value="openai/gpt-oss-120b">gpt-oss-120b — 1K RPD, largest</option>
                  <option value="meta-llama/llama-4-scout-17b-16e-instruct">llama-4-scout-17b — 1K RPD, 30K TPM</option>
                  <option value="qwen/qwen3-32b">qwen3-32b — 1K RPD, 60 RPM</option>
                  <option value="llama-3.1-8b-instant">llama-3.1-8b-instant — 14.4K RPD, fast</option>
                  <option value="openai/gpt-oss-20b">gpt-oss-20b — 1K RPD</option>
                </select>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-[#888] uppercase tracking-wider">Cerebras</h3>
            <div>
              <label className="block text-xs text-[#888] mb-1">API Key</label>
              <input type="password" defaultValue={(s.cerebras_api_key as string) || ""}
                onBlur={(e) => update.mutate({ cerebras_api_key: e.target.value })}
                className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
            </div>
            <div>
              <label className="block text-xs text-[#888] mb-1">Model</label>
              <select value={(s.cerebras_model as string) || "gpt-oss-120b"}
                onChange={(e) => update.mutate({ cerebras_model: e.target.value })}
                className="w-full bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]">
                <option value="gpt-oss-120b">gpt-oss-120b</option>
                <option value="zai-glm-4.7">zai-glm-4.7</option>
              </select>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-[#888] uppercase tracking-wider">Gemini</h3>
            <div>
              <label className="block text-xs text-[#888] mb-1">API Key</label>
              <input type="password" defaultValue={(s.gemini_api_key as string) || ""}
                onBlur={(e) => update.mutate({ gemini_api_key: e.target.value })}
                className="w-full bg-[#111] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5]" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-[#888] mb-1">Filter model</label>
                <select value={(s.gemini_filter_model as string) || "gemini-2.0-flash-lite"}
                  onChange={(e) => update.mutate({ gemini_filter_model: e.target.value })}
                  className="w-full bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]">
                  <option value="gemini-3.1-flash-lite">gemini-3.1-flash-lite — 15 RPM, 500 RPD</option>
                  <option value="gemini-2.5-flash-lite">gemini-2.5-flash-lite — 10 RPM, 20 RPD</option>
                  <option value="gemini-2.5-flash">gemini-2.5-flash — 5 RPM, 20 RPD</option>
                  <option value="gemini-2.0-flash-lite">gemini-2.0-flash-lite</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-[#888] mb-1">Summarize model</label>
                <select value={(s.gemini_summarize_model as string) || "gemini-2.0-flash-lite"}
                  onChange={(e) => update.mutate({ gemini_summarize_model: e.target.value })}
                  className="w-full bg-[#111] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]">
                  <option value="gemini-3.1-flash-lite">gemini-3.1-flash-lite — 15 RPM, 500 RPD</option>
                  <option value="gemini-2.5-flash">gemini-2.5-flash — 5 RPM, 20 RPD</option>
                  <option value="gemini-2.5-flash-lite">gemini-2.5-flash-lite — 10 RPM, 20 RPD</option>
                  <option value="gemini-2.0-flash-lite">gemini-2.0-flash-lite</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === "presets" && (
        <div className="space-y-3">
          {(presets as Array<{ name: string; description: string }>).map((p) => (
            <div key={p.name} className="border border-[#1e1e1e] rounded-lg p-4 flex items-center justify-between">
              <div>
                <div className="text-sm text-[#e5e5e5] font-medium">{p.name}</div>
                <div className="text-xs text-[#666] mt-0.5">{p.description}</div>
              </div>
              <button onClick={() => applyPreset.mutate(p.name)} className="text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040]">Apply</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
