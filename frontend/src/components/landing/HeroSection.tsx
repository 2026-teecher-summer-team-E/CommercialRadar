import { Link } from "react-router-dom";
import styles from "../../pages/LandingPage.module.css";
import { POPULAR_SEARCHES } from "./data";
import { SearchIcon } from "./icons";

/** 히어로: 지도 배경 + 헤드라인 + 검색바 + 인기 검색어. */
export default function HeroSection() {
  return (
    <section className={styles.hero}>
      <div className={styles.heroGrid} aria-hidden="true" />
      <div className={styles.heroInner}>
        <h1 className={styles.heroTitle}>
          실패 없는 창업의 시작,
          <br />
          <span className={styles.heroTitleAccent}>데이터로 보는 진짜 상권</span>
        </h1>
        <p className={styles.heroSub}>
          원하는 지역만 검색하세요. 유동인구부터 생존율, 매출 예측까지 한눈에 확인합니다.
        </p>

        <div className={styles.searchBar}>
          <input
            className={styles.searchInput}
            type="text"
            placeholder="지역명과 원하는 상권을 입력해 보세요!"
            aria-label="상권 검색"
          />
          <Link to="/" className={`${styles.btnPrimary} ${styles.searchBtn}`}>
            <SearchIcon size={15} />
            상권 분석하기
          </Link>
        </div>

        <div className={styles.popular}>
          <span className={styles.popularLabel}>인기 검색:</span>
          {POPULAR_SEARCHES.map((term) => (
            <Link key={term} to="/" className={styles.popularChip}>
              {term}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
