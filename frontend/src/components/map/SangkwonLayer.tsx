import styles from "../../pages/MapPage.module.css";
import type { MapPin } from "./mapData";

interface SangkwonLayerProps {
  pins: MapPin[];
  activeName: string | null;
  activeScore: number | null;
  onSearchArea: () => void;
  /** 핀 클릭(선택). */
  onSelectPin: (id: number) => void;
  /** 상권 프로필(대시보드)로 이동. */
  onOpenProfile: (id: number) => void;
}

/**
 * 지도 영역: 스타일화된 회색 그리드 + 상권 점수 핀 목업.
 *
 * 제약: Kakao 지도 SDK 키/좌표 API가 없어 실제 지도 타일을 못 띄운다.
 * Figma 지도 영역 자체가 실제 지도가 아니라 스타일화된 그리드 + 점수 핀 목업이므로
 * 그것을 CSS/SVG로 재현한다. 핀 위치는 정적(목업), 이름·점수는 실데이터.
 */
export default function SangkwonLayer({
  pins,
  activeName,
  activeScore,
  onSearchArea,
  onSelectPin,
  onOpenProfile,
}: SangkwonLayerProps) {
  return (
    <section className={styles.mapArea} aria-label="상권 지도(목업)">
      {/* 스타일화된 그리드 배경 (실제 지도 아님) */}
      <div className={styles.mapGrid} aria-hidden>
        <span className={`${styles.mapBlob} ${styles.blobA}`} />
        <span className={`${styles.mapBlob} ${styles.blobB}`} />
        <span className={`${styles.mapBlob} ${styles.blobC}`} />
      </div>

      {/* 좌상단 현재 상권 뱃지 */}
      {activeName && (
        <div className={styles.mapBadge}>
          <span className={styles.mapBadgeDot} aria-hidden />
          <span className={styles.mapBadgeName}>{activeName}</span>
          {activeScore != null && (
            <span className={styles.mapBadgeTag}>한식 우수</span>
          )}
        </div>
      )}

      {/* 우상단 컨트롤: 지도 옵션 / 새로고침 */}
      <div className={styles.mapControls}>
        <button type="button" className={styles.mapCtrlBtn}>
          <span aria-hidden>🗺</span> 지도 옵션 <span className={styles.mapCtrlCount}>2</span>
        </button>
        <button type="button" className={styles.mapCtrlBtn}>
          <span aria-hidden>↻</span> 새로고침
        </button>
      </div>

      {/* 우상단 줌 컨트롤(장식) */}
      <div className={styles.zoomControls} aria-hidden>
        <button type="button" className={styles.zoomBtn} tabIndex={-1}>
          +
        </button>
        <button type="button" className={styles.zoomBtn} tabIndex={-1}>
          −
        </button>
      </div>

      {/* 점수 핀 (클릭: 미선택→선택, 선택됨→프로필 이동) */}
      {pins.map((pin) => (
        <div
          key={pin.id}
          role="button"
          tabIndex={0}
          title={pin.active ? `${pin.name} 프로필 보기` : `${pin.name} 선택`}
          className={`${styles.pin} ${pin.active ? styles.pinActive : ""}`}
          style={{ left: `${pin.x}%`, top: `${pin.y}%`, cursor: "pointer" }}
          onClick={() => (pin.active ? onOpenProfile(pin.id) : onSelectPin(pin.id))}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              pin.active ? onOpenProfile(pin.id) : onSelectPin(pin.id);
            }
          }}
        >
          {pin.active && (
            <div className={styles.pinCallout}>
              <span className={styles.pinCalloutName}>{pin.name}</span>
              <span className={styles.pinCalloutScore}>
                상권점수 <b>{pin.score ?? "-"}</b>
              </span>
              <span
                style={{
                  display: "block",
                  marginTop: "3px",
                  fontSize: "11px",
                  fontWeight: 700,
                  color: "#fff",
                  opacity: 0.9,
                }}
              >
                상세 프로필 보기 →
              </span>
            </div>
          )}
          <span className={styles.pinScore}>{pin.score ?? "-"}</span>
          <span className={styles.pinLabel}>{pin.name}</span>
        </div>
      ))}

      {/* 하단 중앙: 이 지역 상권 검색 */}
      <button type="button" className={styles.searchAreaBtn} onClick={onSearchArea}>
        <span aria-hidden>⌕</span> 이 지역 상권 검색
      </button>
    </section>
  );
}
