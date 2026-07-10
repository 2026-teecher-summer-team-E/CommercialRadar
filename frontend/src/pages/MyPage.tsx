import { useEffect, useState } from "react";
import type {
  UserMe,
  UserStats,
  ReportListItem,
  InterestDistrict,
} from "../types";
import { meApi } from "../services/meApi";
import { reportsApi } from "../services/reportsApi";
import { interestApi } from "../services/interestApi";
import { formatJoinDate, initialOf } from "../components/mypage/format";
import ReportCard from "../components/mypage/ReportCard";
import InterestCard from "../components/mypage/InterestCard";
import EmptyState from "../components/mypage/EmptyState";
import listStyles from "../components/mypage/mypage.module.css";
import styles from "./MyPage.module.css";

type TabKey = "reports" | "interests" | "shared";

const REPORTS_LIMIT = 20;

export default function MyPage() {
  const [user, setUser] = useState<UserMe | null>(null);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [interests, setInterests] = useState<InterestDistrict[]>([]);
  const [interestsLoaded, setInterestsLoaded] = useState(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [tab, setTab] = useState<TabKey>("reports");
  const [busyId, setBusyId] = useState<number | null>(null);

  // 마운트 시 me / stats / reports 병렬 fetch
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(false);

    Promise.allSettled([meApi.me(), meApi.stats(), reportsApi.list({ page: 1, limit: REPORTS_LIMIT })])
      .then(([meRes, statsRes, reportsRes]) => {
        if (!alive) return;
        if (meRes.status === "fulfilled") setUser(meRes.value.data);
        if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
        if (reportsRes.status === "fulfilled") setReports(reportsRes.value.data.reports ?? []);
        // me 조회 실패는 페이지가 성립하지 않으므로 에러 처리
        if (meRes.status === "rejected") setError(true);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, []);

  // 관심 상권 탭 최초 진입 시 lazy fetch
  useEffect(() => {
    if (tab !== "interests" || interestsLoaded) return;
    let alive = true;
    interestApi
      .list()
      .then((r) => {
        if (alive) setInterests(r.data ?? []);
      })
      .catch(() => {
        /* 방어적: 실패해도 빈 상태 유지 */
      })
      .finally(() => {
        if (alive) setInterestsLoaded(true);
      });
    return () => {
      alive = false;
    };
  }, [tab, interestsLoaded]);

  const handleShare = (id: number) => {
    setBusyId(id);
    reportsApi
      .share(id)
      .catch(() => {
        /* 공유 실패는 조용히 무시 */
      })
      .finally(() => setBusyId(null));
  };

  const handleRemove = (id: number) => {
    setBusyId(id);
    const prev = reports;
    setReports((rs) => rs.filter((r) => r.id !== id)); // 낙관적 제거
    reportsApi
      .remove(id)
      .then(() => {
        setStats((s) =>
          s ? { ...s, saved_reports: Math.max(0, s.saved_reports - 1) } : s,
        );
      })
      .catch(() => {
        setReports(prev); // 롤백
      })
      .finally(() => setBusyId(null));
  };

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.state}>불러오는 중…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.page}>
        <div className={styles.state}>
          정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
        </div>
      </div>
    );
  }

  const name = user?.name ?? "게스트";
  const savedCount = stats?.saved_reports ?? reports.length;
  const interestCount = stats?.interest_districts ?? 0;
  const sharedCount = stats?.shared_reports ?? 0;

  const tabs: { key: TabKey; label: string; count: number }[] = [
    { key: "reports", label: "저장된 리포트", count: savedCount },
    { key: "interests", label: "관심 상권", count: interestCount },
    { key: "shared", label: "공유된 리포트", count: sharedCount },
  ];

  return (
    <div className={styles.page}>
      {/* 1. 페이지 타이틀 */}
      <header className={styles.header}>
        <h1 className={styles.title}>마이페이지</h1>
        <p className={styles.subtitle}>
          저장한 리포트와 관심 상권을 관리하세요
        </p>
      </header>

      {/* 2. 프로필 히어로 카드 */}
      <section className={styles.hero}>
        <div className={styles.heroTop}>
          <span className={styles.avatar} aria-hidden="true">
            {initialOf(name)}
          </span>
          <div className={styles.heroInfo}>
            <div className={styles.heroNameRow}>
              <span className={styles.heroName}>{name}</span>
              <span
                className={
                  user?.is_company ? styles.badgeCompany : styles.badgeNormal
                }
              >
                {user?.is_company ? "기업 회원" : "일반 회원"}
              </span>
            </div>
            <p className={styles.heroEmail}>{user?.email ?? "이메일 미등록"}</p>
            <p className={styles.heroJoined}>
              {formatJoinDate(user?.created_at)}
            </p>
          </div>
          <button type="button" className={styles.settingsBtn}>
            계정 설정
          </button>
        </div>

        <div className={styles.statsRow}>
          <div className={styles.statCell}>
            <span className={styles.statNum}>{savedCount}</span>
            <span className={styles.statLabel}>저장 리포트</span>
          </div>
          <span className={styles.statDivider} aria-hidden="true" />
          <div className={styles.statCell}>
            <span className={styles.statNum}>{interestCount}</span>
            <span className={styles.statLabel}>관심 상권</span>
          </div>
          <span className={styles.statDivider} aria-hidden="true" />
          <div className={styles.statCell}>
            <span className={styles.statNum}>{sharedCount}</span>
            <span className={styles.statLabel}>공유한 리포트</span>
          </div>
        </div>
      </section>

      {/* 3. 탭 (세그먼트 컨트롤) */}
      <div className={styles.segment} role="tablist">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            className={`${styles.segBtn} ${tab === t.key ? styles.segBtnActive : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
            <span className={styles.segCount}>{t.count}</span>
          </button>
        ))}
      </div>

      {/* 4/5. 탭 콘텐츠 */}
      <section className={styles.tabContent}>
        {tab === "reports" &&
          (reports.length > 0 ? (
            <ul className={listStyles.list}>
              {reports.map((r, i) => (
                <ReportCard
                  key={r.id}
                  report={r}
                  index={i}
                  onShare={handleShare}
                  onRemove={handleRemove}
                  busy={busyId === r.id}
                />
              ))}
            </ul>
          ) : (
            <EmptyState
              title="저장된 리포트가 없어요"
              description="상권 분석 결과를 리포트로 저장하면 여기에서 모아볼 수 있습니다."
            />
          ))}

        {tab === "interests" &&
          (!interestsLoaded ? (
            <div className={styles.state}>불러오는 중…</div>
          ) : interests.length > 0 ? (
            <ul className={listStyles.list}>
              {interests.map((item, i) => (
                <InterestCard key={item.id} item={item} index={i} />
              ))}
            </ul>
          ) : (
            <EmptyState
              title="관심 상권이 없어요"
              description="관심 있는 상권을 저장하면 변화를 빠르게 확인할 수 있습니다."
            />
          ))}

        {tab === "shared" && (
          <EmptyState
            title="공유된 리포트가 없어요"
            description="리포트를 공유하면 공유 링크와 함께 이곳에 표시됩니다."
          />
        )}
      </section>
    </div>
  );
}
