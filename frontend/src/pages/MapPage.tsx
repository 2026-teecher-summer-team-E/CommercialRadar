import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../lib/apiClient";
import { commercialApi } from "../services/commercialApi";
import SangkwonPanel from "../components/map/SangkwonPanel";
import SangkwonLayer from "../components/map/SangkwonLayer";
import {
  MOCK_PIN_POSITIONS,
  toScore,
  type DistrictDetail,
  type DistrictSearchResult,
  type DistrictSummary,
  type MapPin,
} from "../components/map/mapData";
import styles from "./MapPage.module.css";

const DEFAULT_DISTRICT_ID = 1;

/** 대표 상권 몇 개를 지도 핀으로 목업 배치할 때 쓰는 기본 후보 id. */
const FALLBACK_PIN_IDS = [1, 2, 3, 4, 5, 6, 7, 8];

export default function MapPage() {
  const navigate = useNavigate();
  const openProfile = (id: number) => navigate(`/dashboard/${id}`);
  const [selectedId, setSelectedId] = useState<number>(DEFAULT_DISTRICT_ID);
  const [summary, setSummary] = useState<DistrictSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<DistrictSearchResult[]>([]);

  // 선택 상권 상세(좌측 패널) 로드.
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(false);

    Promise.allSettled([
      commercialApi.getDistrict(selectedId) as Promise<{ data: DistrictDetail }>,
      commercialApi.radar(selectedId),
      commercialApi.heatmap(selectedId),
      commercialApi.timeSeries(selectedId),
    ])
      .then(([detailR, radarR, heatmapR, tsR]) => {
        if (!alive) return;
        if (detailR.status !== "fulfilled") {
          setError(true);
          setSummary(null);
          return;
        }
        setSummary({
          detail: detailR.value.data,
          radar: radarR.status === "fulfilled" ? radarR.value.data : null,
          heatmap: heatmapR.status === "fulfilled" ? heatmapR.value.data : null,
          timeSeries: tsR.status === "fulfilled" ? tsR.value.data : null,
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
  }, [selectedId]);

  // 검색: 입력 디바운스 후 위치 드롭다운 옵션 갱신.
  useEffect(() => {
    const keyword = query.trim();
    if (!keyword) {
      setOptions([]);
      return;
    }
    let alive = true;
    const t = setTimeout(() => {
      apiClient
        .get<DistrictSearchResult[]>("/api/commercial-districts/search", {
          params: { q: keyword },
        })
        .then((res) => {
          if (alive) setOptions(res.data);
        })
        .catch(() => {
          if (alive) setOptions([]);
        });
    }, 300);

    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [query]);

  // 드롭다운 옵션: 검색 결과 우선, 없으면 현재 상권만.
  const panelOptions = useMemo<DistrictSearchResult[]>(() => {
    if (options.length > 0) return options;
    if (summary?.detail) {
      const d = summary.detail;
      return [
        {
          id: d.id,
          district_name: d.district_name,
          type_name: d.type_name,
          gu_name: d.gu_name,
          dong_name: d.dong_name,
        },
      ];
    }
    return [];
  }, [options, summary]);

  // 지도 핀: 검색 결과(또는 정적 후보)에 목업 좌표를 매핑. 이름은 실데이터, 점수는 선택 상권만 실점수.
  const pins = useMemo<MapPin[]>(() => {
    const activeScore = toScore(
      summary?.detail?.latest_stats?.district_score ??
        (summary?.radar
          ? summary.radar.axes.reduce((a, x) => a + x.value, 0) /
            (summary.radar.axes.length || 1)
          : null),
    );

    const source: Array<{ id: number; name: string; score: number | null }> =
      options.length > 0
        ? options.map((o) => ({
            id: o.id,
            name: o.district_name,
            score: o.id === selectedId ? activeScore : mockScore(o.id),
          }))
        : FALLBACK_PIN_IDS.map((id) => ({
            id,
            name:
              id === selectedId && summary?.detail
                ? summary.detail.district_name
                : `상권 ${id}`,
            score: id === selectedId ? activeScore : mockScore(id),
          }));

    return source.slice(0, MOCK_PIN_POSITIONS.length).map((s, i) => ({
      id: s.id,
      name: s.name,
      score: s.score,
      x: MOCK_PIN_POSITIONS[i].x,
      y: MOCK_PIN_POSITIONS[i].y,
      active: s.id === selectedId,
    }));
  }, [options, summary, selectedId]);

  const activePin = pins.find((p) => p.active) ?? null;

  return (
    <div className={styles.page}>
      {/* 상단 검색 바 (앱 네비 사이드바는 AppLayout이 담당) */}
      <div className={styles.searchBar}>
        <span className={styles.searchIcon} aria-hidden>
          ⌕
        </span>
        <input
          className={styles.searchInput}
          type="text"
          placeholder="지역·상권·업종 검색…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className={styles.body}>
        <SangkwonPanel
          summary={summary}
          loading={loading}
          error={error}
          options={panelOptions}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onOpenProfile={openProfile}
        />
        <SangkwonLayer
          pins={pins}
          activeName={activePin?.name ?? summary?.detail?.district_name ?? null}
          activeScore={activePin?.score ?? null}
          onSearchArea={() => setQuery(query || "강남")}
          onSelectPin={setSelectedId}
          onOpenProfile={openProfile}
        />
      </div>
    </div>
  );
}

/** 좌표/점수 API가 없는 상권용 안정적 목업 점수(id 기반 결정적). */
function mockScore(id: number): number {
  return 60 + ((id * 7) % 30);
}
