import { api } from "./client";

export interface Company {
  id: number;
  name: string;
  careers_url: string;
  ats_type: string;
  is_active: boolean;
  quarantine_count: number;
  quarantined_at: string | null;
  quarantine_reason: string | null;
}

export interface ProbeResult {
  ats_type: string;
  identifier: string | null;
  probe_attempts: Array<{ url: string; status_code: number | null; error: string | null }>;
}

export const companiesApi = {
  list: () => api.get<Company[]>("/companies").then((r) => r.data),
  probe: (name: string, careers_url: string) =>
    api.post<ProbeResult>("/companies/probe", { name, careers_url }).then((r) => r.data),
  add: (name: string, careers_url: string) =>
    api.post("/companies", { name, careers_url }).then((r) => r.data),
  update: (id: number, data: Partial<{ css_selector: string; is_active: boolean; ats_type: string; ats_identifier: string }>) =>
    api.patch(`/companies/${id}`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/companies/${id}`),
  retry: (id: number) => api.post(`/companies/${id}/retry`).then((r) => r.data),
  importCsv: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/companies/import", form, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
  },
};
