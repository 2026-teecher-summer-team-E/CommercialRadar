import { Link } from "react-router-dom";
import styles from "./NotFoundPage.module.css";

export default function NotFoundPage() {
  return (
    <div className={styles.wrap}>
      <div className={styles.code}>404</div>
      <h1 className={styles.title}>페이지를 찾을 수 없어요</h1>
      <p className={styles.desc}>주소가 바뀌었거나 존재하지 않는 페이지입니다.</p>
      <Link to="/" className={styles.btn}>
        홈으로 돌아가기
      </Link>
    </div>
  );
}
