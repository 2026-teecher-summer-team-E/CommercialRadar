import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../lib/apiClient";
import { commercialApi } from "../services/commercialApi";
import SangkwonPanel from "../components/map/SangkwonPanel";
import LeafletMap, { type MapMode } from "../components/map/LeafletMap";
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
  const [geojson, setGeojson] = useState<GeoJSON.FeatureCollection | null>(null);
  const [mode, setMode] = useState<MapMode>("regions");

  // 전 상권 좌표(핀) + 경계 폴리곤(구역) 1회 로드.
  useEffect(() => {
    let alive = true;
    commercialApi
      .geo()
      .then((r) => alive && setGeo(r.data))
      .catch(() => alive && setGeo([]));
    commercialApi
      .geojson()
      .then((r) => alive && setGeojson(r.data))
      .catch(() => alive && setGeojson(null));
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

  // 좌측 패널 드롭다운은 '현재 선택 상권'만 표시(검색·선택은 상단 검색바가 담당).
  const panelOptions = useMemo<DistrictSearchResult[]>(() => {
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
  }, [summary]);

  // 검색 결과 클릭 → 실제 상권 선택(selectedId 변경) + 검색 초기화.
  const handlePickSearch = (id: number) => {
    setSelectedId(id);
    setQuery("");
    setOptions([]);
  };

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
      {/* 상단 검색 바 + 자동완성 결과 (앱 네비 사이드바는 AppLayout이 담당) */}
      <div className={styles.searchBar} style={{ position: "relative" }}>
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
        {query.trim() && options.length > 0 && (
          <ul
            style={{
              position: "absolute",
              top: "calc(100% + 6px)",
              left: 0,
              right: 0,
              zIndex: 1200,
              listStyle: "none",
              margin: 0,
              padding: 6,
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 12,
              boxShadow: "var(--shadow-pop)",
              maxHeight: 320,
              overflowY: "auto",
            }}
          >
            {options.map((o) => (
              <li key={o.id}>
                <button
                  type="button"
                  onClick={() => handlePickSearch(o.id)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    padding: "9px 12px",
                    border: "none",
                    background: "transparent",
                    borderRadius: 8,
                    cursor: "pointer",
                    fontFamily: "var(--font-sans)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 2,
                  }}
                >
                  <span style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)" }}>
                    {o.district_name}
                  </span>
                  <span style={{ fontSize: 12, color: "var(--color-muted)" }}>
                    {[o.gu_name, o.dong_name].filter(Boolean).join(" · ")}
                    {o.type_name ? ` · ${o.type_name}` : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
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
        <div style={{ flex: 1, position: "relative", display: "flex", minWidth: 0 }}>
          <div
            style={{
              position: "absolute",
              top: 12,
              right: 12,
              zIndex: 1000,
              display: "flex",
              gap: 2,
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              padding: 3,
              boxShadow: "0 1px 2px rgba(15,23,42,.1)",
            }}
          >
            {(["regions", "pins"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                style={{
                  padding: "6px 14px",
                  border: "none",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 700,
                  fontFamily: "var(--font-sans)",
                  cursor: "pointer",
                  background: mode === m ? "var(--color-primary-light)" : "transparent",
                  color: mode === m ? "var(--color-primary)" : "var(--color-muted)",
                }}
              >
                {m === "regions" ? "구역" : "핀"}
              </button>
            ))}
          </div>
          <LeafletMap
            points={geo}
            geojson={geojson}
            mode={mode}
            selectedId={selectedId}
            activeName={summary?.detail?.district_name ?? null}
            activeType={summary?.detail?.type_name ?? null}
            activeScore={activeScore}
            onSelect={setSelectedId}
            onOpenProfile={openProfile}
          />
        </div>
      </div>
    </div>
  );
}
