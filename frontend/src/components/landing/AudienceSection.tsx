import { Link } from "react-router-dom";
import styles from "../../pages/LandingPage.module.css";
import { AUDIENCE_CARDS } from "./data";
import { ArrowRightIcon } from "./icons";

/** 나는 어떤 분석이 필요한가요?: 대상별 경로 카드. */
export default function AudienceSection() {
  return (
    <section className={styles.audience}>
      <div className={styles.container}>
        <div className={styles.sectionHead}>
          <p className={styles.eyebrow}>For You</p>
          <h2 className={styles.h2}>나는 어떤 분석이 필요한가요?</h2>
          <p className={styles.sectionSub}>목적에 맞는 경로로 바로 이동하세요.</p>
        </div>

        <div className={styles.audienceGrid}>
          {AUDIENCE_CARDS.map((card) => (
            <article key={card.title} className={styles.audienceCard}>
              <span className={styles.audienceTag}>{card.tag}</span>
              <h3 className={styles.audienceTitle}>{card.title}</h3>
              <p className={styles.audienceDesc}>{card.description}</p>
              <Link to={card.to} className={`${styles.btnPrimary} ${styles.audienceCta}`}>
                {card.cta}
                <ArrowRightIcon size={14} />
              </Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
