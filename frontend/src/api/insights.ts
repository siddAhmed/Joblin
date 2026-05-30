import { api } from "./client";

export interface Skill {
  name: string;
  count: number;
}

export interface Citation {
  company_name: string;
  job_title: string;
}

export interface AnalyzeResult {
  analyzed: number;
  skipped: number;
  skills_found: number;
}

export interface SkillsData {
  skills: Skill[];
  total_jobs_analyzed: number;
}

export const insightsApi = {
  analyze: (match_ids: number[]) =>
    api.post<AnalyzeResult>("/insights/analyze", { match_ids }).then((r) => r.data),
  skills: () =>
    api.get<SkillsData>("/insights/skills").then((r) => r.data),
  citations: (name: string) =>
    api.get<Citation[]>(`/insights/skills/${encodeURIComponent(name)}/citations`).then((r) => r.data),
};
