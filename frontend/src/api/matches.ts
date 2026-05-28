import { api } from "./client";

export interface Match {
  id: number;
  job_id: number;
  score: number;
  tier: "strong" | "borderline";
  summary: string;
  is_preview: boolean;
  notified_at: string | null;
  not_interested_at: string | null;
  created_at: string;
  job_title: string;
  company_name: string;
  location: string | null;
  job_url: string;
}

export const matchesApi = {
  list: (params?: { tier?: string; limit?: number; offset?: number }) =>
    api.get<Match[]>("/matches", { params }).then((r) => r.data),
  notify: (match_ids: number[]) => api.post("/matches/notify", { match_ids }).then((r) => r.data),
};
