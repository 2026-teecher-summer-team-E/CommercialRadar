import { useNavigate } from "react-router-dom";
import type { DistrictCompareItem } from "../../types";
import {
  fmtNum,
  fmtPct,
  fmtPopulation,
  closureRisk,
  closureRiskLabel,
} from "./format";
import styles from "./Leaderboard.module.css";

/** 순위(1-based)에 따른 뱃지 클래스. 1~3위만 강조. */
function badgeClass(rank: number): string {
  if (rank === 1) return `${styles.badge} ${styles.badgeGold}`;
  if (rank === 2) return `${styles.badge} ${styles.badgeSilver}`;
  if (rank === 3) return `${styles.badge} ${styles.badgeBronze}`;
  return styles.badge;
}

const RISK_CLASS = {
  low: styles.riskLow,
  mid: styles.riskMid,
  high: styles.riskHigh,
  none: styles.riskNone,
} as const;

/** 종합 리더보드 표. 행 클릭 시 상권 대시보드로 이동. */
export default function Leaderboard({ districts }: { districts: DistrictCompareItem[] }) {
  const navigate = useNavigate();

  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th className={styles.rankTh}>순위</th>
          <th className={styles.nameTh}>상권</th>
          <th>생존율</th>
          <th>폐업 위험</th>
          <th>유동인구</th>
          <th>종합 점수</th>
        </tr>
      </thead>
      <tbody>
        {districts.map((d, i) => {
          const rank = i + 1;
          const risk = closureRisk(d.closure_rate);
          return (
            <tr
              key={d.id}
              className={styles.row}
              onClick={() => navigate(`/dashboard/${d.id}`)}
              role="link"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  navigate(`/dashboard/${d.id}`);
                }
              }}
            >
              <td className={styles.rankCell}>
                <span className={badgeClass(rank)}>{rank}</span>
              </td>
              <td className={styles.nameCell}>{d.district_name}</td>
              <td className={`${styles.numCell} ${styles.survival}`}>{fmtPct(d.survival_rate)}</td>
              <td>
                <span className={`${styles.risk} ${RISK_CLASS[risk]}`}>{closureRiskLabel(risk)}</span>
              </td>
              <td className={styles.numCell}>{fmtPopulation(d.avg_population)}</td>
              <td
                className={`${styles.numCell} ${
                  d.district_score == null ? styles.scoreEmpty : styles.score
                }`}
              >
                {fmtNum(d.district_score, 1)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
