/** 트렌드 페이지 전용 숫자/포맷 헬퍼. (다른 폴더 수정 금지 규칙으로 로컬 구현) */

export type MetricKey = "survival" | "population" | "sales";

export interface MetricMeta {
  key: MetricKey;
  label: string;
  /** 값 포맷터. */
  format: (v: number | null | undefined) => string;
  /** 증감(Δ) 표시에서 값이 클수록 좋은 지표인지. */
  higherIsBetter: boolean;
  /** Y축 눈금 라벨 포맷(짧게). */
  tick: (v: number) => string;
  /** Y축을 0~100 으로 고정할지(퍼센트 지표). */
  fixed0to100: boolean;
}

/** null 안전 소수 포맷. */
export function fmtNum(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "-";
  return value.toFixed(digits);
}

/** 퍼센트 포맷 (값 자체가 %단위라고 가정). */
export function fmtPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return `${value.toFixed(1)}%`;
}

/** 유동인구/매출 등 큰 수를 만·억 단위로 축약. */
export function fmtCompact(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${(value / 10_000).toFixed(1)}만`;
  return value.toLocaleString("ko-KR");
}

/** 개수를 콤마 포맷. */
export function fmtCount(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return value.toLocaleString("ko-KR");
}

export const METRICS: Record<MetricKey, MetricMeta> = {
  survival: {
    key: "survival",
    label: "생존율",
    format: fmtPct,
    higherIsBetter: true,
    tick: (v) => `${Math.round(v)}`,
    fixed0to100: true,
  },
  population: {
    key: "population",
    label: "유동인구",
    format: fmtCompact,
    higherIsBetter: true,
    tick: (v) => fmtCompact(v),
    fixed0to100: false,
  },
  sales: {
    key: "sales",
    label: "매출",
    format: fmtCompact,
    higherIsBetter: true,
    tick: (v) => fmtCompact(v),
    fixed0to100: false,
  },
};

export const METRIC_ORDER: MetricKey[] = ["survival", "population", "sales"];
