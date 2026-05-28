import { api } from "./client";

export const settingsApi = {
  get: () => api.get("/settings").then((r) => r.data),
  update: (data: Record<string, unknown>) => api.patch("/settings", data).then((r) => r.data),
  testDiscord: () => api.post("/settings/discord/test").then((r) => r.data),
  testCriteria: (description: string) =>
    api.post("/settings/criteria/test", { description }).then((r) => r.data),
  listPresets: () => api.get("/presets").then((r) => r.data),
  applyPreset: (name: string) => api.post(`/presets/${name}/apply`).then((r) => r.data),
};
