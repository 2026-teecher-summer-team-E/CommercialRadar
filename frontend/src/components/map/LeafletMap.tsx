import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { DistrictGeo } from "../../types";
import styles from "./LeafletMap.module.css";

interface LeafletMapProps {
  points: DistrictGeo[];
  selectedId: number;
  activeName: string | null;
  activeType: string | null;
  activeScore: number | null;
  onSelect: (id: number) => void;
  onOpenProfile: (id: number) => void;
}

/** 상권유형별 마커 색상. */
const TYPE_COLORS: Record<string, string> = {
  골목상권: "#1d4fd8",
  발달상권: "#e8833a",
  전통시장: "#1b8a5a",
  관광특구: "#9333ea",
};

const SEOUL_CENTER: L.LatLngExpression = [37.5665, 126.978];

/**
 * 실제 OpenStreetMap(Leaflet) 지도 + 상권 중심좌표 마커.
 * 마커가 1650개까지 많아질 수 있어 canvas 렌더러 사용.
 */
export default function LeafletMap({
  points,
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
  const markersRef = useRef<Map<number, L.CircleMarker>>(new Map());

  // 콜백 최신값 유지(effect 재실행 없이 마커 핸들러에서 참조).
  const onSelectRef = useRef(onSelect);
  const onOpenRef = useRef(onOpenProfile);
  onSelectRef.current = onSelect;
  onOpenRef.current = onOpenProfile;

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
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);
    rendererRef.current = L.canvas({ padding: 0.5 });
    mapRef.current = map;
    // 컨테이너 크기 확정 후 리사이즈 보정
    setTimeout(() => map.invalidateSize(), 0);
    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current.clear();
    };
  }, []);

  // 2) 마커 렌더(포인트 변경 시)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current.clear();

    points.forEach((p) => {
      const color = TYPE_COLORS[p.type_name ?? ""] ?? "#64748b";
      const marker = L.circleMarker([p.lat, p.lng], {
        renderer: rendererRef.current ?? undefined,
        radius: 5,
        color: "#ffffff",
        weight: 1,
        fillColor: color,
        fillOpacity: 0.85,
      });
      marker.bindTooltip(p.district_name, { direction: "top", offset: [0, -4] });
      marker.on("click", () => onSelectRef.current(p.id));
      marker.addTo(map);
      markersRef.current.set(p.id, marker);
    });
  }, [points]);

  // 3) 선택 강조 + 이동 + 팝업(프로필 이동 버튼)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((m, id) => {
      const sel = id === selectedId;
      m.setStyle({ radius: sel ? 10 : 5, weight: sel ? 3 : 1, fillOpacity: sel ? 1 : 0.8 });
      if (sel) m.bringToFront();
    });

    const selected = markersRef.current.get(selectedId);
    if (!selected) return;
    map.panTo(selected.getLatLng());

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

    selected.bindPopup(el, { closeButton: true, minWidth: 170 }).openPopup();
  }, [selectedId, activeName, activeType, activeScore]);

  return <div ref={containerRef} className={styles.map} aria-label="상권 지도" />;
}
