import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import IngestionConsole from "../components/admin/IngestionConsole";
import styles from "./AdminPage.module.css";

/** 시스템 상태 요약 카드 데이터 (placeholder — 실 지표 연동 전). */
const STATUS_CARDS: {
  label: string;
  value: string;
  hint: string;
  ok?: boolean;
}[] = [
  { label: "API 상태", value: "정상", hint: "GET /health", ok: true },
  { label: "데이터베이스", value: "연결됨", hint: "PostgreSQL / PostGIS", ok: true },
  { label: "인제스천 트리거", value: "수동", hint: "POST /admin/data" },
  { label: "관측성", value: "ingestion_run", hint: "실행 이력 테이블" },
];

/** 관리 콘솔. isAdmin 사용자만 접근 가능(데이터 인제스천 수동 트리거). */
export default function AdminPage() {
  const { user } = useAuth();

  if (!user?.isAdmin) {
    return (
      <div className={styles.page}>
        <div className={styles.denied}>
          <h1 className={styles.deniedTitle}>접근 권한이 없습니다</h1>
          <p className={styles.deniedText}>
            이 페이지는 관리자 전용입니다. 권한이 필요하면 담당자에게
            문의하세요.
          </p>
          <Link to="/" className={styles.homeLink}>
            홈으로 돌아가기
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>관리 콘솔</h1>
        <p className={styles.subtitle}>
          데이터 수집 파이프라인을 수동으로 실행하고 시스템 상태를 확인하세요
        </p>
      </header>

      <section className={styles.statusRow}>
        {STATUS_CARDS.map((c) => (
          <div key={c.label} className={styles.statusCard}>
            <span className={styles.statusLabel}>{c.label}</span>
            <span
              className={`${styles.statusValue} ${c.ok ? styles.statusValueOk : ""}`}
            >
              {c.value}
            </span>
            <span className={styles.statusHint}>{c.hint}</span>
          </div>
        ))}
      </section>

      <IngestionConsole />
    </div>
  );
}
