import { api } from "./client";

export interface Stats {
  total_companies: number;
  total_jobs_in_db: number;
  todays_matches: number;
  strong_today: number;
  quarantine_count: number;
  last_run_completed_at: string | null;
}

export const statsApi = {
  get: () => api.get<Stats>("/stats").then((r) => r.data),
};
