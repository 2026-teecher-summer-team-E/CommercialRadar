import { useMemo, useState } from "react";
import styles from "./AgeGenderCard.module.css";

interface AgeGenderCardProps {
  /** { "10대": n, ... } — 여성(fml) 연령 분포. */
  ageFemale: Record<string, number> | null;
  /** { "10대": n, ... } — 남성(ml) 연령 분포. */
  ageMale: Record<string, number> | null;
}

const AGE_ORDER = ["10대", "20대", "30대", "40대", "50대", "60대이상"];
const AGE_LABEL: Record<string, string> = { "60대이상": "60대+" };

/** 연령·성별 매출 카드. Figma 재현: 연령대 가로 막대(여성/남성 겹침) + 최다 연령 강조. */
export default function AgeGenderCard({ ageFemale, ageMale }: AgeGenderCardProps) {
  const [gender, setGender] = useState<"female" | "male">("female");
  const active = gender === "female" ? ageFemale : ageMale;

  const rows = useMemo(() => {
    const src = active ?? {};
    const total = AGE_ORDER.reduce((a, k) => a + (src[k] ?? 0), 0) || 1;
    const max = Math.max(1, ...AGE_ORDER.map((k) => src[k] ?? 0));
    return AGE_ORDER.map((k) => {
      const v = src[k] ?? 0;
      return { key: k, label: AGE_LABEL[k] ?? k, pct: Math.round((v / total) * 100), rel: v / max };
    });
  }, [active]);

  const top = useMemo(() => rows.reduce((b, r) => (r.pct > b.pct ? r : b), rows[0]), [rows]);
  const hasData = active != null && Object.keys(active).length > 0;

  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <div>
          <h3 className={styles.title}>연령·성별 매출</h3>
          <p className={styles.sub}>
            {hasData ? `최다 · ${top.label} ${top.pct}%` : "데이터 없음"} · 성별 분리
          </p>
        </div>
        <div className={styles.headline}>{hasData ? `${top.label} ${top.pct}%` : "—"}</div>
      </div>

      {hasData ? (
        <div className={styles.bars}>
          {rows.map((r) => (
            <div key={r.key} className={styles.barRow}>
              <span className={styles.barLabel}>{r.label}</span>
              <div className={styles.barTrack}>
                <span
                  className={r.key === top.key ? styles.barFillTop : styles.barFill}
                  style={{ width: `${Math.max(4, r.rel * 100)}%` }}
                />
              </div>
              <span className={r.key === top.key ? styles.barPctTop : styles.barPct}>{r.pct}%</span>
            </div>
          ))}
        </div>
      ) : (
        <div className={styles.empty}>연령·성별 데이터가 없어요.</div>
      )}

      <div className={styles.toggle}>
        <button
          type="button"
          className={gender === "female" ? styles.toggleActive : styles.toggleBtn}
          onClick={() => setGender("female")}
        >
          <i className={styles.dotFemale} /> 여성
        </button>
        <button
          type="button"
          className={gender === "male" ? styles.toggleActive : styles.toggleBtn}
          onClick={() => setGender("male")}
        >
          <i className={styles.dotMale} /> 남성
        </button>
      </div>
    </div>
  );
}
