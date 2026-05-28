import { api } from "./client";

export interface ProviderStats {
  total_tokens_all_time: number;
  prompt_tokens_all_time: number;
  completion_tokens_all_time: number;
  total_tokens_7d: number;
  total_tokens_30d: number;
  filter_calls: number;
  summarize_calls: number;
}

export interface UsageData {
  providers: {
    groq: ProviderStats;
    cerebras: ProviderStats;
    gemini: ProviderStats;
  };
  recent_runs: Array<{
    run_id: number;
    groq: number;
    cerebras: number;
    gemini: number;
  }>;
}

export const usageApi = {
  get: () => api.get<UsageData>("/usage").then((r) => r.data),
};
