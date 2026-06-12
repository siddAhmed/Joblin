import { api } from "./client";

export interface ResumeData {
  tex_content: string;
  updated_at: string;
}

export interface TailorResult {
  tex_content: string;
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
  tailor: (job_id: number) =>
    api.post<TailorResult>("/resume/tailor", { job_id }).then((r) => r.data),
};
