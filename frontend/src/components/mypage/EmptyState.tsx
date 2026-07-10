import styles from "./mypage.module.css";

/** 리스트가 비었을 때 보여주는 안내 블록. */
export default function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className={styles.empty}>
      <span className={styles.emptyIcon} aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
          <path
            d="M6 3h8l4 4v14H6V3z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
          <path
            d="M14 3v4h4"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <p className={styles.emptyTitle}>{title}</p>
      <p className={styles.emptyDesc}>{description}</p>
    </div>
  );
}
