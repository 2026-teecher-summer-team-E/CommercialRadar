import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { apiClient } from "../lib/apiClient";
import { commercialApi } from "../services/commercialApi";
import { mlApi } from "../services/mlApi";
import type {
  RadarResponse,
  PopulationHeatmapResponse,
  DistrictTimeSeriesResponse,
  CategoryRankingResponse,
  SurvivalForecastResponse,
} from "../types";
import RadarChart from "../components/charts/RadarChart";
import ForecastChart from "../components/charts/ForecastChart";
import type { ForecastPoint } from "../components/charts/ForecastChart";
import PopulationHeatmap from "../components/dashboard/PopulationHeatmap";
import BusinessCategory from "../components/dashboard/BusinessCategory";
import ExpandModal from "../components/dashboard/ExpandModal";
import { fmtNum, fmtPct, fmtManUnit, fmtInt, closureRiskLabel, riskColor, quarterLabel, quarterShort } from "../components/dashboard/format";
import styles from "./DashboardPage.module.css";

/** getDistrict 응답(서비스가 제네릭 없이 any 반환) — 페이지 내부 로컬 타입. */
interface DistrictLatestStats {
  year_quarter: string | null;
  district_score: number | null;
  survival_rate: number | null;
  closure_rate: number | null;
  total_business: number | null;
}
interface DistrictDetail {
  id: number;
  district_name: string;
  type_name: string | null;
  gu_name: string | null;
  dong_name: string | null;
  avg_population: number | null;
  latest_stats: DistrictLatestStats | null;
}

/** 임대료 응답(전용 서비스 없음). */
interface RentStat {
  floor_type: string | null;
  avg_rent_per_sqm: number | null;
}
interface RentResponse {
  district_id: number;
  year_quarter: string | null;
  rent_stats: RentStat[];
}

interface DashboardData {
  district: DistrictDetail | null;
  radar: RadarResponse | null;
  heatmap: PopulationHeatmapResponse | null;
  timeSeries: DistrictTimeSeriesResponse | null;
  ranking: CategoryRankingResponse | null;
  forecast: SurvivalForecastResponse | null;
  rent: RentResponse | null;
}

const EXPAND_ICON = "⤢";

/** allSettled 결과에서 값만 안전 추출. */
function pick<T>(r: PromiseSettledResult<{ data: T }>): T | null {
  return r.status === "fulfilled" ? r.value.data : null;
}

