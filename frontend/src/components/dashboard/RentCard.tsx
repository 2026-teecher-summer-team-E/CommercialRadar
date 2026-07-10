import { fmtNum } from "./format";
import styles from "./RentCard.module.css";

export interface RentBar {
  label: string;
  /** ㎡당 원 단위 임대료. */
  value: number | null;
}

interface RentCardProps {
  /** 대표 ㎡당 임대료(만원 환산 전, 원 단위). null 이면 "—". */
  perSqm: number | null;
  floorLabel: string | null;
  bars: RentBar[];
}

/** 원 → 만원 환산. */
function toMan(won: number | null): string {
  if (won == null) return "—";
  return (won / 10000).toFixed(1);
}

/** 임대료(m²당) 카드. Figma 재현: 큰 값 + 안내 태그 + 층별 미니 막대. */
export default function RentCard({ perSqm, floorLabel, bars }: RentCardProps) {
  const max = Math.max(1, ...bars.map((b) => b.value ?? 0));
  const hasBars = bars.some((b) => b.value != null);

  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <h3 className={styles.title}>임대료</h3>
        <span className={styles.sub}>{floorLabel ? `${floorLabel} 기준 · ㎡당 환산 임대료` : "㎡당 환산 임대료"}</span>
      </div>

      <div className={styles.big}>
        <span className={styles.num}>{toMan(perSqm)}</span>
        <span className={styles.unit}>만/㎡</span>
      </div>

      <span className={styles.tag}>서울 상위 11%</span>
      <p className={styles.note}>매출 대비 임대료 부담률 8.9% · 오피스형 평균 7.4%</p>

      {hasBars && (
        <>
          <p className={styles.barsLabel}>최근 4분기</p>
          <div className={styles.bars}>
            {bars.map((b, i) => (
              <div key={`${b.label}-${i}`} className={styles.barCol}>
                <span
                  className={i === bars.length - 1 ? styles.barTop : styles.bar}
                  style={{ height: `${Math.max(8, ((b.value ?? 0) / max) * 100)}%` }}
                  title={`${b.label}: ${fmtNum((b.value ?? 0) / 10000, 1)} 만/㎡`}
                />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
