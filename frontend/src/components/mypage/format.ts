/** 마이페이지 공용 포맷 유틸. */

/** "2026-01-15..." → "2026년 1월 가입" */
export function formatJoinDate(iso: string | null | undefined): string {
  if (!iso) return "가입일 미상";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "가입일 미상";
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 가입`;
}

/** "2026-01-15..." → "2026. 1. 15." */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return `${d.getFullYear()}. ${d.getMonth() + 1}. ${d.getDate()}.`;
}

/** 이름 첫 글자(아바타/이니셜용). 비어있으면 "?" */
export function initialOf(name: string | null | undefined): string {
  const trimmed = (name ?? "").trim();
  return trimmed ? trimmed.charAt(0).toUpperCase() : "?";
}

/** 시리즈색 3종 순환용 CSS 변수 이름. */
const SERIES_VARS = ["--series-1", "--series-2", "--series-3"] as const;
const SERIES_BG_VARS = ["--series-1-bg", "--series-2-bg", "--series-3-bg"] as const;

export function seriesColor(index: number): string {
  return `var(${SERIES_VARS[index % SERIES_VARS.length]})`;
}
export function seriesBg(index: number): string {
  return `var(${SERIES_BG_VARS[index % SERIES_BG_VARS.length]})`;
}
