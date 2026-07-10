import type { ReportListItem } from "../../types";
import { formatDate, initialOf, seriesColor, seriesBg } from "./format";
import styles from "./mypage.module.css";

interface ReportCardProps {
  report: ReportListItem;
  index: number;
  onShare: (id: number) => void;
  onRemove: (id: number) => void;
  busy: boolean;
}

/** 저장된 리포트 1건 카드. */
export default function ReportCard({
  report,
  index,
  onShare,
  onRemove,
  busy,
}: ReportCardProps) {
  return (
    <li className={styles.card}>
      <span
        className={styles.cardMark}
        style={{ color: seriesColor(index), background: seriesBg(index) }}
        aria-hidden="true"
      >
        {initialOf(report.district_name ?? report.title)}
      </span>

      <div className={styles.cardBody}>
        <p className={styles.cardTitle}>{report.title}</p>
        <div className={styles.cardMeta}>
          {report.district_name && (
            <span className={styles.chip}>{report.district_name}</span>
          )}
          {report.category_name && (
            <span className={styles.metaText}>{report.category_name}</span>
          )}
          <span className={styles.metaDate}>{formatDate(report.created_at)}</span>
        </div>
        {report.memo && <p className={styles.cardMemo}>{report.memo}</p>}
      </div>

      <div className={styles.cardActions}>
        <button type="button" className={styles.linkBtn} disabled={busy}>
          보기
        </button>
        <button
          type="button"
          className={styles.iconBtn}
          onClick={() => onShare(report.id)}
          disabled={busy}
          aria-label="리포트 공유"
          title="공유"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <circle cx="18" cy="5" r="2.4" stroke="currentColor" strokeWidth="1.6" />
            <circle cx="6" cy="12" r="2.4" stroke="currentColor" strokeWidth="1.6" />
            <circle cx="18" cy="19" r="2.4" stroke="currentColor" strokeWidth="1.6" />
            <path
              d="M8.2 10.8l7.6-4.4M8.2 13.2l7.6 4.4"
              stroke="currentColor"
              strokeWidth="1.6"
            />
          </svg>
        </button>
        <button
          type="button"
          className={`${styles.iconBtn} ${styles.iconBtnDanger}`}
          onClick={() => onRemove(report.id)}
          disabled={busy}
          aria-label="리포트 삭제"
          title="삭제"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </li>
  );
}
