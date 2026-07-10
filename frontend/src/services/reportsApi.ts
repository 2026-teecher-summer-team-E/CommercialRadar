import { apiClient } from "../lib/apiClient";
import type { ReportListResponse } from "../types";

export const reportsApi = {
  list: (params?: { page?: number; limit?: number }) =>
    apiClient.get<ReportListResponse>("/api/reports", { params }),
  share: (id: number) => apiClient.post(`/api/reports/${id}/share`),
  remove: (id: number) => apiClient.delete(`/api/reports/${id}`),
};
