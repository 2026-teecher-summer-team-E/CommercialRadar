import styles from "../../pages/LandingPage.module.css";
import { DATA_PARTNERS, STATS } from "./data";

/** 통계 숫자 스트립 + 데이터 파트너. */
export default function StatsSection() {
  return (
    <section className={styles.stats}>
      <div className={styles.container}>
        <div className={styles.statGrid}>
          {STATS.map((stat) => (
            <div key={stat.label} className={styles.statCell}>
              <div className={styles.statValue}>{stat.value}</div>
              <div className={styles.statLabel}>{stat.label}</div>
              <div className={styles.statNote}>{stat.note}</div>
            </div>
          ))}
        </div>

        <div className={styles.partners}>
          <p className={styles.partnersLabel}>신뢰할 수 있는 데이터 파트너</p>
          <div className={styles.partnerChips}>
            {DATA_PARTNERS.map((partner) => (
              <span key={partner} className={styles.partnerChip}>
                {partner}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
