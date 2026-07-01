import { useState, useEffect } from "react";
import Editor from "@monaco-editor/react";
import ReactMarkdown from "react-markdown";
import { activitiesApi } from "@/api/activities";

const PLACEHOLDER = `# Career Activities

Use this document to keep a running record of everything you have done professionally.
The AI uses this alongside your resume when tailoring for a specific job.

## Work Experience
-

## Projects
-

## Skills & Certifications
-
`;

export function Activities() {
  const [content, setContent] = useState("");
  const [savedContent, setSavedContent] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(true);

  useEffect(() => {
    activitiesApi
      .get()
      .then((data) => {
        if (data.activities_content !== null) {
          setContent(data.activities_content);
          setSavedContent(data.activities_content);
          setSavedAt(data.updated_at);
        }
      })
      .catch(() => {});
  }, []);

  async function handleSave() {
    setIsSaving(true);
    setSaveError(null);
    try {
      const data = await activitiesApi.save(content);
      setSavedContent(data.activities_content ?? "");
      setSavedAt(data.updated_at);
    } catch {
      setSaveError("Failed to save. Please try again.");
    } finally {
      setIsSaving(false);
    }
  }

  const isDirty = savedContent !== null && content !== savedContent;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-[#1e1e1e] bg-[#0d0d0d] shrink-0">
        <span className="text-xs font-medium text-[#ccc]">Activities</span>
        <div className="ml-auto flex items-center gap-3">
          {saveError && (
            <span className="text-[11px] text-red-400">{saveError}</span>
          )}
          {!saveError && savedAt && !isDirty && (
            <span className="text-[11px] text-[#555]">
              Saved {new Date(savedAt).toLocaleTimeString()}
            </span>
          )}
          {isDirty && (
            <span className="text-[11px] text-[#f59e0b]">Unsaved changes</span>
          )}
          <button
            onClick={handleSave}
            disabled={isSaving || !isDirty}
            className="text-xs border border-[#2a5c2a] rounded px-3 py-1 text-[#4ade80] hover:bg-[#1a3a1a] disabled:opacity-40"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {/* Two-panel layout */}
      <div className="flex flex-1 min-h-0">
        {/* Editor */}
        <div
          className={`min-w-0 border-r border-[#1e1e1e] ${previewOpen ? "flex-1" : "flex-1"}`}
        >
          <Editor
            height="100%"
            language="markdown"
            theme="vs-dark"
            value={content || ""}
            onChange={(v) => setContent(v ?? "")}
            options={{
              fontSize: 13,
              minimap: { enabled: false },
              wordWrap: "on",
              scrollBeyondLastLine: false,
              lineNumbers: "off",
              placeholder: PLACEHOLDER,
            }}
          />
        </div>

        {/* Preview panel */}
        {previewOpen && (
          <div className="w-[45%] shrink-0 flex flex-col min-h-0 bg-[#0a0a0a]">
            <div className="flex items-center justify-between px-3 py-1.5 border-b border-[#1e1e1e] shrink-0">
              <span className="text-[10px] text-[#444]">Preview</span>
              <button
                onClick={() => setPreviewOpen(false)}
                className="text-[10px] text-[#555] hover:text-[#888] border border-[#2a2a2a] rounded px-1.5 py-0.5"
                title="Close preview"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-auto px-5 py-4 prose-activities">
              {content ? (
                <div className="text-[#ccc] text-sm leading-relaxed [&_h1]:text-[#e5e5e5] [&_h1]:text-base [&_h1]:font-semibold [&_h1]:mt-0 [&_h1]:mb-3 [&_h2]:text-[#aaa] [&_h2]:text-sm [&_h2]:font-medium [&_h2]:mt-4 [&_h2]:mb-2 [&_h3]:text-[#999] [&_h3]:text-xs [&_h3]:font-medium [&_h3]:mt-3 [&_h3]:mb-1 [&_ul]:pl-4 [&_ul]:space-y-0.5 [&_li]:text-[#bbb] [&_li]:text-xs [&_p]:text-xs [&_p]:text-[#bbb] [&_strong]:text-[#ddd] [&_code]:bg-[#1a1a1a] [&_code]:text-[#a78bfa] [&_code]:px-1 [&_code]:rounded [&_code]:text-xs">
                  <ReactMarkdown>{content}</ReactMarkdown>
                </div>
              ) : (
                <div className="text-[#333] text-xs italic">
                  Start typing to see a preview...
                </div>
              )}
            </div>
          </div>
        )}

        {/* Expand button when preview is closed */}
        {!previewOpen && (
          <div className="flex items-start pt-2 pr-2 shrink-0">
            <button
              onClick={() => setPreviewOpen(true)}
              className="text-[10px] text-[#555] hover:text-[#888] border border-[#2a2a2a] rounded px-1.5 py-0.5"
              title="Open preview"
            >
              Preview
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