export default function DashboardPage() {
  const { districtCode } = useParams();
  const id = useMemo(() => {
    const n = Number(districtCode);
    return districtCode && Number.isFinite(n) && n > 0 ? n : 1;
  }, [districtCode]);

  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [modal, setModal] = useState<"forecast" | "heatmap" | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(false);

    Promise.allSettled([
      commercialApi.getDistrict(id),
      commercialApi.radar(id),
      commercialApi.heatmap(id),
      commercialApi.timeSeries(id),
      commercialApi.categoryRanking(id),
      mlApi.survivalForecast(id),
      apiClient.get<RentResponse>(`/api/commercial-districts/${id}/rent`),
    ])
      .then((results) => {
        if (!alive) return;
        const [districtR, radarR, heatmapR, tsR, rankingR, forecastR, rentR] = results;
        const district = pick<DistrictDetail>(districtR);
        // 상세조차 못 불러오면 에러 상태로.
        if (!district) {
          setError(true);
          return;
        }
        setData({
          district,
          radar: pick<RadarResponse>(radarR),
          heatmap: pick<PopulationHeatmapResponse>(heatmapR),
          timeSeries: pick<DistrictTimeSeriesResponse>(tsR),
          ranking: pick<CategoryRankingResponse>(rankingR),
          forecast: pick<SurvivalForecastResponse>(forecastR),
          rent: pick<RentResponse>(rentR),
        });
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
  }, [id]);

  // ── 파생 값 ─────────────────────────────────────────────
  const stats = data?.district?.latest_stats ?? null;

  const forecastPoints: ForecastPoint[] = useMemo(() => {
    const fc = data?.forecast?.forecast ?? [];
    const pts: ForecastPoint[] = [];
    // 현재값(실적)을 앞에 붙여 실선→점선 연결.
    if (stats?.survival_rate != null && stats.year_quarter) {
      pts.push({ label: quarterShort(stats.year_quarter), value: stats.survival_rate, forecast: false });
    }
    fc.forEach((p) => {
      pts.push({ label: quarterShort(p.year_quarter), value: p.survival_rate, forecast: true });
    });
    return pts;
  }, [data, stats]);

  const forecastLast = data?.forecast?.forecast?.[data.forecast.forecast.length - 1] ?? null;
  const forecastDelta =
    stats?.survival_rate != null && forecastLast?.survival_rate != null
      ? forecastLast.survival_rate - stats.survival_rate
      : null;

  const trendSalesPoints = useMemo(() => {
    const rows = data?.timeSeries?.data ?? [];
    return rows.map((r) => ({ label: quarterShort(r.year_quarter), value: r.sales }));
  }, [data]);

  // 임대료: 대표값(전체/평균 우선, 없으면 첫 항목).
  const rentStat = useMemo<RentStat | null>(() => {
    const rows = data?.rent?.rent_stats ?? [];
    if (rows.length === 0) return null;
    return rows[0];
  }, [data]);

  // ── 상태 렌더 ───────────────────────────────────────────
  if (loading) {
    return (
      <div className={styles.page}>
        <Header name={null} region={null} typeName={null} />
        <div className={styles.skeletonWrap}>
          <div className={styles.skeleton} />
          <div className={styles.skeleton} />
          <div className={styles.skeleton} />
        </div>
      </div>
    );
  }

  if (error || !data || !data.district) {
    return (
      <div className={styles.page}>
        <Header name={null} region={null} typeName={null} />
        <div className={styles.empty}>대시보드 데이터를 불러오지 못했어요. 잠시 후 다시 시도해주세요.</div>
      </div>
    );
  }

  const d = data.district;
  const region = [d.gu_name, d.dong_name].filter(Boolean).join(" ") || null;

  return (
    <div className={styles.page}>
      <Header name={d.district_name} region={region} typeName={d.type_name} />

      {/* 상단: 종합점수 + 생존율 예측 */}
      <section className={styles.topGrid}>
        {/* 종합 점수 카드 */}
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <h3 className={styles.cardTitle}>종합 점수</h3>
          </div>
          <div className={styles.scoreRow}>
            <div className={styles.scoreBig}>
              <span className={styles.scoreNum}>{fmtNum(stats?.district_score, 0)}</span>
              <span className={styles.scoreDenom}>/100</span>
            </div>
            {stats?.district_score != null && (
              <span className={styles.scoreBadge}>상위 {Math.max(1, Math.round(100 - stats.district_score))}%</span>
            )}
          </div>

          {data.radar && data.radar.axes.length >= 3 ? (
            <div className={styles.radarWrap}>
              <RadarChart axes={data.radar.axes.map((a) => ({ label: a.label, value: a.value }))} size={200} />
            </div>
          ) : (
            <div className={styles.radarEmpty}>레이더 데이터 없음</div>
          )}

          <div className={styles.miniGrid}>
            <MiniStat label="생존율" value={fmtPct(stats?.survival_rate)} accent="var(--color-green)" />
            <MiniStat
              label="폐업 위험"
              value={closureRiskLabel(stats?.closure_rate)}
              accent={riskColor(stats?.closure_rate)}
            />
            <MiniStat label="유동인구" value={`${fmtManUnit(d.avg_population)}·일`} accent="var(--color-primary)" />
          </div>
        </div>

        {/* 생존율 예측 카드 */}
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <div>
              <h3 className={styles.cardTitle}>생존율을 예측</h3>
              <p className={styles.cardSub}>이 상권, 앞으로 어떻게 될까</p>
            </div>
            {forecastPoints.filter((p) => p.value != null).length >= 2 && (
              <button
                type="button"
                className={styles.expandBtn}
                onClick={() => setModal("forecast")}
                aria-label="생존율 예측 확대"
              >
                {EXPAND_ICON}
              </button>
            )}
          </div>

          <div className={styles.forecastHero}>
            <span className={styles.forecastNow}>{fmtPct(stats?.survival_rate, 0)}</span>
            <span className={styles.forecastArrow}>→</span>
            <span className={styles.forecastNext}>{fmtPct(forecastLast?.survival_rate, 0)}</span>
          </div>
          {forecastDelta != null && (
            <div className={styles.forecastDelta}>
              <span className={forecastDelta >= 0 ? styles.deltaUp : styles.deltaDown}>
                {forecastDelta >= 0 ? "▲" : "▼"} {Math.abs(forecastDelta).toFixed(1)}%p
              </span>
              <span className={styles.forecastDeltaSub}>
                {forecastLast?.confidence != null ? `신뢰도 ${Math.round(forecastLast.confidence * 100)}%` : "예측"}
              </span>
            </div>
          )}

          {forecastPoints.filter((p) => p.value != null).length >= 2 ? (
            <div className={styles.chartBody}>
              <ForecastChart points={forecastPoints} />
            </div>
          ) : (
            <div className={styles.empty}>예측 데이터가 없어요.</div>
          )}
        </div>
      </section>

      {/* 유동인구 */}
      <section className={styles.section}>
        <SectionTitle title="유동인구" subtitle="누가, 언제 이 상권에 오는가" />
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <div>
              <h3 className={styles.cardTitle}>유동인구 시간·요일 패턴</h3>
              <p className={styles.cardSub}>시간대·요일별 평균 유동인구</p>
            </div>
            {data.heatmap && (data.heatmap.by_time.length > 0 || data.heatmap.by_day.length > 0) && (
              <button
                type="button"
                className={styles.expandBtn}
                onClick={() => setModal("heatmap")}
                aria-label="유동인구 확대"
              >
                {EXPAND_ICON}
              </button>
            )}
          </div>
          {data.heatmap ? (
            <PopulationHeatmap byTime={data.heatmap.by_time} byDay={data.heatmap.by_day} />
          ) : (
            <div className={styles.empty}>유동인구 데이터가 없어요.</div>
          )}
        </div>
      </section>

      {/* 매출·소비 */}
      <section className={styles.section}>
        <SectionTitle title="매출·소비" subtitle="고객은 얼마나, 어떻게 지갑을 여는가" />
        <div className={styles.duoGrid}>
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>업종별 점포 분포</h3>
            <div className={styles.cardSpacer} />
            <BusinessCategory items={data.ranking?.ranking ?? []} />
          </div>
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>분기별 매출 추이</h3>
            <p className={styles.cardSub}>최근 분기 평균 매출 흐름</p>
            {trendSalesPoints.filter((p) => p.value != null).length >= 2 ? (
              <div className={styles.chartBody}>
                <ForecastChart points={trendSalesPoints.map((p) => ({ ...p, forecast: false }))} />
              </div>
            ) : (
              <div className={styles.empty}>매출 데이터가 없어요.</div>
            )}
          </div>
        </div>
      </section>

      {/* 비용·리스크 */}
      <section className={styles.section}>
        <SectionTitle title="비용·리스크" subtitle="창업 전 반드시 확인할 비용과 신호" />
        <div className={styles.duoGrid}>
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>임대료</h3>
            <p className={styles.cardSub}>{rentStat?.floor_type ? `${rentStat.floor_type} 기준` : "㎡당 평균 임대료"}</p>
            <div className={styles.costBig}>
              <span className={styles.costNum}>{fmtNum(rentStat?.avg_rent_per_sqm, 1)}</span>
              <span className={styles.costUnit}>만/㎡</span>
            </div>
            {data.rent?.rent_stats && data.rent.rent_stats.length > 1 && (
              <ul className={styles.rentList}>
                {data.rent.rent_stats.map((r, i) => (
                  <li key={`${r.floor_type ?? "floor"}-${i}`} className={styles.rentRow}>
                    <span>{r.floor_type ?? "—"}</span>
                    <span className={styles.rentVal}>{fmtNum(r.avg_rent_per_sqm, 1)} 만/㎡</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>운영 지표</h3>
            <div className={styles.cardSpacer} />
            <div className={styles.riskGrid}>
              <MiniStat label="점포 수" value={`${fmtInt(stats?.total_business)}개`} accent="var(--color-primary)" />
              <MiniStat label="폐업률" value={fmtPct(stats?.closure_rate)} accent={riskColor(stats?.closure_rate)} />
              <MiniStat label="기준 분기" value={quarterLabel(stats?.year_quarter)} accent="var(--color-muted)" />
            </div>
          </div>
        </div>
      </section>

      {/* 확대 모달: 생존율 예측 */}
      {modal === "forecast" && (
        <ExpandModal
          title="생존율 예측"
          subtitle={`${quarterLabel(stats?.year_quarter)} 기준 → 향후 전망`}
          onClose={() => setModal(null)}
        >
          <div className={styles.modalChart}>
            <ForecastChart points={forecastPoints} width={640} height={320} />
          </div>
          <table className={styles.modalTable}>
            <thead>
              <tr>
                <th className={styles.leftCell}>분기</th>
                <th className={styles.numCell}>생존율</th>
                <th className={styles.numCell}>신뢰도</th>
              </tr>
            </thead>
            <tbody>
              {(data.forecast?.forecast ?? []).map((p) => (
                <tr key={p.year_quarter}>
                  <td className={styles.leftCell}>{quarterLabel(p.year_quarter)}</td>
                  <td className={styles.numCell}>{fmtPct(p.survival_rate)}</td>
                  <td className={styles.numCell}>
                    {p.confidence != null ? `${Math.round(p.confidence * 100)}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ExpandModal>
      )}

      {/* 확대 모달: 유동인구 히트맵 */}
      {modal === "heatmap" && data.heatmap && (
        <ExpandModal
          title="유동인구 시간·요일 패턴"
          subtitle="시간대·요일별 평균 유동인구 상세"
          onClose={() => setModal(null)}
        >
          <PopulationHeatmap byTime={data.heatmap.by_time} byDay={data.heatmap.by_day} showValues />
        </ExpandModal>
      )}
    </div>
  );
}

function Header({
  name,
  region,
  typeName,
}: {
  name: string | null;
  region: string | null;
  typeName: string | null;
}) {
  return (
    <div className={styles.header}>
      <div>
        <h1 className={styles.title}>{name ?? "상권 프로필"}</h1>
        <p className={styles.subtitle}>
          {[region, typeName].filter(Boolean).join(" · ") || "상권 종합 리포트"}
        </p>
      </div>
      <button type="button" className={styles.reportBtn}>
        상세 리포트 생성
      </button>
    </div>
  );
}

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className={styles.sectionTitle}>
      <span className={styles.accentBar} />
      <div>
        <h2 className={styles.sectionHeading}>{title}</h2>
        {subtitle && <p className={styles.sectionSub}>{subtitle}</p>}
      </div>
    </div>
  );
}

function MiniStat({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className={styles.miniStat}>
      <span className={styles.miniLabel}>{label}</span>
      <span className={styles.miniValue} style={{ color: accent }}>
        {value}
      </span>
    </div>
  );
}
