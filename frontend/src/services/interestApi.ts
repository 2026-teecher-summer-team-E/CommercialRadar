import { apiClient } from "../lib/apiClient";
import type { InterestDistrict } from "../types";

export const interestApi = {
  list: () => apiClient.get<InterestDistrict[]>("/api/interest-districts"),
  remove: (id: number) => apiClient.delete(`/api/interest-districts/${id}`),
};
