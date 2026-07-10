// ── 기존 ─────────────────────────────────────────────
export interface CommercialDistrict {
  id: number;
  district_name: string;
  type_name: string | null;
  gu_name: string | null;
  dong_name: string | null;
  avg_population: number | null;
  area_name: string | null;
}

export interface BusinessCategory {
  id: number;
  commercial_district_id: number;
  category_name: string | null;
  year_quarter: string;
  closure_rate: number | null;
  survival_rate: number | null;
  open_rate: number | null;
  total_business: number | null;
  total_sales: number | null;
}

export type PredictionType = "survival" | "population" | "sales";

// ── 상권 비교 (GET /api/commercial-districts/compare) ──
export interface DistrictCompareItem {
  id: number;
  district_name: string;
  avg_population: number | null;
  survival_rate: number | null;
  closure_rate: number | null;
  district_score: number | null;
}
export interface DistrictCompareResponse {
  year_quarter: string | null;
  category_name: string | null;
  districts: DistrictCompareItem[];
}

// ── 분기별 추이 (GET /api/commercial-districts/{id}/time-series) ──
export interface PopulationMetric {
  total: number | null;
  breakdown?: Record<string, Record<string, number>> | null;
}
export interface DistrictQuarterMetrics {
  year_quarter: string;
  survival_rate: number | null;
  closure_rate: number | null;
  open_rate: number | null;
  population: PopulationMetric | null;
  sales: number | null;
}
export interface DistrictTimeSeriesResponse {
  district_id: number;
  data: DistrictQuarterMetrics[];
}

// ── 업종 랭킹 (GET /api/commercial-districts/{id}/category-ranking) ──
export interface CategoryRankingItem {
  rank: number;
  category_name: string | null;
  district_score: number | null;
  survival_rate: number | null;
  total_business: number | null;
}
export interface CategoryRankingResponse {
  district_id: number;
  year_quarter: string | null;
  ranking: CategoryRankingItem[];
}

// ── 생존율 예측 (GET /api/commercial-districts/{id}/survival-forecast) ──
export interface SurvivalForecastPoint {
  year_quarter: string;
  survival_rate: number | null;
  confidence: number | null;
}
export interface SurvivalForecastResponse {
  district_id: number;
  model: string;
  category_name: string | null;
  forecast: SurvivalForecastPoint[];
}

// ── 레이더 (GET /api/commercial-districts/{id}/radar) [신규] ──
export interface RadarAxis {
  key: string;
  label: string;
  value: number; // 0~100
}
export interface RadarResponse {
  district_id: number;
  year_quarter: string | null;
  axes: RadarAxis[];
}

// ── 유동인구 히트맵 (GET /api/commercial-districts/{id}/population-heatmap) [신규] ──
// 주의: 데이터는 2D 매트릭스가 아니라 시간대/요일 주변분포(marginal)다.
export interface HeatmapSlot {
  slot: string;
  avg_population: number | null;
}
export interface PopulationHeatmapResponse {
  district_id: number;
  by_time: HeatmapSlot[];
  by_day: HeatmapSlot[];
}

// ── 유저 (GET /api/users/me, /api/users/me/stats) [신규] ──
export interface UserMe {
  id: number;
  name: string;
  email: string | null;
  is_admin: boolean;
  is_company: boolean;
  created_at: string;
}
export interface UserStats {
  saved_reports: number;
  interest_districts: number;
  shared_reports: number;
}

// ── 리포트 (GET /api/reports) ──
export interface ReportListItem {
  id: number;
  title: string;
  district_name: string | null;
  category_name: string | null;
  memo: string | null;
  created_at: string;
}
export interface ReportListResponse {
  total: number;
  page: number;
  limit: number;
  reports: ReportListItem[];
}

// ── 관심 상권 (GET /api/interest-districts) ──
export interface InterestDistrict {
  id: number;
  commercial_district_id: number;
  district_name?: string | null;
  category_name?: string | null;
  memo?: string | null;
  created_at: string;
}
