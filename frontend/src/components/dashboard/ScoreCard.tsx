import { fmtPct, fmtManUnit, closureRiskLabel, riskColor } from "./format";
import styles from "./ScoreCard.module.css";

export interface ScoreBadge {
  label: string;
  value: number | null;
}

interface ScoreCardProps {
  districtName: string;
  typeName: string | null;
  regionLine: string | null;
  /** 0~100 종합 점수. */
  score: number | null;
  /** 점수 구성요소 배지(안전존·유동인구·매출). value 없으면 목업 표기. */
  badges: ScoreBadge[];
  survivalRate: number | null;
  closureRate: number | null;
  avgPopulation: number | null;
  /** 유출 비율(주중) 0~100. */
  weekdayPct: number;
  /** 유입 비율(주말) 0~100. */
  weekendPct: number;
  onExpand?: () => void;
}

/** 상권명 앞 2글자(공백 제거). */
function initials(name: string): string {
  return name.replace(/\s/g, "").slice(0, 2) || "상권";
}

/**
 * 종합 점수 카드. Figma 2262:3601 재현.
 * 큰 점수 + 상위%, 점수구성 배지 3개, 파란 라운드 박스(상권 아이덴티티),
 * 지표 pill 3개, 성장 소label, 유출/유입 진행바.
 */
export default function ScoreCard({
  districtName,
  typeName,
  regionLine,
  score,
  badges,
  survivalRate,
  closureRate,
  avgPopulation,
  weekdayPct,
  weekendPct,
  onExpand,
}: ScoreCardProps) {
  const topPct = score != null ? Math.max(1, Math.round(100 - score)) : null;

  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <h3 className={styles.title}>종합 점수</h3>
        {onExpand && (
          <button type="button" className={styles.expandBtn} onClick={onExpand} aria-label="종합 점수 확대">
            ⤢
          </button>
        )}
      </div>

      <div className={styles.scoreRow}>
        <div className={styles.scoreBig}>
          <span className={styles.scoreNum}>{score != null ? Math.round(score) : "—"}</span>
          <span className={styles.scoreDenom}>/100</span>
        </div>
        {topPct != null && <span className={styles.topPill}>상위 {topPct}%</span>}
      </div>

      <span className={styles.constructLabel}>점수 구성</span>
      <div className={styles.badgeRow}>
        {badges.map((b) => (
          <span key={b.label} className={styles.badge}>
            {b.label} <strong>{b.value != null ? Math.round(b.value) : "—"}</strong>
          </span>
        ))}
      </div>

      <div className={styles.identity}>
        <div className={styles.avatar}>
          <span className={styles.avatarInitials}>{initials(districtName)}</span>
          <span className={styles.avatarSub}>{districtName}</span>
        </div>
        <div className={styles.identityBody}>
          <p className={styles.identityName}>{districtName}</p>
          <p className={styles.identityType}>{typeName ?? "상권"}</p>
          {regionLine && <p className={styles.identityRegion}>{regionLine}</p>}
          <span className={styles.identityLink}>산출 근거 보기 ›</span>
        </div>
      </div>

      <div className={styles.pillRow}>
        <div className={styles.pill}>
          <span className={styles.pillLabel}>생존율</span>
          <span className={styles.pillValue}>{fmtPct(survivalRate, 0)}</span>
        </div>
        <div className={styles.pill}>
          <span className={styles.pillLabelDot}>
            <i className={styles.dot} style={{ background: riskColor(closureRate) }} /> 폐업위험
          </span>
          <span className={styles.pillValue} style={{ color: riskColor(closureRate) }}>
            {closureRiskLabel(closureRate)}
          </span>
        </div>
        <div className={styles.pill}>
          <span className={styles.pillLabel}>유동인구</span>
          <span className={styles.pillValue}>{fmtManUnit(avgPopulation)}·일</span>
        </div>
      </div>

      <div className={styles.growthRow}>
        <span className={styles.growthTag}>{typeName ?? "상권"}</span>
        <span className={styles.peakTag}>피크 11~14시</span>
      </div>

      <div className={styles.flowLabels}>
        <span>주중 {Math.round(weekdayPct)}%</span>
        <span>주말 {Math.round(weekendPct)}%</span>
      </div>
      <div className={styles.flowBar}>
        <span className={styles.flowFill} style={{ width: `${weekdayPct}%` }} />
      </div>
    </div>
  );
}
