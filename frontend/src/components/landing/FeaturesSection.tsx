import { Link } from "react-router-dom";
import styles from "../../pages/LandingPage.module.css";
import { FEATURE_CARDS } from "./data";
import { ArrowRightIcon, CheckIcon } from "./icons";

/** 특징 3분할 섹션: 창업 결정에 필요한 모든 데이터. */
export default function FeaturesSection() {
  return (
    <section className={styles.features}>
      <div className={styles.container}>
        <div className={styles.sectionHead}>
          <h2 className={styles.h2}>창업 결정에 필요한 모든 데이터, 한 곳에</h2>
          <p className={styles.sectionSub}>
            텍스트 보고서가 아닌 인터랙티브 시각화로, 데이터를 직접 탐색하세요.
          </p>
        </div>

        <div className={styles.featureGrid}>
          {FEATURE_CARDS.map((card) => (
            <article key={card.title} className={styles.featureCard}>
              <h3 className={styles.featureTitle}>{card.title}</h3>
              <p className={styles.featureDesc}>{card.description}</p>
              <ul className={styles.checkList}>
                {card.items.map((item) => (
                  <li key={item} className={styles.checkItem}>
                    <CheckIcon size={13} className={styles.checkIcon} />
                    {item}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>

        <div className={styles.centerCta}>
          <Link to="/" className={`${styles.btnPrimary} ${styles.ctaLarge}`}>
            지금 바로 분석해보기
            <ArrowRightIcon size={16} />
          </Link>
        </div>
      </div>
    </section>
  );
}
