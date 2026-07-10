import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { apiClient } from "../lib/apiClient";
import { commercialApi } from "../services/commercialApi";
import { mlApi } from "../services/mlApi";
import type {
  PopulationHeatmapResponse,
  DistrictTimeSeriesResponse,
  SurvivalForecastResponse,
} from "../types";
import type { ForecastPoint } from "../components/charts/ForecastChart";
import ScoreCard from "../components/dashboard/ScoreCard";
import SurvivalCard from "../components/dashboard/SurvivalCard";
import PopulationHeatmap from "../components/dashboard/PopulationHeatmap";
import AgeGenderCard from "../components/dashboard/AgeGenderCard";
import RentCard from "../components/dashboard/RentCard";
import type { RentBar } from "../components/dashboard/RentCard";
import BuzzGapCard from "../components/dashboard/BuzzGapCard";
import { DayNightCard, ForeignCard, PerCapitaCard, WeekendCard } from "../components/dashboard/StatCards";
import ExpandModal from "../components/dashboard/ExpandModal";
import { quarterShort } from "../components/dashboard/format";
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

/** 임대료 응답(전용 서비스 없음). avg_rent_per_sqm 는 원 단위. */
interface RentStat {
  floor_type: string | null;
  avg_rent_per_sqm: number | null;
}
interface RentResponse {
  district_id: number;
  year_quarter: string | null;
  rent_stats: RentStat[];
}

/** 화제성 Gap 응답(전용 서비스 없음). */
interface BuzzGapItem {
  district_name: string;
  gu_name: string | null;
  buzz_index: number;
  foot_pctl: number;
  spend_pctl: number;
  visit_gap: number;
  spend_gap: number;
}
interface BuzzGapResponse {
  period: string | null;
  source: string;
  items: BuzzGapItem[];
}

interface DashboardData {
  district: DistrictDetail | null;
  heatmap: PopulationHeatmapResponse | null;
  tsAge: DistrictTimeSeriesResponse | null;
  tsGender: DistrictTimeSeriesResponse | null;
  forecast: SurvivalForecastResponse | null;
  rent: RentResponse | null;
  buzz: BuzzGapResponse | null;
}

/** allSettled 결과에서 값만 안전 추출. */
function pick<T>(r: PromiseSettledResult<{ data: T }>): T | null {
  return r.status === "fulfilled" ? r.value.data : null;
}

/** 최신 분기의 population.breakdown[dimension] 추출 ({slot: value}). */
function lastBreakdown(ts: DistrictTimeSeriesResponse | null, dim: string): Record<string, number> | null {
  const rows = ts?.data ?? [];
  if (rows.length === 0) return null;
  const last = rows[rows.length - 1];
  const bd = last.population?.breakdown ?? null;
  return bd?.[dim] ?? null;
}

