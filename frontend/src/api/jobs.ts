import { api } from "./client";

export interface Job {
  id: number;
  company_id: number;
  title: string;
  location: string | null;
  url: string;
  first_seen_at: string;
  is_active: boolean;
}

export interface JobDetail extends Job {
  raw_description: string;
  match: { score: number; tier: string; summary: string; not_interested_at?: string | null } | null;
}

export const jobsApi = {
  list: (params?: { company_id?: number; search?: string; limit?: number; offset?: number }) =>
    api.get<Job[]>("/jobs", { params }).then((r) => r.data),
  get: (id: number) => api.get<JobDetail>(`/jobs/${id}`).then((r) => r.data),
  dismiss: (id: number) => api.post(`/jobs/${id}/dismiss`).then((r) => r.data),
};
