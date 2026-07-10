import type { ReactNode } from "react";
import Sidebar from "./Sidebar";
import styles from "./AppLayout.module.css";

/** 좌측 사이드바 + 콘텐츠 영역 레이아웃. 앱 내부 페이지(비교/마이페이지 등)에서 사용. */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className={styles.shell}>
      <Sidebar />
      <main className={styles.main}>{children}</main>
    </div>
  );
}
