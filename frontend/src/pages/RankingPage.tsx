import { useEffect, useMemo, useState } from "react";
import { commercialApi } from "../services/commercialApi";
import type { DistrictCompareItem } from "../types";
import Leaderboard from "../components/ranking/Leaderboard";
import styles from "./RankingPage.module.css";

/** 리더보드에 채울 상권 id 목록. */
const DISTRICT_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

type SortKey = "score" | "survival" | "population";

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "score", label: "종합 점수" },
  { key: "survival", label: "생존율" },
  { key: "population", label: "유동인구" },
];

/** 정렬 기준별 비교 함수. null 은 항상 뒤로. 점수는 값이 있는 상권을 우선. */
function sortDistricts(districts: DistrictCompareItem[], key: SortKey): DistrictCompareItem[] {
  const value = (d: DistrictCompareItem): number | null => {
    if (key === "score") return d.district_score;
    if (key === "survival") return d.survival_rate;
    return d.avg_population;
  };
  return [...districts].sort((a, b) => {
    const va = value(a);
    const vb = value(b);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    return vb - va;
  });
}

export default function RankingPage() {
  const [districts, setDistricts] = useState<DistrictCompareItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  // district_score 가 null 인 시드가 많아 기본 정렬은 생존율 desc.
  const [sortKey, setSortKey] = useState<SortKey>("survival");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(false);

    // compare API는 한 번에 2~5개만 허용 → 5개씩 나눠 호출 후 병합.
    const chunks: number[][] = [];
    for (let i = 0; i < DISTRICT_IDS.length; i += 5) chunks.push(DISTRICT_IDS.slice(i, i + 5));

    Promise.all(chunks.map((c) => commercialApi.compare(c)))
      .then((resArr) => {
        if (!alive) return;
        const merged = new Map<number, DistrictCompareItem>();
        resArr.forEach((res) => res.data.districts.forEach((d) => merged.set(d.id, d)));
        setDistricts([...merged.values()]);
      })
      .catch(() => {
        if (alive) setError(true);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, []);

  const sorted = useMemo(() => sortDistricts(districts, sortKey), [districts, sortKey]);

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>상권 랭킹</h1>
        <p className={styles.subtitle}>
          생존율·유동인구·종합 점수를 기준으로 서울 주요 상권을 한눈에 비교하세요
        </p>
      </div>

      <div className={styles.controls}>
        <div className={styles.segment} role="tablist" aria-label="정렬 기준">
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              type="button"
              role="tab"
              aria-selected={sortKey === opt.key}
              className={`${styles.segBtn} ${sortKey === opt.key ? styles.segBtnActive : ""}`}
              onClick={() => setSortKey(opt.key)}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {!loading && !error && sorted.length > 0 && (
          <span className={styles.count}>{sorted.length}개 상권</span>
        )}
      </div>

      {loading ? (
        <div className={styles.skeletonWrap}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className={styles.skeleton} />
          ))}
        </div>
      ) : error ? (
        <div className={styles.state}>랭킹 데이터를 불러오지 못했어요. 잠시 후 다시 시도해주세요.</div>
      ) : sorted.length === 0 ? (
        <div className={styles.state}>표시할 상권이 없어요.</div>
      ) : (
        <div className={styles.card}>
          <Leaderboard districts={sorted} />
        </div>
      )}
    </div>
  );
}
