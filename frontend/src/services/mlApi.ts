import { apiClient } from "../lib/apiClient";
import type { SurvivalForecastResponse } from "../types";

export const mlApi = {
  /** 실제 구현 경로. (구 /api/forecast/survival 스텁이 아님) */
  survivalForecast: (id: number | string, params?: Record<string, string>) =>
    apiClient.get<SurvivalForecastResponse>(`/api/commercial-districts/${id}/survival-forecast`, { params }),
};
