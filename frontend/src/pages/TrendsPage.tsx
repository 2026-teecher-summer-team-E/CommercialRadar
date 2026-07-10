import { useEffect, useMemo, useState } from "react";
import { commercialApi } from "../services/commercialApi";
import type {
  DistrictTimeSeriesResponse,
  CategoryRankingResponse,
  DistrictQuarterMetrics,
} from "../types";
import TrendLineChart from "../components/trends/TrendLineChart";
import {
  METRICS,
  METRIC_ORDER,
  fmtPct,
  fmtCount,
  type MetricKey,
} from "../components/trends/trendsFormat";
import styles from "./TrendsPage.module.css";

/** 상권 선택 드롭다운용 정적 목록. 검색 API가 없으므로 대표 상권 몇 개를 고정 제공한다. */
const DISTRICT_OPTIONS: { id: number; name: string }[] = [
  { id: 1, name: "역삼역" },
  { id: 2, name: "강남역" },
  { id: 3, name: "홍대입구역" },
  { id: 4, name: "성수역" },
  { id: 5, name: "여의도역" },
];

interface TrendData {
  timeSeries: DistrictTimeSeriesResponse;
  ranking: CategoryRankingResponse | null;
}

/** 분기 지표에서 선택 지표의 값을 뽑는다. population 은 total, 나머지는 동명 필드. */
function metricValue(q: DistrictQuarterMetrics, key: MetricKey): number | null {
  switch (key) {
    case "survival":
      return q.survival_rate;
    case "population":
      return q.population?.total ?? null;
    case "sales":
      return q.sales;
    default:
      return null;
  }
}

export default function TrendsPage() {
  const [districtId, setDistrictId] = useState<number>(1);
  const [metric, setMetric] = useState<MetricKey>("survival");
  const [data, setData] = useState<TrendData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(false);

    Promise.all([
      commercialApi.timeSeries(districtId),
      commercialApi.categoryRanking(districtId),
    ])
      .then(([tsRes, rankingRes]) => {
        if (!alive) return;
        setData({ timeSeries: tsRes.data, ranking: rankingRes.data });
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
  }, [districtId]);

  const quarters = useMemo(() => data?.timeSeries.data ?? [], [data]);
  const meta = METRICS[metric];

  const labels = useMemo(() => quarters.map((q) => q.year_quarter), [quarters]);
  const points = useMemo(
    () => quarters.map((q) => metricValue(q, metric)),
    [quarters, metric],
  );

  // 최근 분기 대비 증감(Δ): 값이 있는 마지막 두 지점 비교.
  const delta = useMemo(() => {
    const present = points
      .map((v, i) => ({ v, i }))
      .filter((p): p is { v: number; i: number } => p.v != null && !Number.isNaN(p.v));
    if (present.length < 2) return null;
    const last = present[present.length - 1];
    const prev = present[present.length - 2];
    return { current: last.v, diff: last.v - prev.v };
  }, [points]);

  const districtName =
    DISTRICT_OPTIONS.find((d) => d.id === districtId)?.name ?? `상권 ${districtId}`;

  const rising = data?.ranking?.ranking ?? [];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>트렌드</h1>
          <p className={styles.subtitle}>
            상권의 분기별 지표 변화와 떠오르는 업종을 한눈에 살펴보세요
          </p>
        </div>
        <label className={styles.districtSelect}>
          <span className={styles.districtLabel}>상권</span>
          <select
            className={styles.select}
            value={districtId}
            onChange={(e) => setDistrictId(Number(e.target.value))}
          >
            {DISTRICT_OPTIONS.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* 지표 추이 카드 */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <span className={styles.accentBar} />
          <div>
            <h2 className={styles.sectionHeading}>지표 추이</h2>
            <p className={styles.sectionSub}>{districtName}의 분기별 변화</p>
          </div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardHead}>
            <div className={styles.toggle} role="tablist" aria-label="지표 선택">
              {METRIC_ORDER.map((key) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={metric === key}
                  className={`${styles.toggleBtn} ${metric === key ? styles.toggleActive : ""}`}
                  onClick={() => setMetric(key)}
                >
                  {METRICS[key].label}
                </button>
              ))}
            </div>

            {delta && (
              <div className={styles.deltaBox}>
                <span className={styles.deltaCurrent}>{meta.format(delta.current)}</span>
                <span
                  className={`${styles.deltaTag} ${
                    delta.diff > 0
                      ? styles.deltaUp
                      : delta.diff < 0
                        ? styles.deltaDown
                        : styles.deltaFlat
                  }`}
                >
                  {delta.diff > 0 ? "▲" : delta.diff < 0 ? "▼" : "─"}{" "}
                  {meta.format(Math.abs(delta.diff))}
                </span>
                <span className={styles.deltaSub}>최근 분기 대비</span>
              </div>
            )}
          </div>

          {loading ? (
            <div className={styles.skeleton} />
          ) : error ? (
            <div className={styles.empty}>추이 데이터를 불러오지 못했어요. 잠시 후 다시 시도해주세요.</div>
          ) : labels.length === 0 ? (
            <div className={styles.empty}>표시할 분기 데이터가 없어요.</div>
          ) : (
            <div className={styles.chartBody}>
              <TrendLineChart labels={labels} points={points} meta={meta} />
            </div>
          )}
        </div>
      </section>

      {/* 떠오르는 업종 */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <span className={styles.accentBar} />
          <div>
            <h2 className={styles.sectionHeading}>떠오르는 업종</h2>
            <p className={styles.sectionSub}>{districtName}에서 생존율이 높은 상위 업종</p>
          </div>
        </div>

        <div className={styles.card}>
          {loading ? (
            <div className={styles.skeleton} />
          ) : error ? (
            <div className={styles.empty}>업종 데이터를 불러오지 못했어요.</div>
          ) : rising.length === 0 ? (
            <div className={styles.empty}>업종 순위 데이터가 없어요.</div>
          ) : (
            <ul className={styles.risingList}>
              {rising.slice(0, 6).map((item) => (
                <li
                  key={`${item.rank}-${item.category_name ?? ""}`}
                  className={styles.risingRow}
                >
                  <span className={styles.rankBadge}>{item.rank}</span>
                  <span className={styles.risingName}>{item.category_name ?? "-"}</span>
                  <span className={styles.risingMetric}>
                    <span className={styles.risingMetricLabel}>생존율</span>
                    <span className={styles.risingMetricValue}>{fmtPct(item.survival_rate)}</span>
                  </span>
                  <span className={styles.risingMetric}>
                    <span className={styles.risingMetricLabel}>점포수</span>
                    <span className={styles.risingMetricValue}>{fmtCount(item.total_business)}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
