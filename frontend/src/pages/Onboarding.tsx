import { useState } from "react";
import { useQueryClient, useMutation, useQuery } from "@tanstack/react-query";
import { settingsApi } from "@/api/settings";
import { companiesApi } from "@/api/companies";
import type { DefaultCompany } from "@/api/companies";
import { runsApi } from "@/api/runs";

type Step = 1 | 2 | 3 | 4;

interface Preset {
  name: string;
  label: string;
  description: string;
  group: "experienced" | "intern";
  criteria: Record<string, unknown>;
}

export function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState<Step>(1);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [testRunId, setTestRunId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [deselected, setDeselected] = useState<Set<string>>(new Set());
  const [stage, setStage] = useState<"experienced" | "intern" | null>(null);
  const qc = useQueryClient();

  const { data: defaultCompanies = [] } = useQuery<DefaultCompany[]>({
    queryKey: ["companies-defaults"],
    queryFn: companiesApi.defaults,
    enabled: step === 3,
  });

  const { data: presets = [], isPending: presetsLoading, isError: presetsError } = useQuery<Preset[]>({
    queryKey: ["presets"],
    queryFn: settingsApi.listPresets,
    enabled: step === 2,
  });

  const filteredCompanies = defaultCompanies.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  const selectedCount = defaultCompanies.length - deselected.size;

  const toggleCompany = (name: string) => {
    setDeselected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const selectAll = () => setDeselected(new Set());
  const deselectAll = () =>
    setDeselected(new Set(defaultCompanies.map((c) => c.name)));

  const saveWebhook = useMutation({
    mutationFn: () => settingsApi.update({ discord_webhook_url: webhookUrl }),
    onSuccess: () => setStep(2),
  });

  const applyPreset = useMutation({
    mutationFn: () => settingsApi.applyPreset(selectedPreset!),
    onSuccess: () => setStep(3),
  });

  const importCompanies = useMutation({
    mutationFn: async () => {
      const selected = defaultCompanies.filter((c) => !deselected.has(c.name));
      await companiesApi.bulk(selected);
    },
    onSuccess: () => setStep(4),
  });

  const startTestRun = useMutation({
    mutationFn: () => runsApi.start({ preview: true }),
    onSuccess: (data) => setTestRunId(data.id),
  });

  const finish = () => {
    qc.invalidateQueries({ queryKey: ["companies"] });
    qc.invalidateQueries({ queryKey: ["onboarding-status"] });
    onComplete();
  };

  const stepLabels = ["Discord", "Criteria", "Companies", "Test run"];

  return (
    <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[#e5e5e5]">
            Welcome to Job<span className="text-[#4e9eff]">lin</span>
          </h1>
          <p className="text-sm text-[#666] mt-1">Let's get you set up in 4 steps.</p>
        </div>

        <div className="flex gap-1 mb-6">
          {stepLabels.map((label, i) => (
            <div key={label} className="flex-1 text-center">
              <div className={`h-1 rounded mb-1 ${i + 1 <= step ? "bg-[#4e9eff]" : "bg-[#222]"}`} />
              <span className={`text-[10px] ${i + 1 === step ? "text-[#4e9eff]" : "text-[#555]"}`}>
                {label}
              </span>
            </div>
          ))}
        </div>

        <div className="border border-[#2a2a2a] rounded-xl p-6 bg-[#111]">
          {step === 1 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 1: Discord webhook</h2>
              <p className="text-xs text-[#666] mb-3">
                Create a webhook in your Discord server settings and paste the URL below.
                Joblin will notify you when strong matches are found.
              </p>
              <input
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://discord.com/api/webhooks/..."
                className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] mb-3"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => saveWebhook.mutate()}
                  disabled={saveWebhook.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040]"
                >
                  {saveWebhook.isPending ? "Saving..." : "Save and continue"}
                </button>
                <button onClick={() => setStep(2)} className="text-xs text-[#555] hover:text-[#888]">
                  Skip for now
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 2: Choose a job criteria preset</h2>

              {stage === null ? (
                <>
                  <p className="text-xs text-[#666] mb-3">What stage are you at?</p>
                  <div className="space-y-2 mb-4">
                    {(
                      [
                        { value: "experienced", label: "💼 Experienced", desc: "Senior, staff, or lead-level roles" },
                        { value: "intern", label: "🎓 Intern / New Grad", desc: "Internships, co-ops, entry-level & new grad roles" },
                      ] as const
                    ).map((s) => (
                      <button
                        key={s.value}
                        onClick={() => setStage(s.value)}
                        className="w-full text-left border border-[#2a2a2a] rounded-lg px-4 py-3 bg-[#0a0a0a] hover:bg-[#111] transition-colors"
                      >
                        <div className="text-sm text-[#e5e5e5]">{s.label}</div>
                        <div className="text-[11px] text-[#666]">{s.desc}</div>
                      </button>
                    ))}
                  </div>
                  <button onClick={() => { setStage(null); setSelectedPreset(null); setStep(3); }} className="text-xs text-[#555] hover:text-[#888]">
                    Skip
                  </button>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-2 mb-3">
                    <button
                      onClick={() => { setStage(null); setSelectedPreset(null); }}
                      className="text-xs text-[#4e9eff] hover:underline"
                    >
                      ← Back
                    </button>
                    <span className="text-xs text-[#555]">
                      {stage === "experienced" ? "Experienced" : "Intern / New Grad"}
                    </span>
                  </div>
                  <div className="space-y-2 mb-4">
                    {presetsLoading ? (
                      <p className="text-xs text-[#555] py-4 text-center">Loading presets...</p>
                    ) : presetsError ? (
                      <p className="text-xs text-[#f87171] py-4 text-center">Failed to load presets. Please try again.</p>
                    ) : presets.filter((p) => p.group === stage).length === 0 ? (
                      <p className="text-xs text-[#555] py-4 text-center">No presets available.</p>
                    ) : (
                      presets
                        .filter((p) => p.group === stage)
                        .map((p) => (
                          <button
                            key={p.name}
                            onClick={() => setSelectedPreset(p.name)}
                            className={`w-full text-left border rounded-lg px-4 py-3 transition-colors ${
                              selectedPreset === p.name
                                ? "border-[#4e9eff] bg-[#0e2040]"
                                : "border-[#2a2a2a] bg-[#0a0a0a] hover:bg-[#111]"
                            }`}
                          >
                            <div className="text-sm text-[#e5e5e5]">{p.label}</div>
                            <div className="text-[11px] text-[#666]">{p.description}</div>
                          </button>
                        ))
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => applyPreset.mutate()}
                      disabled={!selectedPreset || applyPreset.isPending}
                      className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                    >
                      {applyPreset.isPending ? "Applying..." : "Apply and continue"}
                    </button>
                    <button onClick={() => { setStage(null); setSelectedPreset(null); setStep(3); }} className="text-xs text-[#555] hover:text-[#888]">
                      Skip
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 className="text-sm font-semibold mb-1">Step 3: Choose companies to track</h2>
              <p className="text-xs text-[#666] mb-3">
                All companies are pre-selected. Deselect any you don't want.
              </p>

              {/* Controls */}
              <div className="flex items-center gap-2 mb-2">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filter companies..."
                  className="flex-1 bg-[#0d0d0d] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]"
                />
                <span className="text-[10px] text-[#555]">{selectedCount} selected</span>
                <button onClick={selectAll} className="text-[10px] text-[#4e9eff] hover:underline">
                  All
                </button>
                <button onClick={deselectAll} className="text-[10px] text-[#555] hover:underline">
                  None
                </button>
              </div>

              {/* Scrollable company list */}
              <div className="h-64 overflow-y-auto border border-[#1e1e1e] rounded bg-[#0a0a0a] p-2 mb-3">
                {defaultCompanies.length === 0 ? (
                  <p className="text-[#555] text-xs text-center mt-8">Loading...</p>
                ) : filteredCompanies.length === 0 ? (
                  <p className="text-[#555] text-xs text-center mt-8">No matches</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {filteredCompanies.map((c) => {
                      const selected = !deselected.has(c.name);
                      return (
                        <button
                          key={c.name}
                          onClick={() => toggleCompany(c.name)}
                          className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                            selected
                              ? "border-[#4e9eff] bg-[#0e2040] text-[#4e9eff]"
                              : "border-[#2a2a2a] bg-transparent text-[#555]"
                          }`}
                        >
                          {c.name}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => importCompanies.mutate()}
                  disabled={selectedCount === 0 || importCompanies.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                >
                  {importCompanies.isPending
                    ? "Adding companies..."
                    : `Add ${selectedCount} companies and continue`}
                </button>
                <button onClick={() => setStep(4)} className="text-xs text-[#555] hover:text-[#888]">
                  Skip
                </button>
              </div>
            </div>
          )}

          {step === 4 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 4: Test run</h2>
              <p className="text-xs text-[#666] mb-4">
                Run a preview scrape to see results before enabling the scheduler. No Discord
                messages will be sent.
              </p>
              {!testRunId ? (
                <button
                  onClick={() => startTestRun.mutate()}
                  disabled={startTestRun.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040]"
                >
                  {startTestRun.isPending ? "Starting..." : "Start preview run"}
                </button>
              ) : (
                <div className="text-xs text-[#888] mb-4">
                  Preview run #{testRunId} started. Check the Runs screen for results.
                </div>
              )}
              <div className="mt-4">
                <button
                  onClick={finish}
                  className="text-xs border border-[#34d399] rounded px-4 py-2 text-[#34d399] bg-[#0d2018]"
                >
                  Finish setup and go to Dashboard
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
