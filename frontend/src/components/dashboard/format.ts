/** 대시보드 페이지 전용 숫자/텍스트 포맷 헬퍼. 값이 없으면 "—". */

const DASH = "—";

/** null 안전 소수 포맷. */
export function fmtNum(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return DASH;
  return value.toFixed(digits);
}

/** 퍼센트 포맷 (값 자체가 %단위라고 가정). */
export function fmtPct(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return DASH;
  return `${value.toFixed(digits)}%`;
}

/** 유동인구를 만 단위로 포맷. (예: 125000 → "12.5만") */
export function fmtManUnit(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return DASH;
  if (value >= 10000) return `${(value / 10000).toFixed(digits)}만`;
  return value.toLocaleString("ko-KR");
}

/** 정수 콤마 포맷. */
export function fmtInt(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return DASH;
  return Math.round(value).toLocaleString("ko-KR");
}

/** 폐업률(closure_rate)을 낮음/보통/높음 위험 등급으로 변환. */
export function closureRiskLabel(rate: number | null | undefined): string {
  if (rate == null || Number.isNaN(rate)) return DASH;
  if (rate < 5) return "낮음";
  if (rate < 10) return "보통";
  return "높음";
}

/** 위험 등급에 대응하는 색 토큰. */
export function riskColor(rate: number | null | undefined): string {
  if (rate == null || Number.isNaN(rate)) return "var(--color-muted)";
  if (rate < 5) return "var(--color-green)";
  if (rate < 10) return "var(--color-amber)";
  return "var(--color-red)";
}

/** 분기 코드(2026-Q1)를 "4분기"처럼 사람이 읽는 라벨로. 그대로 fallback. */
export function quarterLabel(yq: string | null | undefined): string {
  if (!yq) return DASH;
  const m = /^(\d{4})-Q([1-4])$/.exec(yq);
  if (!m) return yq;
  return `${m[1]}년 ${m[2]}분기`;
}

/** 짧은 분기 라벨 (2026-Q1 → "26 1Q"). 차트 X축용. */
export function quarterShort(yq: string | null | undefined): string {
  if (!yq) return "";
  const m = /^(\d{4})-Q([1-4])$/.exec(yq);
  if (!m) return yq;
  return `${m[1].slice(2)} ${m[2]}Q`;
}
