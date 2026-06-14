import { api } from "./client";

export type ApplicationStatus = "interested" | "applied" | "rejected" | "offer";
export type ApplicationSource = "joblin" | "external";

export interface ApplicationTracking {
  id: number;
  job_id: number | null;
  company_name: string;
  job_title: string;
  url: string | null;
  applied_date: string | null;
  notes: string | null;
  status: ApplicationStatus;
  source: ApplicationSource;
  score: number | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationStats {
  total: number;
  by_status: { interested: number; applied: number; rejected: number; offer: number };
  response_rate: number;
  by_source: { joblin: number; external: number };
  daily_series: Array<{
    date: string;
    interested?: number;
    applied?: number;
    rejected?: number;
    offer?: number;
  }>;
}

export const applicationsApi = {
  list: (params?: {
    status?: ApplicationStatus;
    source?: ApplicationSource;
    search?: string;
    limit?: number;
    offset?: number;
  }) => api.get<ApplicationTracking[]>("/applications", { params }).then((r) => r.data),

  create: (data: {
    job_id?: number;
    company_name: string;
    job_title: string;
    url?: string;
    applied_date?: string;
    notes?: string;
    status: ApplicationStatus;
    source: ApplicationSource;
    score?: number;
  }) => api.post<ApplicationTracking>("/applications", data).then((r) => r.data),

  update: (id: number, data: { status?: ApplicationStatus; notes?: string; applied_date?: string }) =>
    api.patch<ApplicationTracking>(`/applications/${id}`, data).then((r) => r.data),

  delete: (id: number) => api.delete(`/applications/${id}`),

  bulkAction: (data: { ids: number[]; action: "status_change" | "delete"; status?: ApplicationStatus }) =>
    api.post("/applications/bulk", data).then((r) => r.data),

  stats: () => api.get<ApplicationStats>("/applications/stats").then((r) => r.data),
};
