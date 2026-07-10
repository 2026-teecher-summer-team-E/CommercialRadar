import { seriesColor } from "./format";
import styles from "./RadarChartSvg.module.css";

export interface RadarSeries {
  /** 상권명(범례용). */
  name: string;
  /** 축 순서와 동일한 길이의 값 배열(0~100). */
  values: number[];
}

interface Props {
  /** 축 라벨(꼭짓점 순서). */
  axes: string[];
  series: RadarSeries[];
  size?: number;
}

const RINGS = 4; // 동심 다각형 그리드 개수
const MAX = 100;

/** N각형 꼭짓점 좌표(반지름 r, 값 0~1 스케일된 factor). */
function points(
  count: number,
  cx: number,
  cy: number,
  radius: number,
  factors: number[],
): string {
  return factors
    .map((f, i) => {
      const angle = (Math.PI * 2 * i) / count - Math.PI / 2;
      const r = radius * f;
      return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
    })
    .join(" ");
}

/** 다중 상권 오버레이 레이더 차트(순수 SVG). */
export default function RadarChartSvg({ axes, series, size = 260 }: Props) {
  const n = axes.length;
  if (n < 3) return null;

  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 44; // 라벨 여백

  // 동심 그리드 다각형
  const rings = Array.from({ length: RINGS }, (_, r) => {
    const f = (r + 1) / RINGS;
    return points(n, cx, cy, radius, Array(n).fill(f));
  });

  // 축선 끝점
  const axisEnds = Array.from({ length: n }, (_, i) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
  });

  // 라벨 위치(축선보다 살짝 바깥)
  const labelPos = Array.from({ length: n }, (_, i) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const lr = radius + 18;
    const x = cx + lr * Math.cos(angle);
    const y = cy + lr * Math.sin(angle);
    let anchor: "start" | "middle" | "end" = "middle";
    if (Math.cos(angle) > 0.3) anchor = "start";
    else if (Math.cos(angle) < -0.3) anchor = "end";
    return { x, y, anchor };
  });

  return (
    <svg
      className={styles.svg}
      viewBox={`0 0 ${size} ${size}`}
      width="100%"
      role="img"
      aria-label="지표 레이더 차트"
    >
      {rings.map((ring, i) => (
        <polygon key={`ring-${i}`} className={styles.ring} points={ring} />
      ))}
      {axisEnds.map((p, i) => (
        <line key={`axis-${i}`} className={styles.axis} x1={cx} y1={cy} x2={p.x} y2={p.y} />
      ))}
      {series.map((s, si) => {
        const factors = s.values.map((v) => Math.max(0, Math.min(1, v / MAX)));
        const color = seriesColor(si);
        return (
          <polygon
            key={`series-${si}`}
            points={points(n, cx, cy, radius, factors)}
            fill={color}
            fillOpacity={0.14}
            stroke={color}
            strokeWidth={2}
          />
        );
      })}
      {labelPos.map((p, i) => (
        <text
          key={`label-${i}`}
          className={styles.label}
          x={p.x}
          y={p.y}
          textAnchor={p.anchor}
          dominantBaseline="middle"
        >
          {axes[i]}
        </text>
      ))}
    </svg>
  );
}
