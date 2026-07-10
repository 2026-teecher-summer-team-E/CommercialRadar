import { apiClient } from "../lib/apiClient";
import type {
  DistrictCompareResponse,
  DistrictTimeSeriesResponse,
  CategoryRankingResponse,
  RadarResponse,
  PopulationHeatmapResponse,
} from "../types";

type QP = Record<string, string | number | undefined>;

export const commercialApi = {
  listDistricts: () => apiClient.get("/api/commercial-districts"),
  getDistrict: (id: string | number) => apiClient.get(`/api/commercial-districts/${id}`),

  /** 다중 상권 비교. district_ids 는 콤마 구분. */
  compare: (ids: Array<number | string>, params?: { year_quarter?: string; category_name?: string }) =>
    apiClient.get<DistrictCompareResponse>("/api/commercial-districts/compare", {
      params: { district_ids: ids.join(","), ...params } as QP,
    }),

  timeSeries: (id: number | string, params?: QP) =>
    apiClient.get<DistrictTimeSeriesResponse>(`/api/commercial-districts/${id}/time-series`, { params }),

  categoryRanking: (id: number | string, params?: QP) =>
    apiClient.get<CategoryRankingResponse>(`/api/commercial-districts/${id}/category-ranking`, { params }),

  /** [신규] 5축 정규화 레이더 */
  radar: (id: number | string, params?: QP) =>
    apiClient.get<RadarResponse>(`/api/commercial-districts/${id}/radar`, { params }),

  /** [신규] 유동인구 히트맵(시간/요일 주변분포) */
  heatmap: (id: number | string, params?: QP) =>
    apiClient.get<PopulationHeatmapResponse>(`/api/commercial-districts/${id}/population-heatmap`, { params }),
};
