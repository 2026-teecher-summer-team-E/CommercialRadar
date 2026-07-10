export interface TimeSeriesPoint {
  label: string;
  value: number | null;
}

interface TimeSeriesChartProps {
  points: TimeSeriesPoint[];
  width?: number;
  height?: number;
  color?: string;
  /** y축 단위 표기 (예: "%"). */
  unit?: string;
}

/**
 * 단일 시리즈 시계열 라인차트(SVG 직접 구현).
 * 값이 하나뿐이거나 없으면 null 반환.
 */
export default function TimeSeriesChart({
  points,
  width = 560,
  height = 220,
  color = "var(--color-primary)",
  unit = "",
}: TimeSeriesChartProps) {
  const valid = points.filter((p) => p.value != null);
  if (valid.length < 2) {
    return null;
  }

  const padL = 12;
  const padR = 12;
  const padT = 16;
  const padB = 28;
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;

  const values = valid.map((p) => p.value as number);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const span = rawMax - rawMin || 1;
  const min = rawMin - span * 0.2;
  const max = rawMax + span * 0.2;

  const x = (i: number) => padL + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const y = (v: number) => padT + innerH - ((v - min) / (max - min)) * innerH;

  const linePath = points
    .map((p, i) =>
      p.value == null ? null : `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`,
    )
    .filter(Boolean)
    .join(" ")
    .replace(/^L/, "M");

  const lastIdx = points.map((p) => p.value != null).lastIndexOf(true);
  const lastVal = lastIdx >= 0 ? points[lastIdx].value : null;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      role="img"
      aria-label="시계열 추이"
      style={{ display: "block", overflow: "visible" }}
    >
      <path d={linePath} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

      {points.map((p, i) =>
        p.value == null ? null : (
          <circle key={i} cx={x(i)} cy={y(p.value)} r={i === lastIdx ? 4 : 2.5} fill={color} />
        ),
      )}

      {lastVal != null && (
        <text
          x={Math.min(x(lastIdx) + 6, width - 2)}
          y={y(lastVal) - 8}
          fontSize="12"
          fontWeight="700"
          fill={color}
          textAnchor="end"
          fontFamily="var(--font-num)"
        >
          {`${lastVal.toFixed(1)}${unit}`}
        </text>
      )}

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
