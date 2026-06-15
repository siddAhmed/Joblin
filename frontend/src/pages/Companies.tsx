import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { companiesApi } from "@/api/companies";
import type { Company, ProbeResult } from "@/api/companies";

function AddModal({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<"url" | "name">("url");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [probing, setProbing] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const qc = useQueryClient();

  const add = useMutation({
    mutationFn: () => companiesApi.add(name, url),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      onClose();
    },
  });

  const discoverByName = useMutation({
    mutationFn: () =>
      companiesApi.discover(
        nameInput
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean)
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      onClose();
    },
  });

  const handleProbe = async () => {
    setProbing(true);
    try {
      setProbe(await companiesApi.probe(name, url));
    } finally {
      setProbing(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-[#111] border border-[#2a2a2a] rounded-xl p-6 w-full max-w-md">
        <h2 className="text-sm font-semibold mb-3">Add Company</h2>

        {/* Tab toggle */}
        <div className="flex gap-1 mb-4 border border-[#2a2a2a] rounded-lg p-0.5 w-fit">
          <button
            onClick={() => setTab("url")}
            className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
              tab === "url" ? "bg-[#1e2a3a] text-[#4e9eff]" : "text-[#555] hover:text-[#888]"
            }`}
          >
            By URL
          </button>
          <button
            onClick={() => setTab("name")}
            className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
              tab === "name" ? "bg-[#1e2a3a] text-[#4e9eff]" : "text-[#555] hover:text-[#888]"
            }`}
          >
            By Name
          </button>
        </div>

        {tab === "url" && (
          <>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Company name"
              className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm mb-2 text-[#e5e5e5]"
            />
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Careers URL"
              className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm mb-3 text-[#e5e5e5]"
            />
            {probe && (
              <div className="mb-3 text-xs border border-[#2a2a2a] rounded p-2 bg-[#0a0a0a]">
                <div className="text-[#888]">
                  Detected: <span className="text-[#4e9eff]">{probe.ats_type}</span>
                </div>
                {probe.probe_attempts.map((a, i) => (
                  <div key={i} className="text-[#555] mt-0.5">
                    {a.url} -- {a.status_code ?? a.error}
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={handleProbe}
                disabled={!name || !url || probing}
                className="text-xs border border-[#2a2a2a] rounded px-3 py-1.5 text-[#888]"
              >
                {probing ? "Probing..." : "Probe ATS"}
              </button>
              <button
                onClick={() => add.mutate()}
                disabled={!name || !url || add.isPending}
                className="text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040]"
              >
                {add.isPending ? "Adding..." : "Add"}
              </button>
              <button
                onClick={onClose}
                className="text-xs border border-[#2a2a2a] rounded px-3 py-1.5 text-[#888] ml-auto"
              >
                Cancel
              </button>
            </div>
          </>
        )}

        {tab === "name" && (
          <>
            <p className="text-xs text-[#666] mb-2">
              One company name per line. Joblin will search for their careers page automatically.
            </p>
            <textarea
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              rows={5}
              placeholder={"Anthropic\nMistral AI\nCohere"}
              className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] font-mono mb-3"
            />
            <div className="flex gap-2">
              <button
                onClick={() => discoverByName.mutate()}
                disabled={!nameInput.trim() || discoverByName.isPending}
                className="text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
              >
                {discoverByName.isPending ? "Queuing..." : "Discover & Add"}
              </button>
              <button
                onClick={onClose}
                className="text-xs border border-[#2a2a2a] rounded px-3 py-1.5 text-[#888] ml-auto"
              >
                Cancel
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function Companies() {
  const [showAdd, setShowAdd] = useState(false);
  const [resolveUrls, setResolveUrls] = useState<Record<number, string>>({});
  const qc = useQueryClient();

  const { data: companies = [], isLoading } = useQuery({
    queryKey: ["companies"],
    queryFn: companiesApi.list,
  });

  const isDiscovering = companies.some((c: Company) => c.discovery_status === "discovering");

  useEffect(() => {
    if (!isDiscovering) return;
    const id = setInterval(() => {
      qc.invalidateQueries({ queryKey: ["companies"] });
    }, 4000);
    return () => clearInterval(id);
  }, [isDiscovering, qc]);

  const remove = useMutation({
    mutationFn: (id: number) => companiesApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });

  const retry = useMutation({
    mutationFn: (id: number) => companiesApi.retry(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });

  const resolve = useMutation({
    mutationFn: ({ id, url }: { id: number; url: string }) => companiesApi.resolve(id, url),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });

  return (
    <div>
      {showAdd && <AddModal onClose={() => setShowAdd(false)} />}
      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={() => setShowAdd(true)}
          className="text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040]"
        >
          Add company
        </button>
      </div>
      {isLoading && <p className="text-[#555] text-sm">Loading...</p>}
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[#1e1e1e] text-[#555] text-left">
            <th className="py-2 pr-4">Company</th>
            <th className="py-2 pr-4">ATS</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {companies.map((c: Company) => {
            if (c.discovery_status === "discovering") {
              return (
                <tr key={c.id} className="border-b border-[#111]">
                  <td className="py-2 pr-4 text-[#e5e5e5]">
                    <span className="mr-1.5 inline-block w-1.5 h-1.5 rounded-full bg-[#4e9eff] animate-pulse" />
                    {c.name}
                  </td>
                  <td className="py-2 pr-4 text-[#555] italic text-[10px]">
                    {c.discovery_message ?? "Discovering..."}
                  </td>
                  <td className="py-2 pr-4">
                    <span className="bg-[#1e1b4b] text-[#818cf8] px-1.5 rounded text-[10px]">
                      Discovering
                    </span>
                  </td>
                  <td className="py-2 text-[#333]">—</td>
                </tr>
              );
            }

            if (c.discovery_status === "failed") {
              return (
                <tr key={c.id} className="border-b border-[#111]">
                  <td className="py-2 pr-4 text-[#e5e5e5]">{c.name}</td>
                  <td className="py-2 pr-4" colSpan={2}>
                    <div className="flex items-center gap-2">
                      <span className="text-red-500 text-[10px]">Discovery failed</span>
                      <input
                        value={resolveUrls[c.id] ?? ""}
                        onChange={(e) =>
                          setResolveUrls((prev) => ({ ...prev, [c.id]: e.target.value }))
                        }
                        placeholder="Paste careers URL..."
                        className="bg-[#0d0d0d] border border-[#2a2a2a] rounded px-2 py-1 text-[11px] text-[#e5e5e5] w-52"
                      />
                      <button
                        onClick={() =>
                          resolve.mutate({ id: c.id, url: resolveUrls[c.id] ?? "" })
                        }
                        disabled={!resolveUrls[c.id]?.trim() || resolve.isPending}
                        className="text-[10px] border border-[#4e9eff] rounded px-2 py-1 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                      >
                        Save
                      </button>
                    </div>
                  </td>
                  <td className="py-2">
                    <button
                      onClick={() => remove.mutate(c.id)}
                      className="text-red-500 hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              );
            }

            return (
              <tr key={c.id} className="border-b border-[#111] hover:bg-[#0f0f0f]">
                <td className="py-2 pr-4 text-[#e5e5e5]">{c.name}</td>
                <td className="py-2 pr-4">
                  <span className="bg-[#1e2a3a] text-[#4e9eff] px-1.5 rounded text-[10px]">
                    {c.ats_type}
                  </span>
                </td>
                <td className="py-2 pr-4">
                  {c.quarantined_at ? (
                    <span className="text-orange-400">Quarantined</span>
                  ) : (
                    <span className="text-emerald-500">Active</span>
                  )}
                </td>
                <td className="py-2 flex gap-2">
                  {c.quarantined_at && (
                    <button
                      onClick={() => retry.mutate(c.id)}
                      className="text-[#4e9eff] hover:underline"
                    >
                      Retry
                    </button>
                  )}
                  <button
                    onClick={() => remove.mutate(c.id)}
                    className="text-red-500 hover:underline"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
