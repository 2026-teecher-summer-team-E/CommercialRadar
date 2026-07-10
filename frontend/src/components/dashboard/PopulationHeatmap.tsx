import type { HeatmapSlot } from "../../types";
import { fmtInt } from "./format";
import styles from "./PopulationHeatmap.module.css";

interface PopulationHeatmapProps {
  byTime: HeatmapSlot[];
  byDay: HeatmapSlot[];
  /** true면 셀에 값을 함께 표시(모달 상세용). */
  showValues?: boolean;
}

/** 값 배열의 최대치로 0~1 정규화한 강도. */
function intensity(value: number | null, max: number): number {
  if (value == null || max <= 0) return 0;
  return Math.max(0, Math.min(1, value / max));
}

/** 유동인구 시간대/요일 주변분포를 두 개의 1D 히트 스트립으로 표현. */
export default function PopulationHeatmap({ byTime, byDay, showValues = false }: PopulationHeatmapProps) {
  const timeMax = Math.max(0, ...byTime.map((s) => s.avg_population ?? 0));
  const dayMax = Math.max(0, ...byDay.map((s) => s.avg_population ?? 0));

  const peakTime = byTime.reduce<HeatmapSlot | null>(
    (best, s) => ((s.avg_population ?? 0) > (best?.avg_population ?? -1) ? s : best),
    null,
  );
  const peakDay = byDay.reduce<HeatmapSlot | null>(
    (best, s) => ((s.avg_population ?? 0) > (best?.avg_population ?? -1) ? s : best),
    null,
  );

  const renderStrip = (slots: HeatmapSlot[], max: number) => (
    <div className={styles.strip}>
      {slots.map((s) => {
        const t = intensity(s.avg_population, max);
        return (
          <div key={s.slot} className={styles.cellWrap}>
            <div
              className={styles.cell}
              style={{ backgroundColor: `color-mix(in srgb, var(--color-primary) ${Math.round(t * 100)}%, var(--color-primary-light))` }}
              title={`${s.slot}: ${fmtInt(s.avg_population)}`}
            >
              {showValues && s.avg_population != null && (
                <span className={styles.cellVal} style={{ color: t > 0.55 ? "#fff" : "var(--color-text-body)" }}>
                  {fmtInt(s.avg_population)}
                </span>
              )}
            </div>
            <span className={styles.slotLabel}>{s.slot}</span>
          </div>
        );
      })}
    </div>
  );

  const hasTime = byTime.length > 0;
  const hasDay = byDay.length > 0;

  if (!hasTime && !hasDay) {
    return <div className={styles.empty}>유동인구 데이터가 없어요.</div>;
  }

  return (
    <div className={styles.wrap}>
      {hasTime && (
        <div className={styles.group}>
          <div className={styles.groupHead}>
            <span className={styles.groupTitle}>시간대별</span>
            {peakTime && (
              <span className={styles.peak}>
                피크 <strong>{peakTime.slot}</strong>
              </span>
            )}
          </div>
          {renderStrip(byTime, timeMax)}
        </div>
      )}
      {hasDay && (
        <div className={styles.group}>
          <div className={styles.groupHead}>
            <span className={styles.groupTitle}>요일별</span>
            {peakDay && (
              <span className={styles.peak}>
                피크 <strong>{peakDay.slot}</strong>
              </span>
            )}
          </div>
          {renderStrip(byDay, dayMax)}
        </div>
      )}
    </div>
  );
}
