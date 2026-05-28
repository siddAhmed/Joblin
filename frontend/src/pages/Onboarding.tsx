import { useState } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { settingsApi } from "@/api/settings";
import { companiesApi } from "@/api/companies";
import { runsApi } from "@/api/runs";

type Step = 1 | 2 | 3 | 4;

export function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState<Step>(1);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [companyCsv, setCompanyCsv] = useState("");
  const [testRunId, setTestRunId] = useState<number | null>(null);
  const qc = useQueryClient();

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
      const lines = companyCsv.trim().split("\n").filter(Boolean);
      for (const line of lines) {
        const [name, url] = line.split(",").map((s) => s.trim());
        if (name && url) await companiesApi.add(name, url);
      }
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
              <span className={`text-[10px] ${i + 1 === step ? "text-[#4e9eff]" : "text-[#555]"}`}>{label}</span>
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
              <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://discord.com/api/webhooks/..."
                className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] mb-3" />
              <div className="flex gap-2">
                <button onClick={() => saveWebhook.mutate()} disabled={saveWebhook.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040]">
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
              <div className="space-y-2 mb-4">
                {[
                  { name: "backend-generalist", label: "Backend generalist", desc: "Python, distributed systems, infrastructure" },
                  { name: "python-ml", label: "Python ML engineer", desc: "ML platform, MLOps, data science" },
                  { name: "frontend", label: "Frontend engineer", desc: "React, TypeScript, product UI" },
                ].map((p) => (
                  <button key={p.name} onClick={() => setSelectedPreset(p.name)}
                    className={`w-full text-left border rounded-lg px-4 py-3 transition-colors ${
                      selectedPreset === p.name ? "border-[#4e9eff] bg-[#0e2040]" : "border-[#2a2a2a] bg-[#0a0a0a] hover:bg-[#111]"
                    }`}>
                    <div className="text-sm text-[#e5e5e5]">{p.label}</div>
                    <div className="text-[11px] text-[#666]">{p.desc}</div>
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <button onClick={() => applyPreset.mutate()} disabled={!selectedPreset || applyPreset.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40">
                  {applyPreset.isPending ? "Applying..." : "Apply and continue"}
                </button>
                <button onClick={() => setStep(3)} className="text-xs text-[#555] hover:text-[#888]">Skip</button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 3: Add companies</h2>
              <p className="text-xs text-[#666] mb-3">
                Paste one company per line as: <code className="text-[#4e9eff]">Name, Careers URL</code>
              </p>
              <textarea value={companyCsv} onChange={(e) => setCompanyCsv(e.target.value)}
                rows={6} placeholder={"Stripe, https://stripe.com/jobs\nLinear, https://linear.app/careers"}
                className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] font-mono mb-3" />
              <div className="flex gap-2">
                <button onClick={() => importCompanies.mutate()} disabled={!companyCsv.trim() || importCompanies.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40">
                  {importCompanies.isPending ? "Importing..." : "Import and continue"}
                </button>
              </div>
            </div>
          )}

          {step === 4 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 4: Test run</h2>
              <p className="text-xs text-[#666] mb-4">
                Run a preview scrape to see results before enabling the scheduler. No Discord messages will be sent.
              </p>
              {!testRunId ? (
                <button onClick={() => startTestRun.mutate()} disabled={startTestRun.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040]">
                  {startTestRun.isPending ? "Starting..." : "Start preview run"}
                </button>
              ) : (
                <div className="text-xs text-[#888] mb-4">
                  Preview run #{testRunId} started. Check the Runs screen for results.
                </div>
              )}
              <div className="mt-4">
                <button onClick={finish}
                  className="text-xs border border-[#34d399] rounded px-4 py-2 text-[#34d399] bg-[#0d2018]">
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
