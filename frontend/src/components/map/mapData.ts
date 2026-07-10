import type {
  CommercialDistrict,
  DistrictTimeSeriesResponse,
  RadarResponse,
  PopulationHeatmapResponse,
} from "../../types";

/**
 * 지도 페이지 전용 타입/포맷/목업 좌표.
 *
 * 제약: Kakao 지도 SDK 키(VITE_KAKAO_MAP_KEY)와 좌표/GeoJSON API가 없으므로
 * 실제 지도 타일을 못 띄운다. Figma의 지도 영역 자체가 스타일화된 그리드 + 점수 핀
 * 목업이므로, 핀 위치는 아래 MOCK_PIN_POSITIONS 정적 배치를 쓰고,
 * 이름/점수는 실데이터(검색 결과 + getDistrict/radar)로 채운다.
 */

/** 지도 위 상권 점수 핀. 좌표는 목업(%), 이름·점수는 실데이터. */
export interface MapPin {
  id: number;
  name: string;
  score: number | null;
  /** 그리드 좌상단 기준 퍼센트 좌표(0~100). 목업 정적 배치. */
  x: number;
  y: number;
  /** true면 현재 선택된 상권(강조 핀). */
  active?: boolean;
}

/** 좌표 API가 없어 사용하는 정적 핀 배치(%). Figma 배치를 근사. */
export const MOCK_PIN_POSITIONS: ReadonlyArray<{ x: number; y: number }> = [
  { x: 50, y: 26 }, // 중앙(활성 후보)
  { x: 42, y: 11 },
  { x: 78, y: 15 },
  { x: 68, y: 20 },
  { x: 12, y: 24 },
  { x: 36, y: 32 },
  { x: 74, y: 42 },
  { x: 8, y: 46 },
  { x: 44, y: 48 },
  { x: 62, y: 52 },
  { x: 88, y: 58 },
  { x: 82, y: 72 },
];

/** 검색 결과(간략 타입). 검색 API 응답 형태. */
export interface DistrictSearchResult {
  id: number;
  district_name: string;
  type_name: string | null;
  gu_name: string | null;
  dong_name: string | null;
}

/** getDistrict 상세 응답. src/types 에 없으므로 여기서 최소 정의. */
export interface DistrictDetail extends CommercialDistrict {
  latest_stats: {
    year_quarter: string;
    district_score: number | null;
    survival_rate: number | null;
    closure_rate: number | null;
    total_business: number | null;
  } | null;
}

/** 좌측 패널에 표시할 상권 요약 데이터 묶음. */
export interface DistrictSummary {
  detail: DistrictDetail;
  radar: RadarResponse | null;
  heatmap: PopulationHeatmapResponse | null;
  timeSeries: DistrictTimeSeriesResponse | null;
}

/** null 안전 정수 점수(0~100). 없으면 null. */
export function toScore(value: number | null | undefined): number | null {
  if (value == null || Number.isNaN(value)) return null;
  return Math.round(value);
}

/** 퍼센트 포맷(값이 %단위라고 가정). */
export function fmtPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return `${value.toFixed(0)}%`;
}

/** 폐업위험 등급(폐업률 → 낮음/보통/높음). */
export function closureRiskLabel(rate: number | null | undefined): string {
  if (rate == null || Number.isNaN(rate)) return "-";
  if (rate < 5) return "낮음";
  if (rate < 10) return "보통";
  return "높음";
}

/** 유동인구를 만 단위로 포맷(예: 125000 → "12.5만"). */
export function fmtPopulation(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  if (value >= 10000) return `${(value / 10000).toFixed(1)}만`;
  return value.toLocaleString("ko-KR");
}

/** 매출을 억/만 단위로 포맷(예: 280000000 → "2.8억"). */
export function fmtSales(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  if (value >= 1_0000_0000) return `${(value / 1_0000_0000).toFixed(1)}억`;
  if (value >= 10000) return `${Math.round(value / 10000)}만`;
  return value.toLocaleString("ko-KR");
}

/** 종합 점수 → 등급 라벨/색. */
export function scoreGrade(score: number | null): { label: string; tone: "good" | "mid" | "low" } {
  if (score == null) return { label: "-", tone: "mid" };
  if (score >= 80) return { label: "우수", tone: "good" };
  if (score >= 60) return { label: "양호", tone: "mid" };
  return { label: "주의", tone: "low" };
}

/** 요일 헤더(혼잡도 히트맵). */
export const DAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"] as const;

/**
 * 시간대별 혼잡도 셀 값(0~1).
 *
 * heatmap 데이터는 2D 매트릭스가 아니라 by_time(시간대)/by_day(요일) 주변분포다.
 * 따라서 by_time × by_day 외적으로 셀 강도를 근사해 그리드로 그린다.
 * 데이터가 없으면 빈 배열을 반환(호출부에서 빈 상태 처리).
 */
export function buildCongestionGrid(heatmap: PopulationHeatmapResponse | null): {
  timeLabels: string[];
  cells: number[][];
} {
  if (!heatmap || heatmap.by_time.length === 0) {
    return { timeLabels: [], cells: [] };
  }
  const timeVals = heatmap.by_time.map((s) => s.avg_population ?? 0);
  const dayVals =
    heatmap.by_day.length === DAY_LABELS.length
      ? heatmap.by_day.map((s) => s.avg_population ?? 0)
      : DAY_LABELS.map(() => 1);

  const maxTime = Math.max(...timeVals, 1);
  const maxDay = Math.max(...dayVals, 1);

  const cells = heatmap.by_time.map((slot) => {
    const t = (slot.avg_population ?? 0) / maxTime;
    return dayVals.map((d) => {
      const dn = d / maxDay;
      return Math.max(0, Math.min(1, t * (0.6 + 0.4 * dn)));
    });
  });

  return {
    timeLabels: heatmap.by_time.map((s) => s.slot),
    cells,
  };
}

/** 혼잡도 강도(0~1) → 4단계 레벨(0~3). 범례: ~40 / 40+ / 65+ / 85+. */
export function congestionLevel(intensity: number): 0 | 1 | 2 | 3 {
  if (intensity >= 0.85) return 3;
  if (intensity >= 0.65) return 2;
  if (intensity >= 0.4) return 1;
  return 0;
}
