import styles from "../../pages/LandingPage.module.css";
import { RadarIcon } from "./icons";

/** 다크 푸터. */
export default function LandingFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.footerInner}>
        <div className={styles.footerBrand}>
          <span className={styles.footerBrandMark}>
            <RadarIcon size={12} />
          </span>
          상권레이더
        </div>
        <p className={styles.footerText}>
          공공데이터포털 · 서울 열린데이터광장 기반 분석 서비스
        </p>
        <p className={styles.footerCopy}>© 2026 District Pulse. All rights reserved.</p>
      </div>
    </footer>
  );
}
