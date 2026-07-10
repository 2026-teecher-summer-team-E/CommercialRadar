import { useMemo } from "react";
import type { HeatmapSlot } from "../../types";
import { fmtInt } from "./format";
import styles from "./PopulationHeatmap.module.css";

interface PopulationHeatmapProps {
  byTime: HeatmapSlot[];
  byDay: HeatmapSlot[];
  /** true면 셀에 값을 함께 표시(모달 상세용). */
  showValues?: boolean;
}

/** Figma 순서 그대로. 데이터에 없는 slot 은 비운다. */
const DAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"];
const TIME_ORDER = ["00~06", "06~11", "11~14", "14~17", "17~21", "21~24"];
/** 세로축 표기(Figma 는 하이픈). slot 키는 물결(~)이라 별도 라벨 매핑. */
const TIME_LABEL: Record<string, string> = {
  "00~06": "00-06",
  "06~11": "06-11",
  "11~14": "11-14",
  "14~17": "14-17",
  "17~21": "17-21",
  "21~24": "21-24",
};

/**
 * 시간대·요일 주변분포(marginal)를 2D 그리드로 근사한다.
 * 각 셀 강도 = (시간대 비율) × (요일 비율), 전체 최댓값으로 0~1 정규화.
 * (지도 페이지 buildCongestionGrid 와 동일 아이디어의 자체 구현.)
 */
export default function PopulationHeatmap({ byTime, byDay, showValues = false }: PopulationHeatmapProps) {
  const timeMap = useMemo(
    () => new Map(byTime.map((s) => [s.slot, s.avg_population ?? 0])),
    [byTime],
  );
  const dayMap = useMemo(
    () => new Map(byDay.map((s) => [s.slot, s.avg_population ?? 0])),
    [byDay],
  );

  const grid = useMemo(() => {
    const timeSum = TIME_ORDER.reduce((a, t) => a + (timeMap.get(t) ?? 0), 0) || 1;
    const daySum = DAY_ORDER.reduce((a, d) => a + (dayMap.get(d) ?? 0), 0) || 1;
    const rows = TIME_ORDER.map((t) => {
      const tw = (timeMap.get(t) ?? 0) / timeSum;
      return DAY_ORDER.map((d) => {
        const dw = (dayMap.get(d) ?? 0) / daySum;
        // 근사 절대값: 시간대 유동량 × 요일 비율.
        const value = (timeMap.get(t) ?? 0) * dw * DAY_ORDER.length;
        return { time: t, day: d, weight: tw * dw, value };
      });
    });
    return rows;
  }, [timeMap, dayMap]);

  const maxWeight = useMemo(() => {
    let m = 0;
    grid.forEach((row) => row.forEach((c) => (m = Math.max(m, c.weight))));
    return m || 1;
  }, [grid]);

  const hasData = byTime.length > 0 && byDay.length > 0;
  if (!hasData) {
    return <div className={styles.empty}>유동인구 데이터가 없어요.</div>;
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.grid} style={{ gridTemplateColumns: `48px repeat(${DAY_ORDER.length}, 1fr)` }}>
        {/* 헤더 행: 요일 */}
        <span className={styles.corner} />
        {DAY_ORDER.map((d) => (
          <span key={d} className={styles.colHead}>
            {d}
          </span>
        ))}
        {/* 데이터 행 */}
        {grid.map((row, ri) => (
          <Row key={TIME_ORDER[ri]} time={TIME_ORDER[ri]} row={row} maxWeight={maxWeight} showValues={showValues} />
        ))}
      </div>
      <div className={styles.legend}>
        <span className={styles.legendLabel}>낮음</span>
        {[0.15, 0.4, 0.65, 0.9].map((t) => (
          <span
            key={t}
            className={styles.legendCell}
            style={{ backgroundColor: `color-mix(in srgb, var(--color-primary) ${Math.round(t * 100)}%, var(--color-primary-light))` }}
          />
        ))}
        <span className={styles.legendLabel}>높음</span>
      </div>
    </div>
  );
}

function Row({
  time,
  row,
  maxWeight,
  showValues,
}: {
  time: string;
  row: Array<{ time: string; day: string; weight: number; value: number }>;
  maxWeight: number;
  showValues: boolean;
}) {
  return (
    <>
      <span className={styles.rowHead}>{TIME_LABEL[time] ?? time}</span>
      {row.map((c) => {
        const t = Math.max(0, Math.min(1, c.weight / maxWeight));
        return (
          <div
            key={c.day}
            className={styles.cell}
            style={{ backgroundColor: `color-mix(in srgb, var(--color-primary) ${Math.round(t * 100)}%, var(--color-primary-light))` }}
            title={`${c.day} ${TIME_LABEL[time] ?? time}: ${fmtInt(c.value)}`}
          >
            {showValues && (
              <span className={styles.cellVal} style={{ color: t > 0.55 ? "#fff" : "var(--color-text-body)" }}>
                {fmtInt(c.value)}
              </span>
            )}
          </div>
        );
      })}
    </>
  );
}
