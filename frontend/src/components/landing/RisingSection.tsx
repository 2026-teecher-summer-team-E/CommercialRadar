import styles from "../../pages/LandingPage.module.css";
import { LATEST_REPORTS, RISING_DISTRICTS, TREND_INDUSTRIES } from "./data";
import { DownloadIcon } from "./icons";

/** 지금 이 순간, 뜨는 상권: 급상승 상권 / 트렌드 업종 / 최신 리포트. */
export default function RisingSection() {
  return (
    <section className={styles.rising}>
      <div className={styles.container}>
        <div className={styles.sectionHead}>
          <h2 className={styles.h2}>지금 이 순간, 뜨는 상권</h2>
          <p className={styles.sectionSub}>
            공공데이터와 카드사 매출 데이터 기반으로 매주 업데이트됩니다.
          </p>
        </div>

        <div className={styles.risingGrid}>
          <div className={styles.panel}>
            <h3 className={styles.panelTitle}>이번 주 급상승 상권 Top 5</h3>
            <ol className={styles.rankList}>
              {RISING_DISTRICTS.map((item, i) => (
                <li key={item.name} className={styles.rankRow}>
                  <span className={styles.rankNo}>{i + 1}</span>
                  <div className={styles.rankBody}>
                    <div className={styles.rankLine}>
                      <span className={styles.rankName}>{item.name}</span>
                      <span className={styles.rankDelta}>{item.delta}</span>
                    </div>
                    <div className={styles.rankSub}>{item.sub}</div>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <div className={styles.panel}>
            <h3 className={styles.panelTitle}>요즘 창업 트렌드 업종</h3>
            <ol className={styles.rankList}>
              {TREND_INDUSTRIES.map((item, i) => (
                <li key={item.name} className={styles.rankRow}>
                  <span className={styles.rankNo}>{i + 1}</span>
                  <div className={styles.rankBody}>
                    <div className={styles.rankLine}>
                      <span className={styles.rankName}>{item.name}</span>
                      <span className={styles.rankDelta}>{item.delta}</span>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <div className={styles.panel}>
            <h3 className={styles.panelTitle}>최신 리포트</h3>
            <ul className={styles.reportList}>
              {LATEST_REPORTS.map((report) => (
                <li key={report.title} className={styles.reportItem}>
                  <div className={styles.reportTop}>
                    <span className={styles.reportTitle}>{report.title}</span>
                    {report.hot && <span className={styles.hotBadge}>HOT</span>}
                  </div>
                  <div className={styles.reportMeta}>
                    <span className={styles.reportDate}>{report.meta}</span>
                    <button type="button" className={styles.downloadLink}>
                      <DownloadIcon size={10} />
                      다운로드
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
