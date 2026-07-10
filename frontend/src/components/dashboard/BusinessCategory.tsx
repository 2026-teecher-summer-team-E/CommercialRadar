import type { CategoryRankingItem } from "../../types";
import { fmtInt, fmtPct } from "./format";
import styles from "./BusinessCategory.module.css";

interface BusinessCategoryProps {
  items: CategoryRankingItem[];
  /** 최대 표시 개수. */
  limit?: number;
}

/** 업종별 순위를 가로 막대(점포수 비중) 리스트로 표현. */
export default function BusinessCategory({ items, limit = 6 }: BusinessCategoryProps) {
  const shown = items.slice(0, limit);
  if (shown.length === 0) {
    return <div className={styles.empty}>업종 데이터가 없어요.</div>;
  }
  const max = Math.max(1, ...shown.map((it) => it.total_business ?? 0));

  return (
    <ul className={styles.list}>
      {shown.map((it) => {
        const pct = ((it.total_business ?? 0) / max) * 100;
        return (
          <li key={`${it.rank}-${it.category_name ?? ""}`} className={styles.row}>
            <span className={styles.name} title={it.category_name ?? undefined}>
              {it.category_name ?? "—"}
            </span>
            <span className={styles.track}>
              <span className={styles.bar} style={{ width: `${pct}%` }} />
            </span>
            <span className={styles.meta}>
              <span className={styles.count}>{fmtInt(it.total_business)}개</span>
              <span className={styles.rate}>{fmtPct(it.survival_rate)}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
