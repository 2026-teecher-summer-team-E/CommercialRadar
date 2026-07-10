import { seriesColor } from "./format";
import styles from "./LineChartSvg.module.css";

export interface LineSeries {
  name: string;
  /** points[i] 는 labels[i] 분기의 값. 없으면 null(포인트 스킵). */
  points: Array<number | null>;
}

interface Props {
  labels: string[];
  series: LineSeries[];
  width?: number;
  height?: number;
}

const Y_TICKS = 4;

/** 다중 상권 오버레이 라인 차트(순수 SVG). Y축은 0~100 고정(생존율 %). */
export default function LineChartSvg({ labels, series, width = 520, height = 260 }: Props) {
  if (labels.length === 0) return null;

  const padL = 36;
  const padR = 12;
  const padT = 12;
  const padB = 28;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const yMin = 0;
  const yMax = 100;

  const xAt = (i: number) =>
    labels.length === 1 ? padL + plotW / 2 : padL + (plotW * i) / (labels.length - 1);
  const yAt = (v: number) => padT + plotH - (plotH * (v - yMin)) / (yMax - yMin);

  const yTicks = Array.from({ length: Y_TICKS + 1 }, (_, i) => yMin + ((yMax - yMin) * i) / Y_TICKS);

  return (
    <svg
      className={styles.svg}
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      role="img"
      aria-label="분기별 생존율 추이 차트"
    >
      {yTicks.map((t, i) => {
        const y = yAt(t);
        return (
          <g key={`yt-${i}`}>
            <line className={styles.grid} x1={padL} y1={y} x2={width - padR} y2={y} />
            <text className={styles.axisLabel} x={padL - 8} y={y} textAnchor="end" dominantBaseline="middle">
              {t}
            </text>
          </g>
        );
      })}

      {labels.map((label, i) => (
        <text
          key={`xt-${i}`}
          className={styles.axisLabel}
          x={xAt(i)}
          y={height - padB + 16}
          textAnchor="middle"
        >
          {label}
        </text>
      ))}

      {series.map((s, si) => {
        const color = seriesColor(si);
        const coords = s.points
          .map((v, i) => (v == null ? null : { x: xAt(i), y: yAt(v) }))
          .filter((c): c is { x: number; y: number } => c !== null);
        if (coords.length === 0) return null;
        const path = coords.map((c) => `${c.x},${c.y}`).join(" ");
        return (
          <g key={`s-${si}`}>
            <polyline className={styles.line} points={path} stroke={color} />
            {coords.map((c, ci) => (
              <circle key={`p-${si}-${ci}`} cx={c.x} cy={c.y} r={3} fill={color} />
            ))}
          </g>
        );
      })}
    </svg>
  );
}
