import { api } from "./client";

export interface Run {
  id: number;
  status: "running" | "completed" | "failed" | "cancelled";
  is_preview: boolean;
  started_at: string;
  completed_at: string | null;
  total_jobs_found: number;
  total_new_jobs: number;
  total_confirmed: number;
  total_notified: number;
}

export const runsApi = {
  list: () => api.get<Run[]>("/runs").then((r) => r.data),
  get: (id: number) => api.get(`/runs/${id}`).then((r) => r.data),
  start: (params: { company_ids?: number[]; preview?: boolean }) =>
    api.post<{ id: number; status: string }>("/runs", params).then((r) => r.data),
  cancel: (id: number) =>
    api.post<{ id: number; status: string }>(`/runs/${id}/cancel`).then((r) => r.data),
};
