import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../lib/apiClient";
import { commercialApi } from "../services/commercialApi";
import SangkwonPanel from "../components/map/SangkwonPanel";
import LeafletMap from "../components/map/LeafletMap";
import {
  toScore,
  type DistrictDetail,
  type DistrictSearchResult,
  type DistrictSummary,
} from "../components/map/mapData";
import type { DistrictGeo } from "../types";
import styles from "./MapPage.module.css";

const DEFAULT_DISTRICT_ID = 1;

export default function MapPage() {
  const navigate = useNavigate();
  const openProfile = useCallback((id: number) => navigate(`/dashboard/${id}`), [navigate]);

  const [selectedId, setSelectedId] = useState<number>(DEFAULT_DISTRICT_ID);
  const [summary, setSummary] = useState<DistrictSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<DistrictSearchResult[]>([]);
  const [geo, setGeo] = useState<DistrictGeo[]>([]);

  // 전 상권 좌표(지도 마커) 1회 로드.
  useEffect(() => {
    let alive = true;
    commercialApi
      .geo()
      .then((r) => {
        if (alive) setGeo(r.data);
      })
      .catch(() => {
        if (alive) setGeo([]);
      });
    return () => {
      alive = false;
    };
  }, []);

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

  const activeScore = useMemo(
    () =>
      toScore(
        summary?.detail?.latest_stats?.district_score ??
          (summary?.radar
            ? summary.radar.axes.reduce((a, x) => a + x.value, 0) /
              (summary.radar.axes.length || 1)
            : null),
      ),
    [summary],
  );

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
        <LeafletMap
          points={geo}
          selectedId={selectedId}
          activeName={summary?.detail?.district_name ?? null}
          activeType={summary?.detail?.type_name ?? null}
          activeScore={activeScore}
          onSelect={setSelectedId}
          onOpenProfile={openProfile}
        />
      </div>
    </div>
  );
}
