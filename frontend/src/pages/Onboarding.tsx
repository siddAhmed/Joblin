import { useState } from "react";
import { useQueryClient, useMutation, useQuery } from "@tanstack/react-query";
import { settingsApi } from "@/api/settings";
import type { ValidateKeysResponse } from "@/api/settings";
import { companiesApi } from "@/api/companies";
import type { DefaultCompany } from "@/api/companies";
import { runsApi } from "@/api/runs";
import { TagChips } from "@/components/TagChips";

type Step = 1 | 2 | 3 | 4 | 5;
type KeyState = { value: string; status: "idle" | "loading" | "valid" | "error"; error: string | null };

interface Preset {
  name: string;
  label: string;
  description: string;
  group: "experienced" | "intern";
  criteria: Record<string, unknown>;
}

interface CriteriaValues {
  title_allowlist: string;
  title_denylist: string;
  location_allowlist: string;
  location_denylist: string;
  seniority_allowlist: string[];
  exclusion_keywords: string[];
  profile_description: string;
}

const SENIORITY_SUGGESTIONS = [
  "Senior", "Staff", "Principal", "Lead", "Mid",
  "Junior", "Intern", "New Grad", "Associate", "Entry Level",
];

function toCriteriaValues(raw: Record<string, unknown>): CriteriaValues {
  return {
    title_allowlist: (raw.title_allowlist as string) ?? "",
    title_denylist: (raw.title_denylist as string) ?? "",
    location_allowlist: (raw.location_allowlist as string) ?? "",
    location_denylist: (raw.location_denylist as string) ?? "",
    seniority_allowlist: Array.isArray(raw.seniority_allowlist) ? (raw.seniority_allowlist as string[]) : [],
    exclusion_keywords: Array.isArray(raw.exclusion_keywords) ? (raw.exclusion_keywords as string[]) : [],
    profile_description: (raw.profile_description as string) ?? "",
  };
}