/** 백분위(0~100, 높을수록 상위) → 상위 % 표기값(작을수록 상위). */
function toTopPct(pctl: number | null | undefined): number | null {
  if (pctl == null) return null;
  return Math.max(1, 100 - Math.round(pctl));
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
      commercialApi.heatmap(id),
      commercialApi.timeSeries(id, { metrics: "population", breakdown: "age" }),
      commercialApi.timeSeries(id, { metrics: "population", breakdown: "gender" }),
      mlApi.survivalForecast(id),
      apiClient.get<RentResponse>(`/api/commercial-districts/${id}/rent`),
      apiClient.get<BuzzGapResponse>("/api/buzz-gap"),
    ])
      .then((results) => {
        if (!alive) return;
        const [districtR, heatmapR, tsAgeR, tsGenderR, forecastR, rentR, buzzR] = results;
        const district = pick<DistrictDetail>(districtR);
        if (!district) {
          setError(true);
          return;
        }
        setData({
          district,
          heatmap: pick<PopulationHeatmapResponse>(heatmapR),
          tsAge: pick<DistrictTimeSeriesResponse>(tsAgeR),
          tsGender: pick<DistrictTimeSeriesResponse>(tsGenderR),
          forecast: pick<SurvivalForecastResponse>(forecastR),
          rent: pick<RentResponse>(rentR),
          buzz: pick<BuzzGapResponse>(buzzR),
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
  const d = data?.district ?? null;
  const stats = d?.latest_stats ?? null;

  const forecastPoints: ForecastPoint[] = useMemo(() => {
    const fc = data?.forecast?.forecast ?? [];
    const pts: ForecastPoint[] = [];
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
      ? Number((forecastLast.survival_rate - stats.survival_rate).toFixed(1))
      : null;

  // 연령 분포(실데이터, dimension="age"). 성별 marginal 은 {남성:총,여성:총} 총량뿐이라
  // 연령×성별 세부는 DB 에 없다. 연령 막대는 성별 비율로 스케일해 토글을 표현한다.
  const ageDist = useMemo(() => lastBreakdown(data?.tsAge ?? null, "age") ?? null, [data]);
  const genderDist = useMemo(() => lastBreakdown(data?.tsGender ?? null, "gender") ?? null, [data]);
  const { femaleDist, maleDist } = useMemo(() => {
    if (!ageDist) return { femaleDist: null, maleDist: null };
    const f = genderDist?.["여성"] ?? 0;
    const m = genderDist?.["남성"] ?? 0;
    const tot = f + m;
    const fr = tot > 0 ? f / tot : 0.5;
    const scale = (r: number) => Object.fromEntries(Object.entries(ageDist).map(([k, v]) => [k, v * r]));
    return { femaleDist: scale(fr), maleDist: scale(1 - fr) };
  }, [ageDist, genderDist]);

  // 임대료 대표값 + 층별 막대.
  const rentBars: RentBar[] = useMemo(() => {
    const rows = data?.rent?.rent_stats ?? [];
    return rows.map((r) => ({ label: r.floor_type ?? "—", value: r.avg_rent_per_sqm }));
  }, [data]);
  const rentRep = useMemo<RentStat | null>(() => {
    const rows = data?.rent?.rent_stats ?? [];
    return rows.length > 0 ? rows[0] : null;
  }, [data]);

  // 화제성 Gap: 현재 상권명과 일치하는 항목.
  const buzzItem = useMemo<BuzzGapItem | null>(() => {
    const items = data?.buzz?.items ?? [];
    if (!d) return null;
    return items.find((it) => it.district_name === d.district_name) ?? null;
  }, [data, d]);

  // 유출/유입 진행바: 요일 주변분포 주중/주말 합으로 근사(없으면 74/26 목업).
  const flow = useMemo(() => {
    const byDay = data?.heatmap?.by_day ?? [];
    if (byDay.length === 0) return { weekday: 74, weekend: 26 };
    const weekdayKeys = new Set(["월", "화", "수", "목", "금"]);
    let wk = 0;
    let we = 0;
    byDay.forEach((s) => {
      const v = s.avg_population ?? 0;
      if (weekdayKeys.has(s.slot)) wk += v;
      else we += v;
    });
    const total = wk + we || 1;
    const weekday = Math.round((wk / total) * 100);
    return { weekday, weekend: 100 - weekday };
  }, [data]);

  const region = d ? [d.gu_name, d.dong_name].filter(Boolean).join(" ") || null : null;
  const regionLine = d
    ? [d.gu_name, d.dong_name, d.district_name].filter(Boolean).join(" ") || null
    : null;

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

  if (error || !data || !d) {
    return (
      <div className={styles.page}>
        <Header name={null} region={null} typeName={null} />
        <div className={styles.empty}>대시보드 데이터를 불러오지 못했어요. 잠시 후 다시 시도해주세요.</div>
      </div>
    );
  }

  const scoreBadges = [
    { label: "생존율", value: stats?.survival_rate != null ? Math.round(stats.survival_rate * 0.46) : 38 },
    { label: "유동인구", value: 27 },
    { label: "매출", value: 22 },
  ];

  return (
    <div className={styles.page}>
      <Header name={d.district_name} region={region} typeName={d.type_name} />

      {/* 상단 2열: 종합점수 + 생존율 예측 */}
      <section className={styles.topGrid}>
        <ScoreCard
          districtName={d.district_name}
          typeName={d.type_name}
          regionLine={regionLine}
          score={stats?.district_score ?? null}
          badges={scoreBadges}
          survivalRate={stats?.survival_rate ?? null}
          closureRate={stats?.closure_rate ?? null}
          avgPopulation={d.avg_population}
          weekdayPct={flow.weekday}
          weekendPct={flow.weekend}
        />

        <SurvivalCard
          current={stats?.survival_rate ?? null}
          forecast={forecastLast?.survival_rate ?? null}
          delta={forecastDelta}
          points={forecastPoints}
          totalBusiness={stats?.total_business ?? null}
          closureRate={stats?.closure_rate ?? null}
          onExpand={() => setModal("forecast")}
        />
      </section>

      {/* 유동인구 */}
      <section className={styles.section}>
        <SectionTitle title="유동인구" subtitle="누가, 언제 이 상권에 오는가" />
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <div>
              <h3 className={styles.cardTitle}>유동인구 시간·요일 패턴</h3>
              <p className={styles.cardSub}>시간대 × 요일 평균 유동인구</p>
            </div>
            {data.heatmap && data.heatmap.by_time.length > 0 && data.heatmap.by_day.length > 0 && (
              <button
                type="button"
                className={styles.expandBtn}
                onClick={() => setModal("heatmap")}
                aria-label="유동인구 확대"
              >
                ⤢
              </button>
            )}
          </div>
          {data.heatmap ? (
            <PopulationHeatmap byTime={data.heatmap.by_time} byDay={data.heatmap.by_day} />
          ) : (
            <div className={styles.empty}>유동인구 데이터가 없어요.</div>
          )}
        </div>

        <div className={styles.trioGrid}>
          <AgeGenderCard ageFemale={femaleDist} ageMale={maleDist} />
          <DayNightCard />
          <ForeignCard />
        </div>
      </section>

      {/* 매출·소비 */}
      <section className={styles.section}>
        <SectionTitle title="매출·소비" subtitle="고객은 얼마나, 어떻게 지갑을 여는가" />
        <div className={styles.duoGrid}>
          <PerCapitaCard />
          <WeekendCard />
        </div>
      </section>

      {/* 비용·리스크 */}
      <section className={styles.section}>
        <SectionTitle title="비용·리스크" subtitle="창업 전 반드시 확인할 비용과 신호" />
        <div className={styles.duoGrid}>
          <RentCard
            perSqm={rentRep?.avg_rent_per_sqm ?? null}
            floorLabel={rentRep?.floor_type ?? null}
            bars={rentBars}
          />
          <BuzzGapCard
            buzzTopPct={buzzItem ? Math.max(1, 100 - buzzItem.buzz_index) : null}
            footTopPct={toTopPct(buzzItem?.foot_pctl)}
            spendTopPct={toTopPct(buzzItem?.spend_pctl)}
            visitGap={buzzItem?.visit_gap ?? null}
            spendGap={buzzItem?.spend_gap ?? null}
          />
        </div>
      </section>

      <div className={styles.footerActions}>
        <button type="button" className={styles.reportBtn}>
          상세 리포트 생성
        </button>
      </div>

      {/* 확대 모달: 생존율 예측 */}
      {modal === "forecast" && (
        <ExpandModal
          title="생존율 예측"
          subtitle="ML 향후 4분기 전망"
          onClose={() => setModal(null)}
        >
          <div className={styles.modalChart}>
            <SurvivalCard
              current={stats?.survival_rate ?? null}
              forecast={forecastLast?.survival_rate ?? null}
              delta={forecastDelta}
              points={forecastPoints}
              totalBusiness={stats?.total_business ?? null}
              closureRate={stats?.closure_rate ?? null}
            />
          </div>
        </ExpandModal>
      )}

      {/* 확대 모달: 유동인구 히트맵 */}
      {modal === "heatmap" && data.heatmap && (
        <ExpandModal
          title="유동인구 시간·요일 패턴"
          subtitle="시간대 × 요일 평균 유동인구 상세"
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
