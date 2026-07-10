import styles from "../../pages/MapPage.module.css";
import {
  DAY_LABELS,
  buildCongestionGrid,
  closureRiskLabel,
  congestionLevel,
  fmtPct,
  fmtPopulation,
  fmtSales,
  scoreGrade,
  toScore,
  type DistrictSearchResult,
  type DistrictSummary,
} from "./mapData";

interface SangkwonPanelProps {
  summary: DistrictSummary | null;
  loading: boolean;
  error: boolean;
  /** 위치 선택 드롭다운 옵션(검색 결과 또는 기본 목록). */
  options: DistrictSearchResult[];
  selectedId: number;
  onSelect: (id: number) => void;
  /** 상권 프로필(대시보드)로 이동. */
  onOpenProfile: (id: number) => void;
}

const FILTER_TYPES = ["전체", "한식", "카페", "편의점", "의류"] as const;

/** 지도 페이지 좌측 콘텐츠 패널: 위치 선택 + 필터 + 점수 + 지표 2x2 + 시간대별 혼잡도. */
export default function SangkwonPanel({
  summary,
  loading,
  error,
  options,
  selectedId,
  onSelect,
  onOpenProfile,
}: SangkwonPanelProps) {
  const detail = summary?.detail ?? null;
  const stats = detail?.latest_stats ?? null;

  // 점수: latest_stats.district_score 우선, 없으면 radar 축 평균 대용.
  const radarAvg = summary?.radar
    ? summary.radar.axes.reduce((a, x) => a + x.value, 0) / (summary.radar.axes.length || 1)
    : null;
  const score = toScore(stats?.district_score ?? radarAvg);
  const grade = scoreGrade(score);

  // 월평균매출: timeSeries 최신 분기 sales.
  const latestSales = summary?.timeSeries?.data?.length
    ? summary.timeSeries.data[summary.timeSeries.data.length - 1].sales
    : null;

  const population = detail?.avg_population ?? null;

  const locationLabel = detail
    ? [detail.gu_name, detail.dong_name].filter(Boolean).join(" · ") || detail.district_name
    : "";

  const { timeLabels, cells } = buildCongestionGrid(summary?.heatmap ?? null);

  return (
    <aside className={styles.panel}>
      {/* 위치 선택 드롭다운 */}
      <div className={styles.selectRow}>
        <span className={styles.pinIcon} aria-hidden>
          ◎
        </span>
        <select
          className={styles.select}
          value={selectedId}
          onChange={(e) => onSelect(Number(e.target.value))}
          aria-label="상권 위치 선택"
        >
          {options.length === 0 && detail && (
            <option value={detail.id}>
              {[detail.gu_name, detail.district_name].filter(Boolean).join(" ")}
            </option>
          )}
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {[o.gu_name, o.district_name].filter(Boolean).join(" ")}
            </option>
          ))}
        </select>
      </div>

      {/* 업종 필터(정적 칩) */}
      <div className={styles.filterRow}>
        <span className={styles.filterIcon} aria-hidden>
          ⚑
        </span>
        <span className={styles.filterLabel}>
          {detail?.type_name ?? "한식"}
        </span>
      </div>

      <div className={styles.filterChips}>
        {FILTER_TYPES.map((t) => (
          <span
            key={t}
            className={`${styles.filterChip} ${
              (detail?.type_name ?? "한식") === t ? styles.filterChipActive : ""
            }`}
          >
            {t}
          </span>
        ))}
      </div>

      {loading && <div className={styles.panelState}>불러오는 중…</div>}
      {error && !loading && (
        <div className={styles.panelState}>상권 정보를 불러오지 못했습니다.</div>
      )}

      {!loading && !error && detail && (
        <>
          {/* 상권명 + 점수 */}
          <div className={styles.districtHead}>
            <span className={styles.districtPin} aria-hidden>
              ◎
            </span>
            <span className={styles.districtName}>{locationLabel}</span>
            {detail.type_name && (
              <span className={styles.districtType}>{detail.type_name}</span>
            )}
          </div>

          <div className={styles.scoreBlock}>
            <span className={styles.scoreNum}>{score ?? "-"}</span>
            <span className={styles.scoreUnit}>점</span>
            <span className={`${styles.scoreGrade} ${styles[`grade_${grade.tone}`]}`}>
              {grade.label}
            </span>
          </div>

          <button
            type="button"
            onClick={() => onOpenProfile(detail.id)}
            style={{
              width: "100%",
              marginTop: "12px",
              padding: "11px",
              borderRadius: "var(--radius-sm)",
              background: "var(--color-primary)",
              color: "#fff",
              border: "none",
              fontWeight: 700,
              fontSize: "13px",
              fontFamily: "inherit",
              cursor: "pointer",
            }}
          >
            상세 프로필 보기 →
          </button>

          <div className={styles.divider} />

          {/* 지표 2x2 */}
          <div className={styles.metricGrid}>
            <Metric label="생존율" value={fmtPct(stats?.survival_rate)} />
            <Metric label="폐업위험" value={closureRiskLabel(stats?.closure_rate)} />
            <Metric label="월평균매출" value={fmtSales(latestSales)} />
            <Metric label="유동인구" value={fmtPopulation(population)} />
          </div>

          <div className={styles.divider} />

          {/* 시간대별 혼잡도 히트맵 */}
          <div className={styles.heatmapHead}>
            <span className={styles.heatmapTitle}>시간대별 혼잡도</span>
            <span className={styles.heatmapPeak}>{detail.type_name ?? "상권"} 피크</span>
          </div>

          {cells.length === 0 ? (
            <div className={styles.panelState}>혼잡도 데이터가 없습니다.</div>
          ) : (
            <div className={styles.heatmap}>
              <div className={styles.heatmapRow}>
                <span className={styles.heatmapCorner} />
                {DAY_LABELS.map((d) => (
                  <span key={d} className={styles.heatmapDay}>
                    {d}
                  </span>
                ))}
              </div>
              {cells.map((row, ri) => (
                <div key={timeLabels[ri] ?? ri} className={styles.heatmapRow}>
                  <span className={styles.heatmapTime}>{timeLabels[ri]}</span>
                  {row.map((intensity, ci) => (
                    <span
                      key={ci}
                      className={`${styles.heatCell} ${styles[`heat_${congestionLevel(intensity)}`]}`}
                      title={`${timeLabels[ri] ?? ""} ${DAY_LABELS[ci] ?? ""}`}
                    />
                  ))}
                </div>
              ))}

              <div className={styles.heatLegend}>
                <LegendItem level={3} label="85+" />
                <LegendItem level={2} label="65+" />
                <LegendItem level={1} label="40+" />
                <LegendItem level={0} label="~40" />
              </div>
            </div>
          )}
        </>
      )}
    </aside>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.metric}>
      <span className={styles.metricLabel}>{label}</span>
      <span className={styles.metricValue}>{value}</span>
    </div>
  );
}

function LegendItem({ level, label }: { level: 0 | 1 | 2 | 3; label: string }) {
  return (
    <span className={styles.legendItem}>
      <span className={`${styles.legendSwatch} ${styles[`heat_${level}`]}`} />
      {label}
    </span>
  );
}
