import { Link } from "react-router-dom";
import styles from "../../pages/LandingPage.module.css";
import { RadarIcon } from "./icons";

/** 랜딩 자체 상단 헤더 (사이드바 없는 독립 레이아웃). */
export default function LandingHeader() {
  return (
    <header className={styles.header}>
      <Link to="/landing" className={styles.brand}>
        <span className={styles.brandMark}>
          <RadarIcon size={14} />
        </span>
        상권레이더
      </Link>
      <div className={styles.headerActions}>
        <Link to="/sign-in" className={styles.loginLink}>
          로그인
        </Link>
        <Link to="/" className={styles.btnPrimary}>
          시작하기
        </Link>
      </div>
    </header>
  );
}
