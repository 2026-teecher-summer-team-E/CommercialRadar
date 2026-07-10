import { useId } from "react";

export interface ForecastPoint {
  label: string;
  value: number | null;
  /** true면 예측 구간(점선). false/undefined면 실적 구간(실선). */
  forecast?: boolean;
}

interface ForecastChartProps {
  points: ForecastPoint[];
  width?: number;
  height?: number;
}

/**
 * 생존율 예측 라인차트(SVG 직접 구현).
 * 실적 구간은 실선, 예측 구간은 점선으로 그린다.
 * 예측 구간에는 부드러운 신뢰밴드(면적)를 채운다.
 */
export default function ForecastChart({ points, width = 560, height = 220 }: ForecastChartProps) {
  const gradId = useId();
  const valid = points.filter((p): p is ForecastPoint & { value: number } => p.value != null);
  if (valid.length < 2) {
    return null;
  }

  const padL = 12;
  const padR = 12;
  const padT = 18;
  const padB = 28;
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;

  const values = points.map((p) => p.value).filter((v): v is number => v != null);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const span = rawMax - rawMin || 1;
  const min = rawMin - span * 0.25;
  const max = rawMax + span * 0.25;

  const x = (i: number) => padL + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const y = (v: number) => padT + innerH - ((v - min) / (max - min)) * innerH;

  // 실적/예측 경계 인덱스를 찾아 두 개의 폴리라인으로 분할.
  const coords = points.map((p, i) => ({ i, v: p.value, forecast: !!p.forecast }));
  const actualPts = coords.filter((c) => c.v != null && !c.forecast);
  const firstForecastIdx = coords.findIndex((c) => c.forecast);
  // 예측 라인은 실적 마지막 점부터 이어지도록 경계점을 포함시킨다.
  const forecastStart = firstForecastIdx > 0 ? firstForecastIdx - 1 : firstForecastIdx;
  const forecastPts =
    firstForecastIdx === -1
      ? []
      : coords.slice(forecastStart).filter((c) => c.v != null);

  const toPath = (arr: Array<{ i: number; v: number | null }>) =>
    arr
      .filter((c) => c.v != null)
      .map((c, k) => `${k === 0 ? "M" : "L"}${x(c.i).toFixed(1)},${y(c.v as number).toFixed(1)}`)
      .join(" ");

  const actualPath = toPath(actualPts);
  const forecastPath = toPath(forecastPts);

  // 예측 신뢰밴드(면적): 예측 구간 위/아래로 약간의 폭.
  const bandPad = span * 0.12;
  const bandTop = forecastPts.map((c) => `${x(c.i).toFixed(1)},${y((c.v as number) + bandPad).toFixed(1)}`);
  const bandBottom = forecastPts
    .map((c) => `${x(c.i).toFixed(1)},${y((c.v as number) - bandPad).toFixed(1)}`)
    .reverse();
  const bandPath =
    forecastPts.length >= 2 ? `M${bandTop.join(" L")} L${bandBottom.join(" L")} Z` : "";

  const lastPt = valid[valid.length - 1];
  const lastIdx = points.indexOf(lastPt as ForecastPoint);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      role="img"
      aria-label="생존율 예측 추이"
      style={{ display: "block", overflow: "visible" }}
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-primary)" stopOpacity="0.16" />
          <stop offset="100%" stopColor="var(--color-primary)" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* 신뢰밴드 */}
      {bandPath && <path d={bandPath} fill={`url(#${gradId})`} stroke="none" />}

      {/* 실적 실선 */}
      {actualPath && (
        <path d={actualPath} fill="none" stroke="var(--color-primary)" strokeWidth="2.5" strokeLinecap="round" />
      )}
      {/* 예측 점선 */}
      {forecastPath && (
        <path
          d={forecastPath}
          fill="none"
          stroke="var(--color-primary)"
          strokeWidth="2.5"
          strokeDasharray="5 5"
          strokeLinecap="round"
        />
      )}

      {/* 데이터 포인트 */}
      {points.map((p, i) =>
        p.value == null ? null : (
          <circle
            key={i}
            cx={x(i)}
            cy={y(p.value)}
            r={i === lastIdx ? 4.5 : 3}
            fill="var(--color-surface)"
            stroke="var(--color-primary)"
            strokeWidth="2"
          />
        ),
      )}

      {/* 마지막 값 라벨 */}
      {lastPt && (
        <text
          x={Math.min(x(lastIdx) + 6, width - 2)}
          y={y(lastPt.value) - 8}
          fontSize="12"
          fontWeight="700"
          fill="var(--color-primary)"
          textAnchor="end"
          fontFamily="var(--font-num)"
        >
          {`${lastPt.value.toFixed(0)}%`}
        </text>
      )}

      {/* X축 라벨 */}
      {points.map((p, i) => (
        <text
          key={`lbl-${i}`}
          x={x(i)}
          y={height - 8}
          fontSize="10"
          fill="var(--color-faint)"
          textAnchor="middle"
        >
          {p.label}
        </text>
      ))}
    </svg>
  );
}
