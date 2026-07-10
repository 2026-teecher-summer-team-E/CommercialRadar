/** 랭킹 페이지 전용 숫자/텍스트 포맷 헬퍼. */

/** null 안전 소수 포맷. 값이 없으면 "—". */
export function fmtNum(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

/** 퍼센트 포맷 (값 자체가 %단위라고 가정). 값이 없으면 "—". */
export function fmtPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}%`;
}

/** 유동인구를 만 단위로 포맷. (예: 32000 → "3.2만") */
export function fmtPopulation(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (value >= 10000) return `${(value / 10000).toFixed(1)}만`;
  return value.toLocaleString("ko-KR");
}

export type ClosureRisk = "low" | "mid" | "high" | "none";

/** 폐업률(closure_rate)을 위험 등급으로 변환. */
export function closureRisk(rate: number | null | undefined): ClosureRisk {
  if (rate == null || Number.isNaN(rate)) return "none";
  if (rate < 5) return "low";
  if (rate < 10) return "mid";
  return "high";
}

/** 폐업 위험 등급의 한국어 라벨. */
export function closureRiskLabel(risk: ClosureRisk): string {
  switch (risk) {
    case "low":
      return "낮음";
    case "mid":
      return "보통";
    case "high":
      return "높음";
    default:
      return "—";
  }
}
