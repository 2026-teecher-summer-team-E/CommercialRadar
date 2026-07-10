import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { DistrictGeo } from "../../types";
import styles from "./LeafletMap.module.css";

export type MapMode = "pins" | "regions";

interface LeafletMapProps {
  points: DistrictGeo[];
  geojson: GeoJSON.FeatureCollection | null;
  mode: MapMode;
  selectedId: number;
  activeName: string | null;
  activeType: string | null;
  activeScore: number | null;
  onSelect: (id: number) => void;
  onOpenProfile: (id: number) => void;
}

/** 상권유형별 색상. */
const TYPE_COLORS: Record<string, string> = {
  골목상권: "#1d4fd8",
  발달상권: "#e8833a",
  전통시장: "#1b8a5a",
  관광특구: "#9333ea",
};
const colorOf = (type: string | null | undefined) => TYPE_COLORS[type ?? ""] ?? "#64748b";

const SEOUL_CENTER: L.LatLngExpression = [37.5665, 126.978];

export default function LeafletMap({
  points,
  geojson,
  mode,
  selectedId,
  activeName,
  activeType,
  activeScore,
  onSelect,
  onOpenProfile,
}: LeafletMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const rendererRef = useRef<L.Canvas | null>(null);

  const markerGroupRef = useRef<L.FeatureGroup | null>(null);
  const markersRef = useRef<Map<number, L.CircleMarker>>(new Map());
  const geoLayerRef = useRef<L.GeoJSON | null>(null);
  const polysRef = useRef<Map<number, L.Path>>(new Map());

  const onSelectRef = useRef(onSelect);
  const onOpenRef = useRef(onOpenProfile);
  onSelectRef.current = onSelect;
  onOpenRef.current = onOpenProfile;

  // 선택 상권 팝업 DOM(이름/유형/점수 + 프로필 버튼).
  const buildPopup = () => {
    const el = document.createElement("div");
    const name = document.createElement("div");
    name.className = styles.popupName;
    name.textContent = activeName ?? "";
    el.appendChild(name);
    const meta = document.createElement("div");
    meta.className = styles.popupMeta;
    meta.innerHTML = `${activeType ?? ""}${
      activeScore != null ? ` · 상권점수 <span class="${styles.popupScore}">${activeScore}</span>` : ""
    }`;
    el.appendChild(meta);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = styles.popupBtn;
    btn.textContent = "상세 프로필 보기 →";
    btn.addEventListener("click", () => onOpenRef.current(selectedId));
    el.appendChild(btn);
    return el;
  };

  // 1) 지도 1회 생성
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      center: SEOUL_CENTER,
      zoom: 12,
      preferCanvas: true,
      zoomControl: true,
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    rendererRef.current = L.canvas({ padding: 0.5 });
    mapRef.current = map;
    setTimeout(() => map.invalidateSize(), 0);
    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current.clear();
      polysRef.current.clear();
    };
  }, []);

  // 2a) 핀 레이어(포인트 변경 시)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markerGroupRef.current?.remove();
    markersRef.current.clear();
    const group = L.featureGroup();
    points.forEach((p) => {
      const marker = L.circleMarker([p.lat, p.lng], {
        renderer: rendererRef.current ?? undefined,
        radius: 5,
        color: "#ffffff",
        weight: 1,
        fillColor: colorOf(p.type_name),
        fillOpacity: 0.85,
      });
      marker.bindTooltip(p.district_name, { direction: "top", offset: [0, -4] });
      marker.on("click", () => onSelectRef.current(p.id));
      group.addLayer(marker);
      markersRef.current.set(p.id, marker);
    });
    markerGroupRef.current = group;
    if (mode === "pins") group.addTo(map);
  }, [points]); // eslint-disable-line react-hooks/exhaustive-deps

  // 2b) 구역(폴리곤) 레이어(geojson 변경 시)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !geojson) return;
    geoLayerRef.current?.remove();
    polysRef.current.clear();
    const layer = L.geoJSON(geojson, {
      style: (feature) => {
        const c = colorOf(feature?.properties?.type_name);
        return {
          renderer: rendererRef.current ?? undefined,
          color: c,
          weight: 1,
          opacity: 0.65,
          fillColor: c,
          fillOpacity: 0.22,
        };
      },
      onEachFeature: (feature, lyr) => {
        const id = feature.properties?.id as number;
        polysRef.current.set(id, lyr as L.Path);
        lyr.on("click", () => onSelectRef.current(id));
        lyr.bindTooltip(feature.properties?.district_name ?? "", { sticky: true });
      },
    });
    geoLayerRef.current = layer;
    if (mode === "regions") layer.addTo(map);
  }, [geojson]); // eslint-disable-line react-hooks/exhaustive-deps

  // 3) 모드 전환: 활성 레이어만 표시
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (mode === "pins") {
      geoLayerRef.current?.remove();
      if (markerGroupRef.current) markerGroupRef.current.addTo(map);
    } else {
      markerGroupRef.current?.remove();
      if (geoLayerRef.current) geoLayerRef.current.addTo(map);
    }
  }, [mode]);

  // 4) 선택 강조 + 이동 + 팝업
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (mode === "pins") {
      markersRef.current.forEach((m, id) => {
        const sel = id === selectedId;
        m.setStyle({ radius: sel ? 10 : 5, weight: sel ? 3 : 1, fillOpacity: sel ? 1 : 0.8 });
        if (sel) m.bringToFront();
      });
      const sel = markersRef.current.get(selectedId);
      if (sel) {
        map.panTo(sel.getLatLng());
        sel.bindPopup(buildPopup(), { closeButton: true, minWidth: 170 }).openPopup();
      }
    } else {
      polysRef.current.forEach((lyr, id) => {
        const sel = id === selectedId;
        const c = colorOf((lyr as L.Path & { feature?: GeoJSON.Feature }).feature?.properties?.type_name as string);
        lyr.setStyle({ weight: sel ? 2.5 : 1, opacity: sel ? 1 : 0.6, fillColor: c, fillOpacity: sel ? 0.5 : 0.2, color: c });
        if (sel) lyr.bringToFront();
      });
      const sel = polysRef.current.get(selectedId) as L.Polygon | undefined;
      if (sel && typeof sel.getBounds === "function") {
        map.panTo(sel.getBounds().getCenter());
        sel.bindPopup(buildPopup(), { closeButton: true, minWidth: 170 }).openPopup();
      }
    }
  }, [selectedId, mode, activeName, activeType, activeScore]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={containerRef} className={styles.map} aria-label="상권 지도" />;
}
