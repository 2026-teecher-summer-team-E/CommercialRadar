import ForecastChart from "../charts/ForecastChart";
import type { ForecastPoint } from "../charts/ForecastChart";
import { fmtPct, fmtInt } from "./format";
import styles from "./SurvivalCard.module.css";

interface SurvivalCardProps {
  /** 현재(첫) 생존율 %. */
  current: number | null;
  /** 전망(끝) 생존율 %. */
  forecast: number | null;
  /** Δ %p (전망 - 현재). */
  delta: number | null;
  points: ForecastPoint[];
  totalBusiness: number | null;
  closureRate: number | null;
  onExpand?: () => void;
}

/** 생존율 예측 카드. Figma 2262:3603 재현. */
export default function SurvivalCard({
  current,
  forecast,
  delta,
  points,
  totalBusiness,
  closureRate,
  onExpand,
}: SurvivalCardProps) {
  const hasChart = points.filter((p) => p.value != null).length >= 2;
  const deltaUp = (delta ?? 0) >= 0;

  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <div>
          <h3 className={styles.title}>생존율 예측</h3>
          <p className={styles.sub}>ML 향후 4분기 전망</p>
        </div>
        {onExpand && hasChart && (
          <button type="button" className={styles.expandBtn} onClick={onExpand} aria-label="생존율 예측 확대">
            ⤢
          </button>
        )}
      </div>

      <div className={styles.body}>
        <div className={styles.left}>
          <div className={styles.hero}>
            <span className={styles.heroNow}>{fmtPct(current, 0)}</span>
            <span className={styles.arrow}>→</span>
            <span className={styles.heroNext}>{fmtPct(forecast, 0)}</span>
          </div>
          {delta != null && (
            <span className={styles.deltaPill}>
              {deltaUp ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}%p · 4분기 후 전망
            </span>
          )}
        </div>

        <div className={styles.stats}>
          <div className={styles.statBox}>
            <span className={styles.statLabel}>현재 매장수</span>
            <span className={styles.statValue}>{fmtInt(totalBusiness)}</span>
          </div>
          <div className={styles.statBox}>
            <span className={styles.statLabel}>폐업률</span>
            <span className={styles.statValue}>{fmtPct(closureRate, 1)}</span>
          </div>
          <div className={styles.statBox}>
            <span className={styles.statLabel}>4분기 후 전망</span>
            <span className={styles.statValueAccent}>
              {fmtPct(forecast, 0)} {delta != null && `${deltaUp ? "▲" : "▼"}${Math.abs(delta).toFixed(1)}%p`}
            </span>
          </div>
        </div>
      </div>

      {hasChart ? (
        <div className={styles.chart}>
          <ForecastChart points={points} width={560} height={200} />
          <div className={styles.chartLegend}>
            <span className={styles.legendSolid}>실적</span>
            <span className={styles.legendDashed}>예측</span>
          </div>
        </div>
      ) : (
        <div className={styles.empty}>예측 데이터가 없어요.</div>
      )}
    </div>
  );
}
