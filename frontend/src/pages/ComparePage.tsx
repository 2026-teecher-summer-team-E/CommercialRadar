import { useEffect, useMemo, useState } from "react";
import { commercialApi } from "../services/commercialApi";
import type {
  DistrictCompareResponse,
  RadarResponse,
  DistrictTimeSeriesResponse,
  CategoryRankingResponse,
} from "../types";
import RadarChartSvg from "../components/compare/RadarChartSvg";
import type { RadarSeries } from "../components/compare/RadarChartSvg";
import LineChartSvg from "../components/compare/LineChartSvg";
import type { LineSeries } from "../components/compare/LineChartSvg";
import Legend from "../components/compare/Legend";
import ExpandModal from "../components/compare/ExpandModal";
import {
  seriesColor,
  fmtNum,
  fmtPct,
  fmtPopulation,
  closureRiskLabel,
} from "../components/compare/format";
import styles from "./ComparePage.module.css";

type ModalKind = "radar" | "trend" | null;

interface CompareData {
  compare: DistrictCompareResponse;
  radars: RadarResponse[];
  timeSeries: DistrictTimeSeriesResponse[];
  ranking: CategoryRankingResponse | null;
}

const EXPAND_ICON = "⤢";

export default function ComparePage() {
  const [selectedIds] = useState<number[]>([1, 2, 3]);
  const [data, setData] = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [modal, setModal] = useState<ModalKind>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(false);

    Promise.all([
      commercialApi.compare(selectedIds),
      Promise.all(selectedIds.map((id) => commercialApi.radar(id))),
      Promise.all(selectedIds.map((id) => commercialApi.timeSeries(id))),
      selectedIds.length > 0 ? commercialApi.categoryRanking(selectedIds[0]) : Promise.resolve(null),
    ])
      .then(([compareRes, radarRes, tsRes, rankingRes]) => {
        if (!alive) return;
        setData({
          compare: compareRes.data,
          radars: radarRes.map((r) => r.data),
          timeSeries: tsRes.map((r) => r.data),
          ranking: rankingRes ? rankingRes.data : null,
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
  }, [selectedIds]);

  const districts = data?.compare.districts ?? [];
  const names = districts.map((d) => d.district_name);

  // 레이더: 모든 상권의 축 라벨은 동일하다고 가정, 첫 상권 축을 기준으로 사용.
  const radarAxes = useMemo(() => data?.radars[0]?.axes.map((a) => a.label) ?? [], [data]);
  const radarSeries: RadarSeries[] = useMemo(() => {
    if (!data) return [];
    return data.radars.map((r, i) => ({
      name: names[i] ?? `상권 ${i + 1}`,
      values: r.axes.map((a) => a.value),
    }));
  }, [data, names]);

  // 라인: 모든 상권 분기의 합집합을 정렬해 X축으로 사용.
  const trendLabels = useMemo(() => {
    if (!data) return [];
    const set = new Set<string>();
    data.timeSeries.forEach((ts) => ts.data.forEach((q) => set.add(q.year_quarter)));
    return Array.from(set).sort();
  }, [data]);

  const trendSeries: LineSeries[] = useMemo(() => {
    if (!data) return [];
    return data.timeSeries.map((ts, i) => {
      const byQuarter = new Map(ts.data.map((q) => [q.year_quarter, q.survival_rate]));
      return {
        name: names[i] ?? `상권 ${i + 1}`,
        points: trendLabels.map((label) => byQuarter.get(label) ?? null),
      };
    });
  }, [data, names, trendLabels]);

  if (loading) {
    return (
      <div className={styles.page}>
        <Header />
        <div className={styles.skeletonWrap}>
          <div className={styles.skeleton} />
          <div className={styles.skeleton} />
          <div className={styles.skeleton} />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className={styles.page}>
        <Header />
        <div className={styles.empty}>비교 데이터를 불러오지 못했어요. 잠시 후 다시 시도해주세요.</div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <Header />

      {/* 컨트롤 바 */}
      <div className={styles.controlBar}>
        <div className={styles.chips}>
          {districts.map((d, i) => (
            <span key={d.id} className={styles.chip}>
              <span className={styles.chipDot} style={{ background: seriesColor(i) }} />
              {d.district_name}
              <button type="button" className={styles.chipClose} aria-label={`${d.district_name} 제거`}>
                ×
              </button>
            </span>
          ))}
          <button type="button" className={styles.addChip}>
            + 상권 추가
          </button>
        </div>
        <div className={styles.selectors}>
          <button type="button" className={styles.selector}>
            2026년 1분기 ▾
          </button>
          <button type="button" className={styles.selector}>
            전체 업종 ▾
          </button>
        </div>
      </div>

      {/* 핵심 지표 비교표 */}
      <section className={styles.section}>
        <SectionTitle title="핵심 지표 비교" subtitle="상권별 대표 지표를 한눈에 비교합니다" />
        <div className={styles.card}>
          <MetricsTable districts={districts} />
        </div>
      </section>

      {/* 차트 2열 */}
      <section className={styles.chartsGrid}>
        <div className={styles.card}>
          <ChartHeader title="지표 레이더" onExpand={() => setModal("radar")} />
          {radarSeries.length > 0 && radarAxes.length >= 3 ? (
            <div className={styles.chartBody}>
              <RadarChartSvg axes={radarAxes} series={radarSeries} />
            </div>
          ) : (
            <div className={styles.empty}>레이더 데이터가 없어요.</div>
          )}
          <Legend names={names} />
        </div>

        <div className={styles.card}>
          <ChartHeader title="분기별 생존율 추이" onExpand={() => setModal("trend")} />
          {trendLabels.length > 0 ? (
            <div className={styles.chartBody}>
              <LineChartSvg labels={trendLabels} series={trendSeries} />
            </div>
          ) : (
            <div className={styles.empty}>추이 데이터가 없어요.</div>
          )}
          <Legend names={names} />
        </div>
      </section>

      {/* 업종별 추천 순위표 */}
      <section className={styles.section}>
        <SectionTitle
          title="업종별 추천 순위"
          subtitle={
            districts[0] ? `${districts[0].district_name} 기준 상위 업종` : "선택 상권 기준 상위 업종"
          }
        />
        <div className={styles.card}>
          <RankingTable ranking={data.ranking} />
        </div>
      </section>

      {/* 확대 모달 */}
      {modal === "radar" && radarAxes.length >= 3 && (
        <ExpandModal
          title="지표 레이더"
          subtitle="상권별 5개 축 비교"
          onClose={() => setModal(null)}
        >
          <div className={styles.modalChart}>
            <RadarChartSvg axes={radarAxes} series={radarSeries} size={420} />
            <Legend names={names} />
          </div>
          <RadarValueTable axes={radarAxes} series={radarSeries} />
        </ExpandModal>
      )}

      {modal === "trend" && trendLabels.length > 0 && (
        <ExpandModal
          title="분기별 생존율 추이"
          subtitle="상권별 생존율(%) 추이"
          onClose={() => setModal(null)}
        >
          <div className={styles.modalChartWide}>
            <LineChartSvg labels={trendLabels} series={trendSeries} width={760} height={360} />
            <Legend names={names} />
          </div>
        </ExpandModal>
      )}
    </div>
  );
}

function Header() {
  return (
    <div className={styles.header}>
      <div>
        <h1 className={styles.title}>상권 비교</h1>
        <p className={styles.subtitle}>여러 상권을 나란히 비교해 최적의 입지를 찾으세요</p>
      </div>
      <button type="button" className={styles.saveBtn}>
        리포트로 저장
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

function ChartHeader({ title, onExpand }: { title: string; onExpand: () => void }) {
  return (
    <div className={styles.chartHeader}>
      <h3 className={styles.chartTitle}>{title}</h3>
      <button type="button" className={styles.expandBtn} onClick={onExpand} aria-label={`${title} 확대`}>
        {EXPAND_ICON}
      </button>
    </div>
  );
}

/** 핵심 지표 비교표. 지표별 최고값 셀을 하이라이트. */
function MetricsTable({ districts }: { districts: DistrictCompareResponse["districts"] }) {
  // 각 지표에서 "최고(=가장 좋음)" 인덱스 계산. 폐업위험은 낮을수록 좋음.
  const bestIndex = (
    values: Array<number | null>,
    mode: "max" | "min",
  ): number => {
    let best = -1;
    let bestVal: number | null = null;
    values.forEach((v, i) => {
      if (v == null) return;
      if (bestVal == null || (mode === "max" ? v > bestVal : v < bestVal)) {
        bestVal = v;
        best = i;
      }
    });
    return best;
  };

  const scores = districts.map((d) => d.district_score);
  const survivals = districts.map((d) => d.survival_rate);
  const closures = districts.map((d) => d.closure_rate);
  const populations = districts.map((d) => d.avg_population);

  const rows = [
    {
      label: "종합 점수",
      best: bestIndex(scores, "max"),
      cells: districts.map((d) => fmtNum(d.district_score, 1)),
    },
    {
      label: "생존율",
      best: bestIndex(survivals, "max"),
      cells: districts.map((d) => fmtPct(d.survival_rate)),
    },
    {
      label: "폐업 위험",
      best: bestIndex(closures, "min"),
      cells: districts.map((d) => closureRiskLabel(d.closure_rate)),
    },
    {
      label: "유동인구",
      best: bestIndex(populations, "max"),
      cells: districts.map((d) => fmtPopulation(d.avg_population)),
    },
  ];

  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th className={styles.metricCol}>지표</th>
          {districts.map((d, i) => (
            <th key={d.id} className={styles.numCell}>
              <span className={styles.thDot} style={{ background: seriesColor(i) }} />
              {d.district_name}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label}>
            <td className={styles.metricCol}>{row.label}</td>
            {row.cells.map((cell, i) => (
              <td key={i} className={`${styles.numCell} ${i === row.best ? styles.bestCell : ""}`}>
                {cell}
                {i === row.best && <span className={styles.bestTag}>1위</span>}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** 레이더 확대 모달의 축별 값 테이블. 축마다 최고값 시리즈색 강조. */
function RadarValueTable({ axes, series }: { axes: string[]; series: RadarSeries[] }) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th className={styles.metricCol}>축</th>
          {series.map((s, i) => (
            <th key={i} className={styles.numCell}>
              <span className={styles.thDot} style={{ background: seriesColor(i) }} />
              {s.name}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {axes.map((axis, ai) => {
          const vals = series.map((s) => s.values[ai] ?? null);
          let best = -1;
          let bestVal: number | null = null;
          vals.forEach((v, i) => {
            if (v == null) return;
            if (bestVal == null || v > bestVal) {
              bestVal = v;
              best = i;
            }
          });
          return (
            <tr key={axis}>
              <td className={styles.metricCol}>{axis}</td>
              {vals.map((v, i) => (
                <td
                  key={i}
                  className={styles.numCell}
                  style={i === best ? { color: seriesColor(i), fontWeight: 700 } : undefined}
                >
                  {fmtNum(v, 0)}
                </td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** 업종별 추천 순위표. */
function RankingTable({ ranking }: { ranking: CategoryRankingResponse | null }) {
  if (!ranking || ranking.ranking.length === 0) {
    return <div className={styles.empty}>업종 순위 데이터가 없어요.</div>;
  }
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th className={styles.rankCol}>순위</th>
          <th className={styles.leftCell}>업종</th>
          <th className={styles.numCell}>생존율</th>
          <th className={styles.numCell}>점포수</th>
          <th className={styles.numCell}>점수</th>
        </tr>
      </thead>
      <tbody>
        {ranking.ranking.map((item) => (
          <tr key={`${item.rank}-${item.category_name ?? ""}`}>
            <td className={styles.rankCol}>{item.rank}</td>
            <td className={styles.leftCell}>{item.category_name ?? "-"}</td>
            <td className={styles.numCell}>{fmtPct(item.survival_rate)}</td>
            <td className={styles.numCell}>
              {item.total_business != null ? item.total_business.toLocaleString("ko-KR") : "-"}
            </td>
            <td className={styles.numCell}>{fmtNum(item.district_score, 1)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
