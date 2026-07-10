import AudienceSection from "../components/landing/AudienceSection";
import FeaturesSection from "../components/landing/FeaturesSection";
import HeroSection from "../components/landing/HeroSection";
import LandingFooter from "../components/landing/LandingFooter";
import LandingHeader from "../components/landing/LandingHeader";
import RisingSection from "../components/landing/RisingSection";
import StatsSection from "../components/landing/StatsSection";
import styles from "./LandingPage.module.css";

/** 독립 레이아웃(사이드바 없음)의 서비스 랜딩 페이지. */
export default function LandingPage() {
  return (
    <div className={styles.page}>
      <LandingHeader />
      <main>
        <HeroSection />
        <FeaturesSection />
        <RisingSection />
        <AudienceSection />
        <StatsSection />
      </main>
      <LandingFooter />
    </div>
  );
}
