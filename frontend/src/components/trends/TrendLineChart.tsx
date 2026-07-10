import styles from "./TrendLineChart.module.css";
import type { MetricMeta } from "./trendsFormat";

interface Props {
  labels: string[];
  /** points[i] 는 labels[i] 분기의 값. 없으면 null(포인트 스킵). */
  points: Array<number | null>;
  meta: MetricMeta;
  width?: number;
  height?: number;
}

const Y_TICKS = 4;

/** 단일 지표 분기별 라인 차트(순수 SVG). 퍼센트 지표는 0~100, 그 외는 데이터 기반 스케일. */
export default function TrendLineChart({ labels, points, meta, width = 640, height = 280 }: Props) {
  if (labels.length === 0) return null;

  const padL = 52;
  const padR = 16;
  const padT = 14;
  const padB = 30;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const present = points.filter((v): v is number => v != null && !Number.isNaN(v));

  let yMin: number;
  let yMax: number;
  if (meta.fixed0to100) {
    yMin = 0;
    yMax = 100;
  } else if (present.length === 0) {
    yMin = 0;
    yMax = 1;
  } else {
    const dataMin = Math.min(...present);
    const dataMax = Math.max(...present);
    if (dataMin === dataMax) {
      // 단일 값: 0~값*1.2 범위로 여유를 준다.
      yMin = 0;
      yMax = dataMax === 0 ? 1 : dataMax * 1.2;
    } else {
      const span = dataMax - dataMin;
      yMin = Math.max(0, dataMin - span * 0.1);
      yMax = dataMax + span * 0.1;
    }
  }
  const yRange = yMax - yMin || 1;

  const xAt = (i: number) =>
    labels.length === 1 ? padL + plotW / 2 : padL + (plotW * i) / (labels.length - 1);
  const yAt = (v: number) => padT + plotH - (plotH * (v - yMin)) / yRange;

  const yTicks = Array.from({ length: Y_TICKS + 1 }, (_, i) => yMin + (yRange * i) / Y_TICKS);

  const coords = points
    .map((v, i) => (v == null || Number.isNaN(v) ? null : { x: xAt(i), y: yAt(v) }))
    .filter((c): c is { x: number; y: number } => c !== null);

  const linePath = coords.map((c) => `${c.x},${c.y}`).join(" ");
  const areaPath =
    coords.length > 1
      ? `M ${coords[0].x},${padT + plotH} ` +
        coords.map((c) => `L ${c.x},${c.y}`).join(" ") +
        ` L ${coords[coords.length - 1].x},${padT + plotH} Z`
      : "";

  return (
    <svg
      className={styles.svg}
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      role="img"
      aria-label={`분기별 ${meta.label} 추이 차트`}
    >
      {yTicks.map((t, i) => {
        const y = yAt(t);
        return (
          <g key={`yt-${i}`}>
            <line className={styles.grid} x1={padL} y1={y} x2={width - padR} y2={y} />
            <text
              className={styles.axisLabel}
              x={padL - 8}
              y={y}
              textAnchor="end"
              dominantBaseline="middle"
            >
              {meta.tick(t)}
            </text>
          </g>
        );
      })}

      {labels.map((label, i) => {
        // 라벨이 많으면 겹치므로 최대 ~8개만 표시(첫·끝 포함).
        const step = Math.max(1, Math.ceil(labels.length / 8));
        if (i % step !== 0 && i !== labels.length - 1) return null;
        return (
          <text
            key={`xt-${i}`}
            className={styles.axisLabel}
            x={xAt(i)}
            y={height - padB + 18}
            textAnchor="middle"
          >
            {label}
          </text>
        );
      })}

      {areaPath && <path className={styles.area} d={areaPath} />}
      {coords.length > 0 && <polyline className={styles.line} points={linePath} />}
      {coords.map((c, ci) => (
        <circle key={`p-${ci}`} className={styles.point} cx={c.x} cy={c.y} r={3.5} />
      ))}
    </svg>
  );
}
