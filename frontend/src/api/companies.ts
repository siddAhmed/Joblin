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
  discovery_status: "none" | "discovering" | "failed";
  discovery_message: string | null;
  catalog_id: number | null;
  source: string | null;
}

export interface AddCompanyResponse {
  id: number;
  catalog_id: number;
  ats_type: string;
  probe_attempts: Array<{ url: string; status_code: number | null; error: string | null }>;
  match_status:
    | "added_new"
    | "linked_existing_working"
    | "linked_existing_pending"
    | "linked_existing_quarantined"
    | "already_in_your_list";
}

export function matchStatusMessage(status: AddCompanyResponse["match_status"]): string {
  switch (status) {
    case "added_new":
      return "Added -- detecting ATS type...";
    case "linked_existing_working":
      return "Already in our catalog and working -- added to your list";
    case "linked_existing_pending":
      return "Already in our catalog (ATS detection pending) -- added to your list";
    case "linked_existing_quarantined":
      return "This company is in our catalog but currently quarantined -- added anyway";
    case "already_in_your_list":
      return "You are already monitoring this company";
  }
}

export interface ProbeResult {
  ats_type: string;
  identifier: string | null;
  probe_attempts: Array<{ url: string; status_code: number | null; error: string | null }>;
}

export interface DefaultCompany {
  name: string;
  careers_url: string;
}

export const companiesApi = {
  list: () => api.get<Company[]>("/companies").then((r) => r.data),
  defaults: () => api.get<DefaultCompany[]>("/companies/defaults").then((r) => r.data),
  probe: (name: string, careers_url: string) =>
    api.post<ProbeResult>("/companies/probe", { name, careers_url }).then((r) => r.data),
  add: (name: string, careers_url: string) =>
    api.post<AddCompanyResponse>("/companies", { name, careers_url }).then((r) => r.data),
  bulk: (items: DefaultCompany[]) =>
    api.post<{ created: number }>("/companies/bulk", items).then((r) => r.data),
  discover: (names: string[]) =>
    api.post<{ created: number; ids: number[] }>("/companies/discover", { names }).then((r) => r.data),
  resolve: (id: number, careers_url: string) =>
    api.post(`/companies/${id}/resolve`, { careers_url }).then((r) => r.data),
  update: (
    id: number,
    data: Partial<{ css_selector: string; is_active: boolean; ats_type: string; ats_identifier: string }>
  ) => api.patch(`/companies/${id}`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/companies/${id}`),
  retry: (id: number) => api.post(`/companies/${id}/retry`).then((r) => r.data),
  importCsv: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api
      .post("/companies/import", form, { headers: { "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },
};
