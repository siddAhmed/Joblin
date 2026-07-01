import { api } from "./client";

export interface ResumeData {
  tex_content: string;
  updated_at: string;
}

export const resumeApi = {
  get: () =>
    api.get<ResumeData>("/resume").then((r) => r.data),
  save: (tex_content: string) =>
    api.put<ResumeData>("/resume", { tex_content }).then((r) => r.data),
  compile: (tex_content: string) =>
    api
      .post<ArrayBuffer>("/resume/compile", { tex_content }, { responseType: "arraybuffer" })
      .then((r) => r.data),
};

export async function tailorWithProgress(
  job_id: number,
  onPhase: (phase: number, label: string) => void
): Promise<string> {
  const response = await fetch("/api/resume/tailor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Tailoring failed" }));
    throw new Error(err.detail || "Tailoring failed");
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      if (!chunk.trim()) continue;
      let eventType = "message";
      let dataStr = "";
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) dataStr = line.slice(6).trim();
      }
      if (!dataStr) continue;
      const data = JSON.parse(dataStr);
      if (eventType === "phase") onPhase(data.phase, data.label);
      else if (eventType === "done") return data.tex_content as string;
      else if (eventType === "error") throw new Error(data.detail || "Tailoring failed");
    }
  }

  throw new Error("Stream ended without completion");
}
