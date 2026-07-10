export interface RadarAxisDatum {
  label: string;
  value: number; // 0~100
}

interface RadarChartProps {
  axes: RadarAxisDatum[];
  size?: number;
  color?: string;
}

/**
 * 단일 시리즈 레이더 차트(SVG 직접 구현). 값은 0~100 정규화 가정.
 * 축이 3개 미만이면 null 반환.
 */
export default function RadarChart({ axes, size = 200, color = "var(--color-primary)" }: RadarChartProps) {
  if (axes.length < 3) return null;

  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 30;
  const n = axes.length;
  const rings = [0.25, 0.5, 0.75, 1];

  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const point = (i: number, r: number): [number, number] => [
    cx + Math.cos(angle(i)) * radius * r,
    cy + Math.sin(angle(i)) * radius * r,
  ];

  const gridPolygon = (r: number) =>
    axes.map((_, i) => point(i, r).map((c) => c.toFixed(1)).join(",")).join(" ");

  const dataPolygon = axes
    .map((a, i) => point(i, Math.max(0, Math.min(1, a.value / 100))).map((c) => c.toFixed(1)).join(","))
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      width="100%"
      role="img"
      aria-label="상권 지표 레이더"
      style={{ display: "block", overflow: "visible", maxWidth: size }}
    >
      {/* 그리드 링 */}
      {rings.map((r) => (
        <polygon
          key={r}
          points={gridPolygon(r)}
          fill="none"
          stroke="var(--color-line)"
          strokeWidth="1"
        />
      ))}
      {/* 축선 */}
      {axes.map((_, i) => {
        const [px, py] = point(i, 1);
        return <line key={i} x1={cx} y1={cy} x2={px} y2={py} stroke="var(--color-line)" strokeWidth="1" />;
      })}
      {/* 데이터 폴리곤 */}
      <polygon points={dataPolygon} fill={color} fillOpacity="0.18" stroke={color} strokeWidth="2" />
      {axes.map((a, i) => {
        const [px, py] = point(i, Math.max(0, Math.min(1, a.value / 100)));
        return <circle key={i} cx={px} cy={py} r={3} fill={color} />;
      })}
      {/* 축 라벨 */}
      {axes.map((a, i) => {
        const [lx, ly] = point(i, 1.18);
        const anchor = Math.abs(lx - cx) < 4 ? "middle" : lx > cx ? "start" : "end";
        return (
          <text
            key={i}
            x={lx}
            y={ly}
            fontSize="10"
            fill="var(--color-muted)"
            textAnchor={anchor}
            dominantBaseline="middle"
          >
            {a.label}
          </text>
        );
      })}
    </svg>
  );
}
