import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Editor from "@monaco-editor/react";
import { resumeApi } from "@/api/resume";
import { matchesApi } from "@/api/matches";

interface TailoredFor {
  jobId: number;
  title: string;
  company: string;
}

export function Resume() {
  const [searchParams] = useSearchParams();
  const [editorContent, setEditorContent] = useState("");
  const [referenceContent, setReferenceContent] = useState<string | null>(null);
  const [referenceUpdatedAt, setReferenceUpdatedAt] = useState<string | null>(null);
  const [tailoredFor, setTailoredFor] = useState<TailoredFor | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<number | "">("");
  const [isCompiling, setIsCompiling] = useState(false);
  const [isTailoring, setIsTailoring] = useState(false);
  const [compileError, setCompileError] = useState<string | null>(null);
  const [tailorError, setTailorError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [downloadName, setDownloadName] = useState<string>(
    () => localStorage.getItem("resume_download_filename") ?? "resume"
  );

  const { data: matches = [] } = useQuery({
    queryKey: ["matches", ""],
    queryFn: () => matchesApi.list({}),
  });

  useEffect(() => {
    resumeApi
      .get()
      .then((data) => {
        setEditorContent(data.tex_content);
        setReferenceContent(data.tex_content);
        setReferenceUpdatedAt(data.updated_at);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const jobIdParam = searchParams.get("jobId");
    if (jobIdParam && matches.length > 0) {
      setSelectedJobId(Number(jobIdParam));
    }
  }, [searchParams, matches]);

  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    };
  }, [pdfUrl]);

  async function handleSave() {
    setSaveError(null);
    try {
      const data = await resumeApi.save(editorContent);
      setReferenceContent(data.tex_content);
      setReferenceUpdatedAt(data.updated_at);
      setTailoredFor(null);
    } catch {
      setSaveError("Failed to save. Please try again.");
    }
  }

  async function handleCompile() {
    setIsCompiling(true);
    setCompileError(null);
    try {
      const pdfBuffer = await resumeApi.compile(editorContent);
      const blob = new Blob([pdfBuffer], { type: "application/pdf" });
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
      setPdfUrl(URL.createObjectURL(blob));
    } catch (err: any) {
      let detail = "Compilation failed";
      try {
        const raw = err?.response?.data;
        if (raw instanceof ArrayBuffer) {
          detail = JSON.parse(new TextDecoder().decode(raw))?.detail || detail;
        } else if (raw?.detail) {
          detail = raw.detail;
        }
      } catch {}
      setCompileError(detail);
    } finally {
      setIsCompiling(false);
    }
  }

  async function handleTailor() {
    if (!selectedJobId) return;
    setIsTailoring(true);
    setTailorError(null);
    try {
      const result = await resumeApi.tailor(Number(selectedJobId));
      setEditorContent(result.tex_content);
      const match = matches.find((m) => m.job_id === Number(selectedJobId));
      setTailoredFor({
        jobId: Number(selectedJobId),
        title: match?.job_title ?? "Unknown",
        company: match?.company_name ?? "Unknown",
      });
    } catch (err: any) {
      setTailorError(err?.response?.data?.detail || "Tailoring failed");
    } finally {
      setIsTailoring(false);
    }
  }

  function handleViewReference() {
    if (referenceContent !== null) {
      setEditorContent(referenceContent);
      setTailoredFor(null);
    }
  }

  function handleDownloadNameChange(name: string) {
    setDownloadName(name);
    localStorage.setItem("resume_download_filename", name);
  }

  function handleDownload() {
    if (!pdfUrl) return;
    const a = document.createElement("a");
    a.href = pdfUrl;
    a.download = `${downloadName.trim() || "resume"}.pdf`;
    a.click();
  }

  function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (ev) => {
      const content = ev.target?.result as string;
      setEditorContent(content);
      setTailoredFor(null);
      setSaveError(null);
      try {
        const data = await resumeApi.save(content);
        setReferenceContent(data.tex_content);
        setReferenceUpdatedAt(data.updated_at);
      } catch {
        setSaveError("Failed to save uploaded file. Please save manually.");
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  const isDirty = referenceContent !== null && editorContent !== referenceContent;
  const hasReference = referenceContent !== null;

  function renderStatusBar() {
    if (!hasReference && !editorContent) {
      return (
        <span className="text-[#555]">
          No resume yet - upload a .tex file to get started
        </span>
      );
    }
    if (!hasReference && editorContent) {
      return (
        <div className="flex items-center gap-2">
          <span className="text-[#f59e0b]">Not saved as reference</span>
          <button
            onClick={handleSave}
            className="text-[10px] border border-[#2a5c2a] rounded px-1.5 py-0.5 text-[#4ade80] hover:bg-[#1a3a1a]"
          >
            Save as Reference
          </button>
        </div>
      );
    }
    if (tailoredFor) {
      return (
        <div className="flex items-center gap-2">
          <span className="text-[#a78bfa]">
            ✦ Tailored for {tailoredFor.title} @ {tailoredFor.company}
          </span>
          <button
            onClick={handleSave}
            className="text-[10px] border border-[#2a5c2a] rounded px-1.5 py-0.5 text-[#4ade80] hover:bg-[#1a3a1a]"
          >
            Save as Reference
          </button>
          <button
            onClick={handleViewReference}
            className="text-[10px] border border-[#2a2a2a] rounded px-1.5 py-0.5 text-[#888] hover:text-[#ccc]"
          >
            ↩ View Reference
          </button>
        </div>
      );
    }
    if (isDirty) {
      return (
        <div className="flex items-center gap-2">
          <span className="text-[#f59e0b]">Unsaved changes</span>
          <button
            onClick={handleSave}
            className="text-[10px] border border-[#2a5c2a] rounded px-1.5 py-0.5 text-[#4ade80] hover:bg-[#1a3a1a]"
          >
            Save as Reference
          </button>
          <button
            onClick={handleViewReference}
            disabled={!hasReference}
            className="text-[10px] border border-[#2a2a2a] rounded px-1.5 py-0.5 text-[#888] hover:text-[#ccc] disabled:opacity-40"
          >
            ↩ Reset
          </button>
        </div>
      );
    }
    return (
      <span className="text-[#555]">
        Reference saved
        {referenceUpdatedAt
          ? ` · ${new Date(referenceUpdatedAt).toLocaleString()}`
          : ""}
      </span>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[#1e1e1e] bg-[#0d0d0d] flex-wrap shrink-0">
        <span className="text-[11px] text-[#555]">Job:</span>
        <select
          value={selectedJobId}
          onChange={(e) =>
            setSelectedJobId(e.target.value ? Number(e.target.value) : "")
          }
          className="bg-[#111] border border-[#2a2a2a] rounded px-2 py-1 text-xs text-[#ccc] max-w-[220px]"
        >
          <option value="">Select a match...</option>
          {matches.map((m) => (
            <option key={m.id} value={m.job_id}>
              {m.job_title} @ {m.company_name}
            </option>
          ))}
        </select>
        <button
          onClick={handleTailor}
          disabled={!selectedJobId || !hasReference || isTailoring}
          className="text-xs border border-[#4e4e9f] rounded px-3 py-1 text-[#a78bfa] hover:bg-[#1a1a3a] disabled:opacity-40"
        >
          {isTailoring ? "Tailoring..." : "✦ Tailor"}
        </button>
        <button
          onClick={handleCompile}
          disabled={isCompiling || !editorContent}
          className="text-xs border border-[#2a2a2a] rounded px-3 py-1 text-[#ccc] hover:bg-[#1a1a1a] disabled:opacity-40"
        >
          {isCompiling ? "Compiling..." : "▶ Compile"}
        </button>
        <div className="flex items-center gap-1">
          <input
            type="text"
            value={downloadName}
            onChange={(e) => handleDownloadNameChange(e.target.value)}
            placeholder="resume"
            className="bg-[#111] border border-[#2a2a2a] rounded px-2 py-1 text-xs text-[#ccc] w-28 focus:outline-none focus:border-[#444]"
          />
          <span className="text-[11px] text-[#444]">.pdf</span>
          <button
            onClick={handleDownload}
            disabled={!pdfUrl}
            className="text-xs border border-[#2a2a2a] rounded px-3 py-1 text-[#888] hover:text-[#ccc] disabled:opacity-40"
          >
            ↓ PDF
          </button>
        </div>
        <label className="ml-auto cursor-pointer text-xs border border-[#2a2a2a] rounded px-3 py-1 text-[#888] hover:text-[#ccc]">
          Upload .tex
          <input
            type="file"
            accept=".tex"
            className="hidden"
            onChange={handleUpload}
          />
        </label>
      </div>

      {/* Status bar */}
      <div className="px-4 py-1.5 border-b border-[#1e1e1e] bg-[#0a0a0a] text-[11px] shrink-0">
        {renderStatusBar()}
      </div>

      {/* Save error */}
      {saveError && (
        <div className="px-4 py-1 bg-red-950/20 border-b border-red-900/30 text-[10px] text-red-500 flex items-center justify-between shrink-0">
          <span>{saveError}</span>
          <button onClick={() => setSaveError(null)} className="ml-2 text-red-700 hover:text-red-500">✕</button>
        </div>
      )}

      {/* Tailor error */}
      {tailorError && (
        <div className="px-4 py-2 bg-red-950/30 border-b border-red-900/40 text-[11px] text-red-400 flex items-start justify-between shrink-0">
          <span className="flex-1">{tailorError}</span>
          <button
            onClick={() => setTailorError(null)}
            className="ml-2 text-red-600 hover:text-red-400 shrink-0"
          >
            ✕
          </button>
        </div>
      )}

      {/* Compile error */}
      {compileError && (
        <div className="px-4 py-2 bg-red-950/30 border-b border-red-900/40 text-[11px] text-red-400 flex items-start justify-between shrink-0">
          <pre className="whitespace-pre-wrap font-mono text-[10px] max-h-24 overflow-auto flex-1">
            {compileError}
          </pre>
          <button
            onClick={() => setCompileError(null)}
            className="ml-2 text-red-600 hover:text-red-400 shrink-0"
          >
            ✕
          </button>
        </div>
      )}

      {/* Two-panel editor + preview */}
      <div className="flex flex-1 min-h-0">
        <div className="flex-1 min-w-0 border-r border-[#1e1e1e]">
          <Editor
            height="100%"
            language="plaintext"
            theme="vs-dark"
            value={editorContent}
            onChange={(v) => setEditorContent(v ?? "")}
            options={{
              fontSize: 13,
              minimap: { enabled: false },
              wordWrap: "on",
              scrollBeyondLastLine: false,
              lineNumbers: "on",
            }}
          />
        </div>
        <div className="flex-1 min-w-0 bg-[#0a0a0a] flex items-center justify-center">
          {pdfUrl ? (
            <iframe
              src={pdfUrl}
              className="w-full h-full border-0"
              title="Resume PDF preview"
            />
          ) : (
            <div className="text-center text-[#444]">
              <p className="text-sm">No preview yet</p>
              <p className="text-[11px] mt-1">
                Click ▶ Compile to generate PDF
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
