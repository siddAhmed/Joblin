import { api } from "./client";

export interface ActivitiesData {
  activities_content: string | null;
  updated_at: string | null;
}

export const activitiesApi = {
  get: () =>
    api.get<ActivitiesData>("/resume/activities").then((r) => r.data),
  save: (activities_content: string) =>
    api
      .put<ActivitiesData>("/resume/activities", { activities_content })
      .then((r) => r.data),
};
