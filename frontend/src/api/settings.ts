import { api } from "./client";

export type KeyValidationResult = { valid: boolean; error: string | null }
export type ValidateKeysResponse = {
  groq?: KeyValidationResult
  cerebras?: KeyValidationResult
  gemini?: KeyValidationResult
}

export const settingsApi = {
  get: () => api.get("/settings").then((r) => r.data),
  update: (data: Record<string, unknown>) => api.patch("/settings", data).then((r) => r.data),
  testDiscord: () => api.post("/settings/discord/test").then((r) => r.data),
  testCriteria: (description: string) =>
    api.post("/settings/criteria/test", { description }).then((r) => r.data),
  listPresets: () => api.get("/presets").then((r) => r.data),
  applyPreset: (name: string) => api.post(`/presets/${name}/apply`).then((r) => r.data),
  validateKeys: (keys: { groq_api_key?: string; cerebras_api_key?: string; gemini_api_key?: string }) =>
    api
      .post<ValidateKeysResponse>("/settings/validate-keys", keys)
      .then((r) => r.data)
      .catch((err) => {
        if (err.response?.status === 422) return err.response.data as ValidateKeysResponse;
        throw err;
      }),
};