export function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState<Step>(1);

  // Step 1 state
  const [groq, setGroq] = useState<KeyState>({ value: "", status: "idle", error: null });
  const [cerebras, setCerebras] = useState<KeyState>({ value: "", status: "idle", error: null });
  const [gemini, setGemini] = useState<KeyState>({ value: "", status: "idle", error: null });

  // Step 2+ state
  const [webhookUrl, setWebhookUrl] = useState("");
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [testRunId, setTestRunId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [deselected, setDeselected] = useState<Set<string>>(new Set());
  const [stage, setStage] = useState<"experienced" | "intern" | null>(null);
  const [criteria, setCriteria] = useState<CriteriaValues | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const qc = useQueryClient();

  const { data: defaultCompanies = [] } = useQuery<DefaultCompany[]>({
    queryKey: ["companies-defaults"],
    queryFn: companiesApi.defaults,
    enabled: step === 4,
  });

  const { data: presets = [], isPending: presetsLoading, isError: presetsError } = useQuery<Preset[]>({
    queryKey: ["presets"],
    queryFn: settingsApi.listPresets,
    enabled: step === 3,
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

  // Step 1 mutations
  const validateKeysMutation = useMutation({
    mutationFn: (keys: { groq_api_key?: string; cerebras_api_key?: string; gemini_api_key?: string }) =>
      settingsApi.validateKeys(keys),
    onMutate: (keys) => {
      if (keys.groq_api_key) setGroq((g) => ({ ...g, status: "loading" }));
      if (keys.cerebras_api_key) setCerebras((c) => ({ ...c, status: "loading" }));
      if (keys.gemini_api_key) setGemini((g) => ({ ...g, status: "loading" }));
    },
    onSuccess: (data: ValidateKeysResponse) => {
      if (data.groq) setGroq((g) => ({ ...g, status: data.groq!.valid ? "valid" : "error", error: data.groq!.error }));
      if (data.cerebras) setCerebras((c) => ({ ...c, status: data.cerebras!.valid ? "valid" : "error", error: data.cerebras!.error }));
      if (data.gemini) setGemini((g) => ({ ...g, status: data.gemini!.valid ? "valid" : "error", error: data.gemini!.error }));
    },
  });

  const saveKeys = useMutation({
    mutationFn: () => {
      const payload: Record<string, string> = {
        groq_api_key: groq.value,
        cerebras_api_key: cerebras.value,
      };
      if (gemini.value) payload.gemini_api_key = gemini.value;
      return settingsApi.update(payload);
    },
    onSuccess: () => setStep(2),
  });

  // Step 2 mutations
  const saveWebhook = useMutation({
    mutationFn: () => settingsApi.update({ discord_webhook_url: webhookUrl }),
    onSuccess: () => setStep(3),
  });

  const saveCriteria = useMutation({
    mutationFn: (c: CriteriaValues) => settingsApi.update({ criteria: c }),
    onSuccess: () => setStep(4),
  });

  const importCompanies = useMutation({
    mutationFn: async () => {
      const selected = defaultCompanies.filter((c) => !deselected.has(c.name));
      await companiesApi.bulk(selected);
    },
    onSuccess: () => setStep(5),
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

  const stepLabels = ["API Keys", "Discord", "Criteria", "Companies", "Test run"];

  return (
    <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[#e5e5e5]">
            Welcome to Job<span className="text-[#4e9eff]">lin</span>
          </h1>
          <p className="text-sm text-[#666] mt-1">Let's get you set up in 5 steps.</p>
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
              <h2 className="text-sm font-semibold mb-2">Step 1: Connect your AI providers</h2>
              <p className="text-xs text-[#666] mb-4">
                Joblin uses Groq and Cerebras to filter and summarize job listings. Paste your API keys below.
              </p>

              {/* Groq card */}
              <div className="border border-[#2a2a2a] rounded-lg p-4 mb-3 bg-[#0a0a0a]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[#e5e5e5]">
                    Groq
                    <span className="text-[#f87171] text-[10px] ml-2">required</span>
                  </span>
                  <a
                    href="https://console.groq.com/keys"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] text-[#4e9eff] hover:underline"
                  >
                    Get your key →
                  </a>
                </div>
                <input
                  type="password"
                  value={groq.value}
                  onChange={(e) => setGroq({ value: e.target.value, status: "idle", error: null })}
                  placeholder="gsk_..."
                  className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                />
                {groq.status === "valid" && (
                  <p className="text-[10px] text-[#34d399] mt-1">Valid</p>
                )}
                {groq.status === "error" && (
                  <p className="text-[10px] text-[#f87171] mt-1">{groq.error}</p>
                )}
              </div>

              {/* Cerebras card */}
              <div className="border border-[#2a2a2a] rounded-lg p-4 mb-3 bg-[#0a0a0a]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[#e5e5e5]">
                    Cerebras
                    <span className="text-[#f87171] text-[10px] ml-2">required</span>
                  </span>
                  <a
                    href="https://cloud.cerebras.ai/"
                    target="_blank"
                    rel="noopener noreferrer"
                    title="API Keys in the sidebar"
                    className="text-[10px] text-[#4e9eff] hover:underline"
                  >
                    Get your key →
                  </a>
                </div>
                <input
                  type="password"
                  value={cerebras.value}
                  onChange={(e) => setCerebras({ value: e.target.value, status: "idle", error: null })}
                  placeholder="csk_..."
                  className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                />
                {cerebras.status === "valid" && (
                  <p className="text-[10px] text-[#34d399] mt-1">Valid</p>
                )}
                {cerebras.status === "error" && (
                  <p className="text-[10px] text-[#f87171] mt-1">{cerebras.error}</p>
                )}
              </div>

              {/* Gemini card */}
              <div className="border border-[#2a2a2a] rounded-lg p-4 mb-4 bg-[#0a0a0a]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[#e5e5e5]">
                    Gemini
                    <span className="text-[#555] text-[10px] ml-2">optional</span>
                  </span>
                  <a
                    href="https://aistudio.google.com/apikey"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] text-[#4e9eff] hover:underline"
                  >
                    Get your key →
                  </a>
                </div>
                <input
                  type="password"
                  value={gemini.value}
                  onChange={(e) => setGemini({ value: e.target.value, status: "idle", error: null })}
                  placeholder="AIza..."
                  className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                />
                {gemini.status === "valid" && (
                  <p className="text-[10px] text-[#34d399] mt-1">Valid</p>
                )}
                {gemini.status === "error" && (
                  <p className="text-[10px] text-[#f87171] mt-1">{gemini.error}</p>
                )}
              </div>

              <div className="flex gap-2 items-center">
                <button
                  onClick={() => {
                    const keys: { groq_api_key?: string; cerebras_api_key?: string; gemini_api_key?: string } = {};
                    if (groq.value) keys.groq_api_key = groq.value;
                    if (cerebras.value) keys.cerebras_api_key = cerebras.value;
                    if (gemini.value) keys.gemini_api_key = gemini.value;
                    validateKeysMutation.mutate(keys);
                  }}
                  disabled={validateKeysMutation.isPending || (!groq.value && !cerebras.value && !gemini.value)}
                  className="text-xs border border-[#2a2a2a] rounded px-4 py-2 text-[#888] bg-[#0a0a0a] disabled:opacity-40"
                >
                  {validateKeysMutation.isPending ? "Testing..." : "Test keys"}
                </button>
                <button
                  onClick={() => saveKeys.mutate()}
                  disabled={groq.status !== "valid" || cerebras.status !== "valid" || saveKeys.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                >
                  {saveKeys.isPending ? "Saving..." : "Next"}
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 2: Discord webhook</h2>
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
                <button onClick={() => setStep(3)} className="text-xs text-[#555] hover:text-[#888]">
                  Skip for now
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 3: Choose a job criteria preset</h2>

              {editorOpen && criteria ? (
                /* Sub-step C: Criteria editor */
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <button
                      onClick={() => { setEditorOpen(false); setShowAdvanced(false); }}
                      className="text-xs text-[#4e9eff] hover:underline"
                    >
                      ← Back
                    </button>
                    <span className="text-xs text-[#555]">
                      {presets.find((p) => p.name === selectedPreset)?.label}
                    </span>
                  </div>

                  <div className="bg-[#0e2040] border border-[#1e3a5f] rounded-lg p-3 mb-4">
                    <div className="text-xs text-[#90c4ff] font-semibold mb-2">⚡ How Joblin filters jobs — two layers</div>
                    <div className="space-y-2">
                      <div className="bg-[#0a1a30] rounded p-2">
                        <div className="text-[10px] text-[#f59e0b] font-semibold mb-1">Layer 1 — Heuristic filters (title, seniority, location, exclusions)</div>
                        <div className="text-[10px] text-[#7aa3cc] leading-relaxed">Fast, non-AI rules. A job that fails is <span className="text-[#fbbf24]">dropped immediately</span> — the AI never sees it. If your patterns are too strict, you'll miss good matches with no warning.</div>
                      </div>
                      <div className="bg-[#0a1a30] rounded p-2">
                        <div className="text-[10px] text-[#34d399] font-semibold mb-1">Layer 2 — AI scoring (profile description)</div>
                        <div className="text-[10px] text-[#7aa3cc] leading-relaxed">Jobs that pass heuristics are scored by AI using your profile. Contextual and forgiving — a richer, more specific profile gives better, more relevant scores.</div>
                      </div>
                    </div>
                  </div>

                  <div className="mb-3">
                    <div className="flex items-baseline gap-2 mb-1">
                      <label className="text-[10px] text-[#888] uppercase tracking-wider">Title must match</label>
                      <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                    </div>
                    <input
                      value={criteria.title_allowlist}
                      onChange={(e) => setCriteria({ ...criteria, title_allowlist: e.target.value })}
                      className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                    />
                    <p className="text-[9px] text-[#555] mt-1 leading-relaxed">Regex patterns, pipe-separated. Jobs whose title doesn't match any of these are discarded before AI scoring. Keep patterns broad — <span className="text-[#888]">"react" alone would miss "Frontend Engineer at Stripe"</span>.</p>
                  </div>

                  <div className="mb-3">
                    <div className="flex items-baseline gap-2 mb-1">
                      <label className="text-[10px] text-[#888] uppercase tracking-wider">Title must NOT match</label>
                      <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                    </div>
                    <input
                      value={criteria.title_denylist}
                      onChange={(e) => setCriteria({ ...criteria, title_denylist: e.target.value })}
                      className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                    />
                    <p className="text-[9px] text-[#555] mt-1 leading-relaxed">Jobs whose title matches any of these are discarded. Be precise — <span className="text-[#888]">"design" would also block "design systems engineer"</span>.</p>
                  </div>

                  <div className="mb-3">
                    <div className="flex items-baseline gap-2 mb-2">
                      <label className="text-[10px] text-[#888] uppercase tracking-wider">Seniority levels</label>
                      <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                    </div>
                    <TagChips
                      value={criteria.seniority_allowlist}
                      onChange={(v) => setCriteria({ ...criteria, seniority_allowlist: v })}
                      suggestions={SENIORITY_SUGGESTIONS}
                      color="blue"
                    />
                    <p className="text-[9px] text-[#555] mt-1 leading-relaxed">Inferred from the job title. <span className="text-[#888]">If seniority can't be inferred, the job passes through.</span> Leave all unchecked to skip this filter entirely.</p>
                  </div>

                  <div className="mb-3">
                    <div className="flex items-baseline gap-2 mb-1">
                      <label className="text-[10px] text-[#888] uppercase tracking-wider">Your profile</label>
                      <span className="text-[9px] bg-[#0a2010] border border-[#1a4a20] rounded px-1 py-px text-[#34d399]">AI scored</span>
                      <span className="text-[9px] text-[#34d399]">most impactful</span>
                    </div>
                    <textarea
                      value={criteria.profile_description}
                      onChange={(e) => setCriteria({ ...criteria, profile_description: e.target.value })}
                      rows={3}
                      className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                    />
                    <p className="text-[9px] text-[#555] mt-1 leading-relaxed">The AI reads this to score job relevance — it understands context, not just keywords. Include your tech stack, years of experience, what kind of company you want, and what you want to avoid. The more specific, the better your scores.</p>
                  </div>

                  <div className="border-t border-[#1a1a1a] pt-2 mb-2">
                    <button
                      type="button"
                      onClick={() => setShowAdvanced(!showAdvanced)}
                      className="text-[10px] text-[#555] hover:text-[#888]"
                    >
                      {showAdvanced ? "▼" : "▶"} Advanced — location filters &amp; exclusion phrases
                    </button>
                    <p className="text-[9px] text-[#444] mt-1">These are also heuristic filters. Use them if you have specific geographic or content requirements.</p>
                  </div>

                  {showAdvanced && (
                    <div className="space-y-3 mb-3">
                      <div>
                        <div className="flex items-baseline gap-2 mb-1">
                          <label className="text-[10px] text-[#888] uppercase tracking-wider">Location must match</label>
                          <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                        </div>
                        <input
                          value={criteria.location_allowlist}
                          onChange={(e) => setCriteria({ ...criteria, location_allowlist: e.target.value })}
                          placeholder="e.g. remote|new york|london"
                          className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                        />
                        <p className="text-[9px] text-[#555] mt-1">Regex patterns. Leave blank to accept any location.</p>
                      </div>
                      <div>
                        <div className="flex items-baseline gap-2 mb-1">
                          <label className="text-[10px] text-[#888] uppercase tracking-wider">Location must NOT match</label>
                          <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                        </div>
                        <input
                          value={criteria.location_denylist}
                          onChange={(e) => setCriteria({ ...criteria, location_denylist: e.target.value })}
                          className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-xs text-[#e5e5e5]"
                        />
                        <p className="text-[9px] text-[#555] mt-1">Jobs in matching locations are discarded.</p>
                      </div>
                      <div>
                        <div className="flex items-baseline gap-2 mb-2">
                          <label className="text-[10px] text-[#888] uppercase tracking-wider">Exclusion keywords</label>
                          <span className="text-[9px] bg-[#1a1200] border border-[#3a2a00] rounded px-1 py-px text-[#f59e0b]">heuristic</span>
                        </div>
                        <TagChips
                          value={criteria.exclusion_keywords}
                          onChange={(v) => setCriteria({ ...criteria, exclusion_keywords: v })}
                          color="red"
                        />
                        <p className="text-[9px] text-[#555] mt-1">Jobs containing any of these exact phrases are discarded. Useful for filtering out visa-restricted or on-site-only postings.</p>
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2 items-center">
                    <button
                      onClick={() => saveCriteria.mutate(criteria)}
                      disabled={saveCriteria.isPending}
                      className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                    >
                      {saveCriteria.isPending ? "Saving..." : "Apply and continue"}
                    </button>
                    <button
                      onClick={() => setStep(4)}
                      className="text-xs text-[#555] hover:text-[#888]"
                    >
                      Skip customisation
                    </button>
                  </div>
                </div>

              ) : stage === null ? (
                /* Sub-step A: Stage picker */
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
                  <button
                    onClick={() => { setStage(null); setSelectedPreset(null); setStep(4); }}
                    className="text-xs text-[#555] hover:text-[#888]"
                  >
                    Skip
                  </button>
                </>

              ) : (
                /* Sub-step B: Preset picker */
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
                            onClick={() => {
                              setSelectedPreset(p.name);
                              setCriteria(toCriteriaValues(p.criteria as Record<string, unknown>));
                            }}
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
                      onClick={() => setEditorOpen(true)}
                      disabled={!selectedPreset}
                      className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                    >
                      Customize and continue
                    </button>
                    <button
                      onClick={() => { setStage(null); setSelectedPreset(null); setStep(4); }}
                      className="text-xs text-[#555] hover:text-[#888]"
                    >
                      Skip
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {step === 4 && (
            <div>
              <h2 className="text-sm font-semibold mb-1">Step 4: Choose companies to track</h2>
              <p className="text-xs text-[#666] mb-3">
                All companies are pre-selected. Deselect any you don't want.
              </p>

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
                <button onClick={() => setStep(5)} className="text-xs text-[#555] hover:text-[#888]">
                  Skip
                </button>
              </div>
            </div>
          )}

          {step === 5 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 5: Test run</h2>
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
