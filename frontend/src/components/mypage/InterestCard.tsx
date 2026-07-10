import type { InterestDistrict } from "../../types";
import { formatDate, initialOf, seriesColor, seriesBg } from "./format";
import styles from "./mypage.module.css";

/** 관심 상권 1건 카드. */
export default function InterestCard({
  item,
  index,
}: {
  item: InterestDistrict;
  index: number;
}) {
  const title = item.district_name ?? `상권 #${item.commercial_district_id}`;
  return (
    <li className={styles.card}>
      <span
        className={styles.cardMark}
        style={{ color: seriesColor(index), background: seriesBg(index) }}
        aria-hidden="true"
      >
        {initialOf(title)}
      </span>

      <div className={styles.cardBody}>
        <p className={styles.cardTitle}>{title}</p>
        <div className={styles.cardMeta}>
          {item.category_name && (
            <span className={styles.chip}>{item.category_name}</span>
          )}
          <span className={styles.metaDate}>{formatDate(item.created_at)}</span>
        </div>
        {item.memo && <p className={styles.cardMemo}>{item.memo}</p>}
      </div>
    </li>
  );
}
